import java.io.*;
import java.net.*;

/**
 * Socket klient implementace v Javě
 */
public class Client {
    /**
     * Hlavní metoda klienta
     */
    public static void main(String[] args) {
        String hostname = "127.0.0.1";
        int port = 8080;
        
        try (
            // Vytvoření socketu a připojení k serveru
            Socket socket = new Socket(hostname, port);
            
            // Získání vstupního a výstupního streamu
            PrintWriter out = new PrintWriter(socket.getOutputStream(), true);
            BufferedReader in = new BufferedReader(
                new InputStreamReader(socket.getInputStream())
            );
            
            // Čtení z konzole
            BufferedReader userInput = new BufferedReader(
                new InputStreamReader(System.in)
            )
        ) {
            System.out.println("Připojeno k serveru na " + hostname + ":" + port);
            System.out.println("Zadejte zprávy (pro ukončení zadejte 'quit'):");
            
            // Hlavní smyčka pro komunikaci
            String userMessage;
            while ((userMessage = userInput.readLine()) != null) {
                if (userMessage.equalsIgnoreCase("quit")) {
                    break;
                }
                
                // Odeslání zprávy serveru
                out.println(userMessage);
                
                // Přijetí odpovědi od serveru
                String response = in.readLine();
                if (response == null) {
                    System.out.println("Server ukončil spojení");
                    break;
                }
                
                System.out.println("Odpověď serveru: " + response);
            }
            
        } catch (UnknownHostException e) {
            System.err.println("Chyba: Neznámý hostitel " + hostname);
        } catch (ConnectException e) {
            System.err.println("Chyba: Nelze se připojit k serveru. Ujistěte se, že server běží.");
        } catch (IOException e) {
            System.err.println("Chyba I/O: " + e.getMessage());
        }
        
        System.out.println("Odpojeno od serveru");
    }
}
