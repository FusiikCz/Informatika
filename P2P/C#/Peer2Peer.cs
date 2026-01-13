using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

/**
 * Peer-to-Peer (P2P) socket implementace v C#
 * Každý peer může současně fungovat jako server i klient
 * 
 * Kompatibilní s: Python, C++, Java peery (stejný protokol)
 * 
 * Kompilace:
 *   csc Peer2Peer.cs
 * 
 * Spuštění:
 *   Peer2Peer.exe
 */
class Peer2Peer
{
    private const int DEFAULT_PORT = 8081;
    private const int MAX_PEERS = 50;
    private const int MAX_MESSAGE_SIZE = 40960;
    
    private static Dictionary<string, PeerInfo> connectedPeers = new Dictionary<string, PeerInfo>();
    private static readonly object peersLock = new object();
    private static TcpListener listenerSocket = null;
    private static bool peerRunning = true;
    private static string username = "Peer";
    
    class PeerInfo
    {
        public TcpClient socket;
        public NetworkStream stream;
        public string username;
        public long lastHeartbeat;
        
        public PeerInfo(TcpClient socket, NetworkStream stream, string username)
        {
            this.socket = socket;
            this.stream = stream;
            this.username = username;
            this.lastHeartbeat = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        }
    }
    
    private static bool SendMessage(NetworkStream stream, string message)
    {
        try
        {
            byte[] messageBytes = Encoding.UTF8.GetBytes(message);
            int messageLength = messageBytes.Length;
            
            byte[] lengthBytes = BitConverter.GetBytes(IPAddress.HostToNetworkOrder(messageLength));
            stream.Write(lengthBytes, 0, 4);
            
            if (messageLength > 0)
            {
                stream.Write(messageBytes, 0, messageLength);
            }
            
            stream.Flush();
            return true;
        }
        catch
        {
            return false;
        }
    }
    
    private static string ReceiveMessage(NetworkStream stream)
    {
        try
        {
            byte[] lengthBytes = new byte[4];
            int totalRead = 0;
            while (totalRead < 4)
            {
                int bytesRead = stream.Read(lengthBytes, totalRead, 4 - totalRead);
                if (bytesRead == 0) return null;
                totalRead += bytesRead;
            }
            
            int messageLength = IPAddress.NetworkToHostOrder(BitConverter.ToInt32(lengthBytes, 0));
            if (messageLength > MAX_MESSAGE_SIZE || messageLength < 0) return null;
            
            byte[] messageBytes = new byte[messageLength];
            totalRead = 0;
            while (totalRead < messageLength)
            {
                int bytesRead = stream.Read(messageBytes, totalRead, messageLength - totalRead);
                if (bytesRead == 0) return null;
                totalRead += bytesRead;
            }
            
            return Encoding.UTF8.GetString(messageBytes);
        }
        catch
        {
            return null;
        }
    }
    
    private static void HandleIncomingPeer(TcpClient peerSocket)
    {
        string peerAddress = peerSocket.Client.RemoteEndPoint.ToString();
        string peerUsername = "Peer";
        
        try
        {
            NetworkStream stream = peerSocket.GetStream();
            
            string welcomeMsg = ReceiveMessage(stream);
            if (welcomeMsg != null && welcomeMsg.StartsWith("USERNAME:"))
            {
                peerUsername = welcomeMsg.Substring(9);
                if (peerUsername.Length > 20) peerUsername = peerUsername.Substring(0, 20);
            }
            
            lock (peersLock)
            {
                if (connectedPeers.Count >= MAX_PEERS)
                {
                    SendMessage(stream, "ERROR: Maximální počet peerů dosažen");
                    peerSocket.Close();
                    return;
                }
                connectedPeers[peerAddress] = new PeerInfo(peerSocket, stream, peerUsername);
            }
            
            Console.WriteLine("Peer připojen: " + peerUsername + " (" + peerAddress + ")");
            SendMessage(stream, "Vítejte v P2P síti, " + peerUsername + "! Jste připojeni k " + username + ".");
            
            while (peerRunning)
            {
                string message = ReceiveMessage(stream);
                if (message == null) break;
                
                lock (peersLock)
                {
                    if (connectedPeers.ContainsKey(peerAddress))
                    {
                        connectedPeers[peerAddress].lastHeartbeat = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
                    }
                }
                
                if (message == "/quit")
                {
                    SendMessage(stream, "Odpojování...");
                    break;
                }
                else
                {
                    SendMessage(stream, "Echo: " + message);
                }
            }
        }
        catch
        {
            // Chyba
        }
        finally
        {
            lock (peersLock)
            {
                connectedPeers.Remove(peerAddress);
            }
            try
            {
                peerSocket.Close();
            }
            catch { }
            Console.WriteLine("Peer odpojen: " + peerUsername);
        }
    }
    
