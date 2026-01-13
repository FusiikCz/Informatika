import java.io.*;
import java.net.*;
import java.nio.ByteBuffer;
import java.util.HashMap;
import java.util.Map;
import java.util.Scanner;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Peer-to-Peer (P2P) socket implementace v Javě
 * Každý peer může současně fungovat jako server i klient
 * 
 * Kompatibilní s: Python, C++, C# peery (stejný protokol)
 * 
 * Kompilace:
 *   javac Peer2Peer.java
 * 
 * Spuštění:
 *   java Peer2Peer
 */
public class Peer2Peer {
    private static final int DEFAULT_PORT = 8081;
    private static final int MAX_PEERS = 50;
    private static final int MAX_MESSAGE_SIZE = 40960;
    
    private static Map<String, PeerInfo> connectedPeers = new ConcurrentHashMap<>();
    private static ServerSocket listenerSocket = null;
    private static boolean peerRunning = true;
    private static String username = "Peer";
    
    static class PeerInfo {
        Socket socket;
        DataInputStream in;
        DataOutputStream out;
        String username;
        long lastHeartbeat;
        
        PeerInfo(Socket socket, DataInputStream in, DataOutputStream out, String username) {
            this.socket = socket;
            this.in = in;
            this.out = out;
            this.username = username;
            this.lastHeartbeat = System.currentTimeMillis();
        }
    }
    
    private static boolean sendMessage(DataOutputStream out, String message) {
        try {
            byte[] messageBytes = message.getBytes("UTF-8");
            out.writeInt(messageBytes.length);
            if (messageBytes.length > 0) {
                out.write(messageBytes);
            }
            out.flush();
            return true;
        } catch (IOException e) {
            return false;
        }
    }
    
    private static String receiveMessage(DataInputStream in) {
        try {
            int messageLength = in.readInt();
            if (messageLength > MAX_MESSAGE_SIZE || messageLength < 0) {
                return null;
            }
            byte[] messageBytes = new byte[messageLength];
            int totalRead = 0;
            while (totalRead < messageLength) {
                int bytesRead = in.read(messageBytes, totalRead, messageLength - totalRead);
                if (bytesRead == -1) return null;
                totalRead += bytesRead;
            }
            return new String(messageBytes, "UTF-8");
        } catch (IOException e) {
            return null;
        }
    }
    
    private static void handleIncomingPeer(Socket peerSocket) {
        String peerAddress = peerSocket.getRemoteSocketAddress().toString();
        String peerUsername = "Peer";
        
        try {
            DataInputStream in = new DataInputStream(peerSocket.getInputStream());
            DataOutputStream out = new DataOutputStream(peerSocket.getOutputStream());
            
            String welcomeMsg = receiveMessage(in);
            if (welcomeMsg != null && welcomeMsg.startsWith("USERNAME:")) {
                peerUsername = welcomeMsg.substring(9);
                if (peerUsername.length() > 20) peerUsername = peerUsername.substring(0, 20);
            }
            
            synchronized (connectedPeers) {
                if (connectedPeers.size() >= MAX_PEERS) {
                    sendMessage(out, "ERROR: Maximální počet peerů dosažen");
                    peerSocket.close();
                    return;
                }
                connectedPeers.put(peerAddress, new PeerInfo(peerSocket, in, out, peerUsername));
            }
            
            System.out.println("Peer připojen: " + peerUsername + " (" + peerAddress + ")");
            sendMessage(out, "Vítejte v P2P síti, " + peerUsername + "! Jste připojeni k " + username + ".");
            
            while (peerRunning) {
                String message = receiveMessage(in);
                if (message == null) break;
                
                synchronized (connectedPeers) {
                    if (connectedPeers.containsKey(peerAddress)) {
                        connectedPeers.get(peerAddress).lastHeartbeat = System.currentTimeMillis();
                    }
                }
                
                if (message.equals("/quit")) {
                    sendMessage(out, "Odpojování...");
                    break;
                } else {
                    sendMessage(out, "Echo: " + message);
                }
            }
        } catch (IOException e) {
            // Chyba
        } finally {
            synchronized (connectedPeers) {
                connectedPeers.remove(peerAddress);
            }
            try {
                peerSocket.close();
            } catch (IOException e) {}
            System.out.println("Peer odpojen: " + peerUsername);
        }
    }
    
