import java.io.*;
import java.net.*;
import java.util.ArrayList;
import java.util.List;

/**
 * Socket server implementace v Javě
 * Používá thread-per-client architekturu
 */
public class Server {
    // Seznam všech připojených klientů
    private static List<Socket> clients = new ArrayList<>();
    private static final Object clientsLock = new Object(); // Zámek pro thread-safe přístup
    
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
            // Přidání klienta do seznamu (thread-safe)
            synchronized (clientsLock) {
                clients.add(clientSocket);
                System.out.println("Klient připojen. Celkem klientů: " + clients.size());
            }
            
            try {
                // Získání vstupního a výstupního streamu
                BufferedReader in = new BufferedReader(
                    new InputStreamReader(clientSocket.getInputStream())
                );
                PrintWriter out = new PrintWriter(
                    clientSocket.getOutputStream(), true
                );
                
                String clientAddress = clientSocket.getRemoteSocketAddress().toString();
                System.out.println("Komunikace s klientem: " + clientAddress);
                
                // Hlavní smyčka pro komunikaci s klientem
                String message;
                while ((message = in.readLine()) != null) {
                    System.out.println("Přijato od klienta: " + message);
                    
                    // Echo - odeslání zprávy zpět klientovi
                    String response = "Echo: " + message;
                    out.println(response);
                }
                
            } catch (IOException e) {
                System.err.println("Chyba při komunikaci s klientem: " + e.getMessage());
            } finally {
                // Odstranění klienta ze seznamu (thread-safe)
                synchronized (clientsLock) {
                    clients.remove(clientSocket);
                    System.out.println("Klient odpojen. Celkem klientů: " + clients.size());
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
        int port = 8080;
        
        // Vytvoření serverového socketu
        try (ServerSocket serverSocket = new ServerSocket(port)) {
            System.out.println("Server naslouchá na portu " + port + "...");
            
            // Hlavní smyčka - přijímání nových klientů
            while (true) {
                try {
                    // Přijetí nového klienta
                    // accept() blokuje, dokud se nepřipojí nový klient
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
