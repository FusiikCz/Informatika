using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

/**
 * Socket server implementace v C#
 * Používá thread-per-client architekturu
 */
class Server
{
    // Seznam všech připojených klientů
    private static List<TcpClient> clients = new List<TcpClient>();
    private static readonly object clientsLock = new object(); // Zámek pro thread-safe přístup
    
    /**
     * Funkce pro obsluhu jednoho klienta
     * @param client TcpClient objekt klienta
     */
    static void HandleClient(TcpClient client)
    {
        // Přidání klienta do seznamu (thread-safe)
        lock (clientsLock)
        {
            clients.Add(client);
            Console.WriteLine($"Klient připojen. Celkem klientů: {clients.Count}");
        }
        
        try
        {
            // Získání síťového streamu
            NetworkStream stream = client.GetStream();
            byte[] buffer = new byte[1024];
            
            string clientAddress = client.Client.RemoteEndPoint.ToString();
            Console.WriteLine($"Komunikace s klientem: {clientAddress}");
            
            // Hlavní smyčka pro komunikaci s klientem
            while (true)
            {
                // Přijetí zprávy od klienta
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                
                if (bytesRead == 0)
                {
                    // Klient se odpojil
                    break;
                }
                
                // Dekódování zprávy z bytů na string
                string message = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                Console.WriteLine($"Přijato od klienta: {message}");
                
                // Echo - odeslání zprávy zpět klientovi
                string response = "Echo: " + message;
                byte[] responseBytes = Encoding.UTF8.GetBytes(response);
                stream.Write(responseBytes, 0, responseBytes.Length);
            }
        }
        catch (Exception e)
        {
            Console.WriteLine($"Chyba při komunikaci s klientem: {e.Message}");
        }
        finally
        {
            // Odstranění klienta ze seznamu (thread-safe)
            lock (clientsLock)
            {
                clients.Remove(client);
                Console.WriteLine($"Klient odpojen. Celkem klientů: {clients.Count}");
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
        int port = 8080;
        
        // Vytvoření TCP listeneru
        // IPAddress.Any = přijímat na všech rozhraních
        TcpListener listener = new TcpListener(IPAddress.Any, port);
        
        try
        {
            // Spuštění naslouchání
            listener.Start();
            Console.WriteLine($"Server naslouchá na portu {port}...");
            
            // Hlavní smyčka - přijímání nových klientů
            while (true)
            {
                try
                {
                    // Přijetí nového klienta
                    // AcceptTcpClient() blokuje, dokud se nepřipojí nový klient
                    TcpClient client = listener.AcceptTcpClient();
                    
                    // Vytvoření nového vlákna pro obsluhu klienta
                    Thread clientThread = new Thread(() => HandleClient(client));
                    clientThread.IsBackground = true; // Background thread se ukončí s hlavním programem
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
            // Zastavení listeneru
            listener.Stop();
            Console.WriteLine("Server ukončen");
        }
    }
}
