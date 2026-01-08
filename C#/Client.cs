using System;
using System.Net.Sockets;
using System.Text;

/**
 * Socket klient implementace v C#
 */
class Client
{
    /**
     * Hlavní metoda klienta
     */
    static void Main(string[] args)
    {
        string hostname = "127.0.0.1";
        int port = 8080;
        
        try
        {
            // Vytvoření TCP klienta a připojení k serveru
            TcpClient client = new TcpClient(hostname, port);
            
            // Získání síťového streamu
            NetworkStream stream = client.GetStream();
            
            Console.WriteLine($"Připojeno k serveru na {hostname}:{port}");
            Console.WriteLine("Zadejte zprávy (pro ukončení zadejte 'quit'):");
            
            // Hlavní smyčka pro komunikaci
            while (true)
            {
                // Čtení zprávy od uživatele
                Console.Write("> ");
                string message = Console.ReadLine();
                
                if (message == null || message.ToLower() == "quit")
                {
                    break;
                }
                
                // Odeslání zprávy serveru
                // encode() převede string na byty
                byte[] messageBytes = Encoding.UTF8.GetBytes(message);
                stream.Write(messageBytes, 0, messageBytes.Length);
                
                // Přijetí odpovědi od serveru
                byte[] buffer = new byte[1024];
                int bytesRead = stream.Read(buffer, 0, buffer.Length);
                
                if (bytesRead == 0)
                {
                    Console.WriteLine("Server ukončil spojení");
                    break;
                }
                
                // Dekódování odpovědi z bytů na string
                string response = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                Console.WriteLine($"Odpověď serveru: {response}");
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