    private static void listenerThread() {
        try {
            listenerSocket = new ServerSocket(DEFAULT_PORT);
            System.out.println("P2P listener naslouchá na portu " + DEFAULT_PORT);
            
            while (peerRunning) {
                try {
                    Socket peerSocket = listenerSocket.accept();
                    new Thread(() -> handleIncomingPeer(peerSocket)).start();
                } catch (IOException e) {
                    if (peerRunning) break;
                }
            }
        } catch (IOException e) {
            System.err.println("Chyba listeneru: " + e.getMessage());
        }
    }
    
    private static boolean connectToPeer(String host, int port) {
        String peerAddress = host + ":" + port;
        
        synchronized (connectedPeers) {
            if (connectedPeers.containsKey(peerAddress)) {
                System.out.println("Již jste připojeni k " + host + ":" + port);
                return false;
            }
        }
        
        try {
            Socket socket = new Socket(host, port);
            DataInputStream in = new DataInputStream(socket.getInputStream());
            DataOutputStream out = new DataOutputStream(socket.getOutputStream());
            
            sendMessage(out, "USERNAME:" + username);
            
            String welcome = receiveMessage(in);
            if (welcome != null && !welcome.isEmpty()) {
                System.out.println("✓ " + welcome);
            }
            
            synchronized (connectedPeers) {
                connectedPeers.put(peerAddress, new PeerInfo(socket, in, out, "Peer_" + port));
            }
            
            return true;
        } catch (IOException e) {
            System.out.println("Chyba: Nelze se připojit k " + host + ":" + port);
            return false;
        }
    }
    
    private static int broadcastToAllPeers(String message) {
        int sentCount = 0;
        synchronized (connectedPeers) {
            for (PeerInfo peer : connectedPeers.values()) {
                if (sendMessage(peer.out, message)) {
                    sentCount++;
                }
            }
        }
        return sentCount;
    }
    
    public static void main(String[] args) {
        System.out.println("========================================");
        System.out.println("Java P2P Aplikace");
        System.out.println("========================================");
        
        Scanner scanner = new Scanner(System.in);
        System.out.print("Zadejte vaše jméno (nebo Enter pro výchozí): ");
        String usernameInput = scanner.nextLine();
        if (!usernameInput.trim().isEmpty()) {
            username = usernameInput.trim().substring(0, Math.min(20, usernameInput.length()));
        }
        
        new Thread(() -> listenerThread()).start();
        
        try {
            Thread.sleep(500);
        } catch (InterruptedException e) {}
        
        System.out.println("\nVaše jméno: " + username);
        System.out.println("Nasloucháte na portu: " + DEFAULT_PORT);
        System.out.println("\nDostupné příkazy:");
        System.out.println("  /connect <host> <port>  - Připojení k peeru");
        System.out.println("  /list                  - Seznam peerů");
        System.out.println("  /broadcast <msg>        - Broadcast zpráva");
        System.out.println("  /quit                  - Ukončení");
        System.out.println("========================================");
        System.out.println();
        
        while (peerRunning) {
            System.out.print("> ");
            String command = scanner.nextLine();
            
            if (command.trim().isEmpty()) continue;
            
            if (command.equals("/quit") || command.equals("quit")) {
                break;
            } else if (command.startsWith("/connect ")) {
                String[] parts = command.split(" ", 3);
                if (parts.length >= 3) {
                    try {
                        String host = parts[1];
                        int port = Integer.parseInt(parts[2]);
                        connectToPeer(host, port);
                    } catch (NumberFormatException e) {
                        System.out.println("Chyba: Neplatný port");
                    }
                }
            } else if (command.equals("/list")) {
                synchronized (connectedPeers) {
                    System.out.println("\nPřipojení peery:");
                    for (Map.Entry<String, PeerInfo> entry : connectedPeers.entrySet()) {
                        System.out.println("  - " + entry.getValue().username + " (" + entry.getKey() + ")");
                    }
                    System.out.println();
                }
            } else if (command.startsWith("/broadcast ")) {
                String msg = command.substring(11);
                int count = broadcastToAllPeers(msg);
                System.out.println("Zpráva odeslána " + count + " peerům");
            } else {
                int count = broadcastToAllPeers(command);
                if (count > 0) {
                    System.out.println("Zpráva odeslána " + count + " peerům");
                }
            }
        }
        
        peerRunning = false;
        
        synchronized (connectedPeers) {
            for (PeerInfo peer : connectedPeers.values()) {
                try {
                    peer.socket.close();
                } catch (IOException e) {}
            }
            connectedPeers.clear();
        }
        
        try {
            if (listenerSocket != null) {
                listenerSocket.close();
            }
        } catch (IOException e) {}
        
        System.out.println("Aplikace ukončena");
        scanner.close();
    }
}
