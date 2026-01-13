import java.io.*;
import java.net.*;

/**
 * Rozšířená socket klient implementace v Javě
 * Používá length-prefixed protokol (kompatibilní s Python/C++/C# servery)
 * 
 * Kompilace:
 *   javac Client.java
 * 
 * Spuštění:
 *   java Client
 */
public class Client {
    private static final String HOSTNAME = "127.0.0.1";
    private static final int PORT = 8080;
    private static final int MAX_MESSAGE_SIZE = 40960; // 40KB
    
    /**
     * Odešle zprávu s prefixem délky (kompatibilní s Python/C++/C# servery)
     */
    private static boolean sendMessage(DataOutputStream out, String message) {
        try {
            byte[] messageBytes = message.getBytes("UTF-8");
            int messageLength = messageBytes.length;
            
            // Odeslání délky zprávy (4 byty, big-endian)
            out.writeInt(messageLength);
            
            // Odeslání samotné zprávy
            if (messageLength > 0) {
                out.write(messageBytes);
            }
            
            out.flush();
            return true;
        } catch (IOException e) {
            System.err.println("Chyba při odesílání zprávy: " + e.getMessage());
            return false;
        }
    }
    
    /**
     * Přijme zprávu s prefixem délky (kompatibilní s Python/C++/C# servery)
     */
    private static String receiveMessage(DataInputStream in) {
        try {
            // Přijetí délky zprávy (4 byty)
            int messageLength = in.readInt();
            
            // Validace délky
            if (messageLength > MAX_MESSAGE_SIZE || messageLength < 0) {
                System.err.println("Chyba: Neplatná délka zprávy: " + messageLength);
                return null;
            }
            
            // Přijetí samotné zprávy
            byte[] messageBytes = new byte[messageLength];
            int totalRead = 0;
            while (totalRead < messageLength) {
                int bytesRead = in.read(messageBytes, totalRead, messageLength - totalRead);
                if (bytesRead == -1) {
                    return null; // Spojení ukončeno
                }
                totalRead += bytesRead;
            }
            
            return new String(messageBytes, "UTF-8");
        } catch (IOException e) {
            return null;
        }
    }
    
    /**
     * Hlavní metoda klienta
     */
    public static void main(String[] args) {
        try (
            Socket socket = new Socket(HOSTNAME, PORT);
            DataInputStream in = new DataInputStream(socket.getInputStream());
            DataOutputStream out = new DataOutputStream(socket.getOutputStream());
            BufferedReader userInput = new BufferedReader(new InputStreamReader(System.in))
        ) {
            System.out.println("========================================");
            System.out.println("Java Socket Client");
            System.out.println("========================================");
            System.out.println("✓ Připojeno k serveru na " + HOSTNAME + ":" + PORT);
            
            // Přijetí uvítací zprávy
            String welcome = receiveMessage(in);
            if (welcome != null && !welcome.isEmpty()) {
                System.out.println(welcome);
            }
            
            // Volitelné: Odeslání uživatelského jména
            System.out.print("Zadejte vaše jméno (nebo Enter pro výchozí): ");
            String username = userInput.readLine();
            
            if (username != null && !username.trim().isEmpty()) {
                sendMessage(out, "USERNAME:" + username.trim());
            } else {
                sendMessage(out, "USERNAME:Guest");
            }
            
            System.out.println("\n=== Chat připojen ===");
            System.out.println("Napište zprávu a stiskněte Enter pro odeslání všem uživatelům");
            System.out.println("Použijte '/help' pro nápovědu, '/quit' pro odpojení\n");
            
            // Hlavní smyčka pro komunikaci
            String userMessage;
            while ((userMessage = userInput.readLine()) != null) {
                if (userMessage.trim().isEmpty()) {
                    continue;
                }
                
                if (userMessage.equalsIgnoreCase("quit") || 
                    userMessage.equals("/quit") || 
                    userMessage.equals("exit") || 
                    userMessage.equals("/exit")) {
                    sendMessage(out, "/quit");
                    break;
                }
                
                // Odeslání zprávy serveru
                if (!sendMessage(out, userMessage)) {
                    System.err.println("Chyba při odesílání zprávy");
                    break;
                }
                
                // Přijetí odpovědi od serveru
                String response = receiveMessage(in);
                if (response == null || response.isEmpty()) {
                    System.out.println("Server ukončil spojení");
                    break;
                }
                
                // Rozlišení mezi systémovými zprávami a chat zprávami
                if (response.startsWith("Server:")) {
                    System.out.println("[SYSTEM] " + response);
                } else if (response.contains(":") && !response.startsWith("ERROR") && !response.startsWith("INFO")) {
                    // Chat zpráva od uživatele
                    System.out.println(response);
                } else {
                    // Jiné zprávy
                    System.out.println("[Server] " + response);
                }
            }
            
        } catch (UnknownHostException e) {
            System.err.println("Chyba: Neznámý hostitel " + HOSTNAME);
        } catch (ConnectException e) {
            System.err.println("Chyba: Nelze se připojit k serveru. Ujistěte se, že server běží.");
        } catch (IOException e) {
            System.err.println("Chyba I/O: " + e.getMessage());
        }
        
        System.out.println("Odpojeno od serveru");
    }
}