    private static void ListenerThread()
    {
        try
        {
            listenerSocket = new TcpListener(IPAddress.Any, DEFAULT_PORT);
            listenerSocket.Start();
            Console.WriteLine("P2P listener naslouchá na portu " + DEFAULT_PORT);
            
            while (peerRunning)
            {
                try
                {
                    TcpClient peerSocket = listenerSocket.AcceptTcpClient();
                    new Thread(() => HandleIncomingPeer(peerSocket)).Start();
                }
                catch
                {
                    if (peerRunning) break;
                }
            }
        }
        catch (Exception e)
        {
            Console.WriteLine("Chyba listeneru: " + e.Message);
        }
    }
    
    private static bool ConnectToPeer(string host, int port)
    {
        string peerAddress = host + ":" + port;
        
        lock (peersLock)
        {
            if (connectedPeers.ContainsKey(peerAddress))
            {
                Console.WriteLine("Již jste připojeni k " + host + ":" + port);
                return false;
            }
        }
        
        try
        {
            TcpClient socket = new TcpClient(host, port);
            NetworkStream stream = socket.GetStream();
            
            SendMessage(stream, "USERNAME:" + username);
            
            string welcome = ReceiveMessage(stream);
            if (welcome != null && !string.IsNullOrEmpty(welcome))
            {
                Console.WriteLine("✓ " + welcome);
            }
            
            lock (peersLock)
            {
                connectedPeers[peerAddress] = new PeerInfo(socket, stream, "Peer_" + port);
            }
            
            return true;
        }
        catch
        {
            Console.WriteLine("Chyba: Nelze se připojit k " + host + ":" + port);
            return false;
        }
    }
    
    private static int BroadcastToAllPeers(string message)
    {
        int sentCount = 0;
        lock (peersLock)
        {
            foreach (PeerInfo peer in connectedPeers.Values)
            {
                if (SendMessage(peer.stream, message))
                {
                    sentCount++;
                }
            }
        }
        return sentCount;
    }
    
    static void Main(string[] args)
    {
        Console.WriteLine("========================================");
        Console.WriteLine("C# P2P Aplikace");
        Console.WriteLine("========================================");
        
        Console.Write("Zadejte vaše jméno (nebo Enter pro výchozí): ");
        string usernameInput = Console.ReadLine();
        if (!string.IsNullOrWhiteSpace(usernameInput))
        {
            username = usernameInput.Trim().Substring(0, Math.Min(20, usernameInput.Length));
        }
        
        new Thread(() => ListenerThread()).Start();
        Thread.Sleep(500);
        
        Console.WriteLine("\nVaše jméno: " + username);
        Console.WriteLine("Nasloucháte na portu: " + DEFAULT_PORT);
        Console.WriteLine("\nDostupné příkazy:");
        Console.WriteLine("  /connect <host> <port>  - Připojení k peeru");
        Console.WriteLine("  /list                  - Seznam peerů");
        Console.WriteLine("  /broadcast <msg>        - Broadcast zpráva");
        Console.WriteLine("  /quit                  - Ukončení");
        Console.WriteLine("========================================");
        Console.WriteLine();
        
        while (peerRunning)
        {
            Console.Write("> ");
            string command = Console.ReadLine();
            
            if (string.IsNullOrWhiteSpace(command)) continue;
            
            if (command == "/quit" || command == "quit")
            {
                break;
            }
            else if (command.StartsWith("/connect "))
            {
                string[] parts = command.Split(' ');
                if (parts.Length >= 3)
                {
                    try
                    {
                        string host = parts[1];
                        int port = int.Parse(parts[2]);
                        ConnectToPeer(host, port);
                    }
                    catch
                    {
                        Console.WriteLine("Chyba: Neplatný port");
                    }
                }
            }
            else if (command == "/list")
            {
                lock (peersLock)
                {
                    Console.WriteLine("\nPřipojení peery:");
                    foreach (var entry in connectedPeers)
                    {
                        Console.WriteLine("  - " + entry.Value.username + " (" + entry.Key + ")");
                    }
                    Console.WriteLine();
                }
            }
            else if (command.StartsWith("/broadcast "))
            {
                string msg = command.Substring(11);
                int count = BroadcastToAllPeers(msg);
                Console.WriteLine("Zpráva odeslána " + count + " peerům");
            }
            else
            {
                int count = BroadcastToAllPeers(command);
                if (count > 0)
                {
                    Console.WriteLine("Zpráva odeslána " + count + " peerům");
                }
            }
        }
        
        peerRunning = false;
        
        lock (peersLock)
        {
            foreach (PeerInfo peer in connectedPeers.Values)
            {
                try
                {
                    peer.socket.Close();
                }
                catch { }
            }
            connectedPeers.Clear();
        }
        
        try
        {
            if (listenerSocket != null)
            {
                listenerSocket.Stop();
            }
        }
        catch { }
        
        Console.WriteLine("Aplikace ukončena");
    }
}
