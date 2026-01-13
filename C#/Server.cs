using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

/**
 * Rozšířená socket server implementace v C#
 * Používá thread-per-client architekturu s length-prefixed protokolem
 * 
 * Kompatibilní s: Python, C++, Java klienty
 * 
 * Kompilace:
 *   csc Server.cs
 * 
 * Spuštění:
 *   Server.exe
 */
class Server
{
    private const int PORT = 8080;
    private const int MAX_CLIENTS = 100;
    private const int MAX_MESSAGE_SIZE = 40960; // 40KB
    private const int BUFFER_SIZE = 4096;
    
    // Struktura pro uložení informací o klientovi
    private class ClientInfo
    {
        public TcpClient socket;
        public NetworkStream stream;
        public string username;
        
        public ClientInfo(TcpClient socket, NetworkStream stream, string username)
        {
            this.socket = socket;
            this.stream = stream;
            this.username = username;
        }
    }
    
    // Seznam všech připojených klientů
    private static List<ClientInfo> clients = new List<ClientInfo>();
    private static readonly object clientsLock = new object();
    
    /**
     * Broadcast zprávy všem klientům
     */
    private static void BroadcastMessage(string message, TcpClient excludeClient = null)
    {
        lock (clientsLock)
        {
            List<ClientInfo> disconnected = new List<ClientInfo>();
            
            foreach (ClientInfo client in clients)
            {
                if (excludeClient != null && client.socket == excludeClient)
                {
                    continue;
                }
                
                try
                {
                    SendMessage(client.stream, message);
                }
                catch
                {
                    disconnected.Add(client);
                }
            }
            
            // Odstranění odpojených klientů
            foreach (ClientInfo client in disconnected)
            {
                clients.Remove(client);
            }
        }
    }
    
    /**
     * Odešle zprávu s prefixem délky (kompatibilní s Python/C++/Java)
     */
    private static bool SendMessage(NetworkStream stream, string message)
    {
        try
        {
            byte[] messageBytes = Encoding.UTF8.GetBytes(message);
            int messageLength = messageBytes.Length;
            
            // Odeslání délky zprávy (4 byty, big-endian)
            byte[] lengthBytes = BitConverter.GetBytes(IPAddress.HostToNetworkOrder(messageLength));
            stream.Write(lengthBytes, 0, 4);
            
            // Odeslání samotné zprávy
            if (messageLength > 0)
            {
                stream.Write(messageBytes, 0, messageLength);
            }
            
            stream.Flush();
            return true;
        }
        catch (Exception e)
        {
            Console.WriteLine($"Chyba při odesílání zprávy: {e.Message}");
            return false;
        }
    }
    
    /**
     * Přijme zprávu s prefixem délky (kompatibilní s Python/C++/Java)
     */
    private static string ReceiveMessage(NetworkStream stream)
    {
        try
        {
            // Přijetí délky zprávy (4 byty)
            byte[] lengthBytes = new byte[4];
            int totalRead = 0;
            while (totalRead < 4)
            {
                int bytesRead = stream.Read(lengthBytes, totalRead, 4 - totalRead);
                if (bytesRead == 0)
                {
                    return null; // Spojení ukončeno
                }
                totalRead += bytesRead;
            }
            
            // Převod z big-endian na int
            int messageLength = IPAddress.NetworkToHostOrder(BitConverter.ToInt32(lengthBytes, 0));
            
            // Validace délky
            if (messageLength > MAX_MESSAGE_SIZE || messageLength < 0)
            {
                Console.WriteLine($"Chyba: Neplatná délka zprávy: {messageLength}");
                return null;
            }
            
            // Přijetí samotné zprávy
            byte[] messageBytes = new byte[messageLength];
            totalRead = 0;
            while (totalRead < messageLength)
            {
                int bytesRead = stream.Read(messageBytes, totalRead, messageLength - totalRead);
                if (bytesRead == 0)
                {
                    return null; // Spojení ukončeno
                }
                totalRead += bytesRead;
            }
            
            return Encoding.UTF8.GetString(messageBytes);
        }
        catch (Exception)
        {
            return null;
        }
    }
    
