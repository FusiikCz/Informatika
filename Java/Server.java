import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;

/**
 * Rozšířená socket server implementace v Javě
 * Používá thread-per-client architekturu s length-prefixed protokolem
 * 
 * Kompatibilní s: Python, C++, C# klienty
 * 
 * Kompilace:
 *   javac Server.java
 * 
 * Spuštění:
 *   java Server
 */
public class Server {
    private static final int PORT = 8080;
    private static final int MAX_CLIENTS = 100;
    private static final int MAX_MESSAGE_SIZE = 40960; // 40KB
    private static final int BUFFER_SIZE = 4096;
    
    // Struktura pro uložení informací o klientovi
    private static class ClientInfo {
        Socket socket;
        DataOutputStream out;
        String username;
        
        ClientInfo(Socket socket, DataOutputStream out, String username) {
            this.socket = socket;
            this.out = out;
            this.username = username;
        }
    }
    
    // Seznam všech připojených klientů
    private static List<ClientInfo> clients = new ArrayList<>();
    private static final Object clientsLock = new Object();
    
    /**
     * Broadcast zprávy všem klientům
     */
    private static void broadcastMessage(String message, Socket excludeSocket) {
        synchronized (clientsLock) {
            List<ClientInfo> disconnected = new ArrayList<>();
            
            for (ClientInfo client : clients) {
                if (excludeSocket != null && client.socket == excludeSocket) {
                    continue;
                }
                
                try {
                    sendMessage(client.out, message);
                } catch (Exception e) {
                    disconnected.add(client);
                }
            }
            
            // Odstranění odpojených klientů
            clients.removeAll(disconnected);
        }
    }
    
    /**
     * Odešle zprávu s prefixem délky (kompatibilní s Python/C++/C#)
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
     * Přijme zprávu s prefixem délky (kompatibilní s Python/C++/C#)
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
     * Vnitřní třída pro obsluhu jednoho klienta
     */
    private static class ClientHandler implements Runnable {
        private Socket clientSocket;
        
        public ClientHandler(Socket socket) {
            this.clientSocket = socket;
        }
        
        @Override
        public void run() {
            String username = "User";
            
            try {
                DataInputStream in = new DataInputStream(clientSocket.getInputStream());
                DataOutputStream out = new DataOutputStream(clientSocket.getOutputStream());
                
                String clientAddress = clientSocket.getRemoteSocketAddress().toString();
                System.out.println("Komunikace s klientem: " + clientAddress);
                
                // Přijetí uživatelského jména (volitelné)
                String welcomeMsg = receiveMessage(in);
                if (welcomeMsg != null && welcomeMsg.startsWith("USERNAME:")) {
                    username = welcomeMsg.substring(9);
                    if (username.length() > 20) username = username.substring(0, 20);
                    System.out.println("Klient nastavil jméno: " + username);
                }
                
                // Přidání klienta do seznamu (thread-safe)
                synchronized (clientsLock) {
                    if (clients.size() >= MAX_CLIENTS) {
                        sendMessage(out, "ERROR: Server je plný");
                        clientSocket.close();
                        return;
                    }
                    clients.add(new ClientInfo(clientSocket, out, username));
                    System.out.println("Klient připojen: " + username + ". Celkem klientů: " + clients.size());
                }
                
                // Odeslání uvítací zprávy
                sendMessage(out, "Vítejte v chatu, " + username + "! Napište zprávu a stiskněte Enter. Použijte /help pro nápovědu.");
                
                // Broadcast o novém připojení
                broadcastMessage("Server: " + username + " se připojil k chatu", clientSocket);
                
                // Hlavní smyčka pro komunikaci s klientem
                while (true) {
                    String message = receiveMessage(in);
                    
                    if (message == null) {
                        // Klient se odpojil
                        break;
                    }
                    
                    System.out.println("Přijato od " + username + ": " + message);
                    
                    // Speciální příkazy
                    if (message.startsWith("/")) {
                        if (message.equals("/quit")) {
                            sendMessage(out, "Odpojování...");
                            break;
                        } else if (message.equals("/list")) {
                            synchronized (clientsLock) {
                                StringBuilder userList = new StringBuilder("Připojení uživatelé: ");
                                for (int i = 0; i < clients.size(); i++) {
                                    if (i > 0) userList.append(", ");
                                    userList.append(clients.get(i).username);
                                }
                                sendMessage(out, userList.toString());
                            }
                        } else if (message.equals("/help")) {
                            sendMessage(out, "=== Chat Server - Nápověda ===\nVšechny vaše zprávy se automaticky posílají všem uživatelům v chatu.\n\nDostupné příkazy:\n/quit - Odpojení ze serveru\n/list - Seznam připojených uživatelů\n/help - Zobrazení této nápovědy\n\nPro odeslání zprávy jednoduše napište text a stiskněte Enter.");
                        } else {
                            sendMessage(out, "ERROR: Neznámý příkaz. Použijte /help");
                        }
                    } else {
                        // Chat zpráva - broadcast všem klientům
                        String chatMessage = username + ": " + message;
                        System.out.println("Chat zpráva od " + username + ": " + message);
                        broadcastMessage(chatMessage, null);
                    }
                }
                
            } catch (IOException e) {
                System.err.println("Chyba při komunikaci s klientem: " + e.getMessage());
            } finally {
                // Broadcast o odpojení
                broadcastMessage("Server: " + username + " opustil chat", null);
                
                // Odstranění klienta ze seznamu (thread-safe)
                synchronized (clientsLock) {
                    clients.removeIf(c -> c.socket == clientSocket);
                    System.out.println("Klient odpojen: " + username + ". Celkem klientů: " + clients.size());
                }
                
                // Uzavření socketu
                try {
                    clientSocket.close();
                } catch (IOException e) {
                    System.err.println("Chyba při uzavírání socketu: " + e.getMessage());
                }
            }
        }
    }
    
    /**
     * Hlavní metoda serveru
     */
    public static void main(String[] args) {
        System.out.println("========================================");
        System.out.println("Java Chat Server");
        System.out.println("========================================");
        System.out.println("Server naslouchá na portu " + PORT + "...");
        System.out.println("Maximální počet klientů: " + MAX_CLIENTS);
        System.out.println("Kompatibilní s: Python, C++, C# klienty");
        System.out.println("Stiskněte Ctrl+C pro ukončení");
        System.out.println("========================================");
        
        try (ServerSocket serverSocket = new ServerSocket(PORT)) {
            // Hlavní smyčka - přijímání nových klientů
            while (true) {
                try {
                    // Přijetí nového klienta
                    Socket clientSocket = serverSocket.accept();
                    
                    // Vytvoření nového vlákna pro obsluhu klienta
                    Thread clientThread = new Thread(new ClientHandler(clientSocket));
                    clientThread.start();
                    
                } catch (IOException e) {
                    System.err.println("Chyba při přijímání klienta: " + e.getMessage());
                }
            }
            
        } catch (IOException e) {
            System.err.println("Chyba při vytváření serverového socketu: " + e.getMessage());
            System.exit(1);
        }
    }
}
