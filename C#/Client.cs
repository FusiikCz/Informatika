using System;
using System.Net.Sockets;
using System.Text;

/**
 * Rozšířená socket klient implementace v C#
 * Používá length-prefixed protokol (kompatibilní s Python/C++/Java servery)
 * 
 * Kompilace:
 *   csc Client.cs
 * 
 * Spuštění:
 *   Client.exe
 */
class Client
{
    private const string HOSTNAME = "127.0.0.1";
    private const int PORT = 8080;
    private const int MAX_MESSAGE_SIZE = 40960; // 40KB
    
    /**
     * Odešle zprávu s prefixem délky (kompatibilní s Python/C++/Java servery)
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
     * Přijme zprávu s prefixem délky (kompatibilní s Python/C++/Java servery)
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
     * Hlavní metoda klienta
     */
    static void Main(string[] args)
    {
        try
        {
            Console.WriteLine("========================================");
            Console.WriteLine("C# Socket Client");
            Console.WriteLine("========================================");
            Console.WriteLine($"Připojování k serveru na {HOSTNAME}:{PORT}...");
            
            TcpClient client = new TcpClient(HOSTNAME, PORT);
            NetworkStream stream = client.GetStream();
            
            Console.WriteLine($"✓ Připojeno k serveru na {HOSTNAME}:{PORT}");
            
            // Přijetí uvítací zprávy
            string welcome = ReceiveMessage(stream);
            if (welcome != null && !string.IsNullOrEmpty(welcome))
            {
                Console.WriteLine(welcome);
            }
            
            // Volitelné: Odeslání uživatelského jména
            Console.Write("Zadejte vaše jméno (nebo Enter pro výchozí): ");
            string username = Console.ReadLine();
            
            if (!string.IsNullOrWhiteSpace(username))
            {
                SendMessage(stream, "USERNAME:" + username.Trim());
            }
            else
            {
                SendMessage(stream, "USERNAME:Guest");
            }
            
            Console.WriteLine("\n=== Chat připojen ===");
            Console.WriteLine("Napište zprávu a stiskněte Enter pro odeslání všem uživatelům");
            Console.WriteLine("Použijte '/help' pro nápovědu, '/quit' pro odpojení\n");
            
            // Hlavní smyčka pro komunikaci
            while (true)
            {
                Console.Write("> ");
                string message = Console.ReadLine();
                
                if (string.IsNullOrWhiteSpace(message))
                {
                    continue;
                }
                
                if (message.ToLower() == "quit" || 
                    message == "/quit" || 
                    message.ToLower() == "exit" || 
                    message == "/exit")
                {
                    SendMessage(stream, "/quit");
                    break;
                }
                
                // Odeslání zprávy serveru
                if (!SendMessage(stream, message))
                {
                    Console.WriteLine("Chyba při odesílání zprávy");
                    break;
                }
                
                // Přijetí odpovědi od serveru
                string response = ReceiveMessage(stream);
                if (response == null || string.IsNullOrEmpty(response))
                {
                    Console.WriteLine("Server ukončil spojení");
                    break;
                }
                
                // Rozlišení mezi systémovými zprávami a chat zprávami
                if (response.StartsWith("Server:"))
                {
                    Console.WriteLine($"[SYSTEM] {response}");
                }
                else if (response.Contains(":") && !response.StartsWith("ERROR") && !response.StartsWith("INFO"))
                {
                    // Chat zpráva od uživatele
                    Console.WriteLine(response);
                }
                else
                {
                    // Jiné zprávy
                    Console.WriteLine($"[Server] {response}");
                }
            }
            
            // Uzavření streamu a klienta
            stream.Close();
            client.Close();
        }
        catch (SocketException e)
        {
            Console.WriteLine($"Chyba socketu: {e.Message}");
            if (e.SocketErrorCode == SocketError.ConnectionRefused)
            {
                Console.WriteLine("Nelze se připojit k serveru. Ujistěte se, že server běží.");
            }
        }
        catch (Exception e)
        {
            Console.WriteLine($"Chyba: {e.Message}");
        }
        
        Console.WriteLine("Odpojeno od serveru");
    }
}