    /**
     * Funkce pro obsluhu jednoho klienta
     */
    static void HandleClient(TcpClient client)
    {
        string username = "User";
        
        try
        {
            NetworkStream stream = client.GetStream();
            string clientAddress = client.Client.RemoteEndPoint.ToString();
            Console.WriteLine($"Komunikace s klientem: {clientAddress}");
            
            // Přijetí uživatelského jména (volitelné)
            string welcomeMsg = ReceiveMessage(stream);
            if (welcomeMsg != null && welcomeMsg.StartsWith("USERNAME:"))
            {
                username = welcomeMsg.Substring(9);
                if (username.Length > 20) username = username.Substring(0, 20);
                Console.WriteLine($"Klient nastavil jméno: {username}");
            }
            
            // Přidání klienta do seznamu (thread-safe)
            lock (clientsLock)
            {
                if (clients.Count >= MAX_CLIENTS)
                {
                    SendMessage(stream, "ERROR: Server je plný");
                    client.Close();
                    return;
                }
                clients.Add(new ClientInfo(client, stream, username));
                Console.WriteLine($"Klient připojen: {username}. Celkem klientů: {clients.Count}");
            }
            
            // Odeslání uvítací zprávy
            SendMessage(stream, $"Vítejte v chatu, {username}! Napište zprávu a stiskněte Enter. Použijte /help pro nápovědu.");
            
            // Broadcast o novém připojení
            BroadcastMessage($"Server: {username} se připojil k chatu", client);
            
            // Hlavní smyčka pro komunikaci s klientem
            while (true)
            {
                string message = ReceiveMessage(stream);
                
                if (message == null)
                {
                    // Klient se odpojil
                    break;
                }
                
                Console.WriteLine($"Přijato od {username}: {message}");
                
                // Speciální příkazy
                if (message.StartsWith("/"))
                {
                    if (message == "/quit")
                    {
                        SendMessage(stream, "Odpojování...");
                        break;
                    }
                    else if (message == "/list")
                    {
                        lock (clientsLock)
                        {
                            string userList = "Připojení uživatelé: ";
                            for (int i = 0; i < clients.Count; i++)
                            {
                                if (i > 0) userList += ", ";
                                userList += clients[i].username;
                            }
                            SendMessage(stream, userList);
                        }
                    }
                    else if (message == "/help")
                    {
                        SendMessage(stream, "=== Chat Server - Nápověda ===\nVšechny vaše zprávy se automaticky posílají všem uživatelům v chatu.\n\nDostupné příkazy:\n/quit - Odpojení ze serveru\n/list - Seznam připojených uživatelů\n/help - Zobrazení této nápovědy\n\nPro odeslání zprávy jednoduše napište text a stiskněte Enter.");
                    }
                    else
                    {
                        SendMessage(stream, "ERROR: Neznámý příkaz. Použijte /help");
                    }
                }
                else
                {
                    // Chat zpráva - broadcast všem klientům
                    string chatMessage = username + ": " + message;
                    Console.WriteLine($"Chat zpráva od {username}: {message}");
                    BroadcastMessage(chatMessage);
                }
            }
        }
        catch (Exception e)
        {
            Console.WriteLine($"Chyba při komunikaci s klientem: {e.Message}");
        }
        finally
        {
            // Broadcast o odpojení
            BroadcastMessage($"Server: {username} opustil chat");
            
            // Odstranění klienta ze seznamu (thread-safe)
            lock (clientsLock)
            {
                clients.RemoveAll(c => c.socket == client);
                Console.WriteLine($"Klient odpojen: {username}. Celkem klientů: {clients.Count}");
            }
            
            // Uzavření klienta
            client.Close();
        }
    }
    
    /**
     * Hlavní metoda serveru
     */
    static void Main(string[] args)
    {
        Console.WriteLine("========================================");
        Console.WriteLine("C# Chat Server");
        Console.WriteLine("========================================");
        Console.WriteLine($"Server naslouchá na portu {PORT}...");
        Console.WriteLine($"Maximální počet klientů: {MAX_CLIENTS}");
        Console.WriteLine("Kompatibilní s: Python, C++, Java klienty");
        Console.WriteLine("Stiskněte Ctrl+C pro ukončení");
        Console.WriteLine("========================================");
        
        TcpListener listener = new TcpListener(IPAddress.Any, PORT);
        
        try
        {
            listener.Start();
            
            // Hlavní smyčka - přijímání nových klientů
            while (true)
            {
                try
                {
                    // Přijetí nového klienta
                    TcpClient client = listener.AcceptTcpClient();
                    
                    // Vytvoření nového vlákna pro obsluhu klienta
                    Thread clientThread = new Thread(() => HandleClient(client));
                    clientThread.IsBackground = true;
                    clientThread.Start();
                }
                catch (Exception e)
                {
                    Console.WriteLine($"Chyba při přijímání klienta: {e.Message}");
                }
            }
        }
        catch (Exception e)
        {
            Console.WriteLine($"Chyba při vytváření serveru: {e.Message}");
        }
        finally
        {
            listener.Stop();
            Console.WriteLine("Server ukončen");
        }
    }
}
