/**
 * Peer-to-Peer (P2P) socket implementace v C++
 * Každý peer může současně fungovat jako server i klient
 * 
 * Kompatibilní s: Python, Java, C# peery (stejný protokol)
 * 
 * Kompilace:
 *   g++ -std=c++11 -pthread peer2peer.cpp -o peer2peer
 * 
 * Spuštění:
 *   ./peer2peer
 */

#include <iostream>
#include <thread>
#include <vector>
#include <mutex>
#include <map>
#include <string>
#include <cstring>
#include <cstdint>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <ctime>
#include <chrono>

// Konfigurace
const int DEFAULT_PORT = 8081;
const int MAX_PEERS = 50;
const size_t BUFFER_SIZE = 4096;
const uint32_t MAX_MESSAGE_SIZE = 40960;
const int CONNECTION_TIMEOUT = 10;
const int HEARTBEAT_INTERVAL = 30;

// Struktura pro peer informace
struct PeerInfo {
    int socket;
    std::string username;
    time_t last_heartbeat;
};

// Globální stav
std::map<std::pair<std::string, int>, PeerInfo> connected_peers;
std::mutex peers_mutex;
bool peer_running = true;
int listener_socket = -1;
std::string username = "Peer";

/**
 * Odešle zprávu s prefixem délky
 */
bool send_message(int sock, const std::string& message) {
    uint32_t message_length = htonl(static_cast<uint32_t>(message.length()));
    
    if (send(sock, &message_length, 4, 0) != 4) {
        return false;
    }
    
    if (message.length() > 0) {
        if (send(sock, message.c_str(), message.length(), 0) != static_cast<ssize_t>(message.length())) {
            return false;
        }
    }
    
    return true;
}

/**
 * Přijme zprávu s prefixem délky
 */
std::string receive_message(int sock) {
    uint32_t message_length_net;
    if (recv(sock, &message_length_net, 4, MSG_WAITALL) != 4) {
        return "";
    }
    
    uint32_t message_length = ntohl(message_length_net);
    
    if (message_length > MAX_MESSAGE_SIZE) {
        return "";
    }
    
    std::string message(message_length, '\0');
    if (message_length > 0) {
        if (recv(sock, &message[0], message_length, MSG_WAITALL) != static_cast<ssize_t>(message_length)) {
            return "";
        }
    }
    
    return message;
}

/**
 * Obsluha příchozího peera
 */
void handle_incoming_peer(int peer_sock, std::string peer_host, int peer_port) {
    std::pair<std::string, int> peer_address = std::make_pair(peer_host, peer_port);
    std::string peer_username = "Peer_" + std::to_string(peer_port);
    
    try {
        // Přijetí uživatelského jména
        std::string welcome_msg = receive_message(peer_sock);
        if (!welcome_msg.empty() && welcome_msg.find("USERNAME:") == 0) {
            peer_username = welcome_msg.substr(9);
            if (peer_username.length() > 20) peer_username = peer_username.substr(0, 20);
        }
        
        // Přidání peera
        {
            std::lock_guard<std::mutex> lock(peers_mutex);
            if (connected_peers.size() >= MAX_PEERS) {
                send_message(peer_sock, "ERROR: Maximální počet peerů dosažen");
                close(peer_sock);
                return;
            }
            PeerInfo info;
            info.socket = peer_sock;
            info.username = peer_username;
            info.last_heartbeat = time(nullptr);
            connected_peers[peer_address] = info;
            std::cout << "Peer připojen: " << peer_username << " (" << peer_host << ":" << peer_port << ")" << std::endl;
        }
        
        // Odeslání uvítací zprávy
        send_message(peer_sock, "Vítejte v P2P síti, " + peer_username + "! Jste připojeni k " + username + ".");
        
        // Hlavní smyčka
        while (peer_running) {
            std::string message = receive_message(peer_sock);
            
            if (message.empty()) {
                break;
            }
            
            // Aktualizace heartbeat
            {
                std::lock_guard<std::mutex> lock(peers_mutex);
                if (connected_peers.find(peer_address) != connected_peers.end()) {
                    connected_peers[peer_address].last_heartbeat = time(nullptr);
                }
            }
            
            // Zpracování zprávy
            if (message == "/quit") {
                send_message(peer_sock, "Odpojování...");
                break;
            } else {
                send_message(peer_sock, "Echo: " + message);
            }
        }
    } catch (...) {
        // Chyba
    }
    
    // Odstranění peera
    {
        std::lock_guard<std::mutex> lock(peers_mutex);
        connected_peers.erase(peer_address);
        std::cout << "Peer odpojen: " << peer_username << std::endl;
    }
    
    close(peer_sock);
}

/**
 * Vlákno pro naslouchání
 */
void listener_thread_func() {
    listener_socket = socket(AF_INET, SOCK_STREAM, 0);
    
    if (listener_socket < 0) {
        return;
    }
    
    int opt = 1;
    setsockopt(listener_socket, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(DEFAULT_PORT);
    addr.sin_addr.s_addr = INADDR_ANY;
    
    if (bind(listener_socket, (sockaddr*)&addr, sizeof(addr)) < 0) {
        close(listener_socket);
        return;
    }
    
    listen(listener_socket, MAX_PEERS);
    std::cout << "P2P listener naslouchá na portu " << DEFAULT_PORT << std::endl;
    
    while (peer_running) {
        sockaddr_in peer_addr;
        socklen_t addr_len = sizeof(peer_addr);
        int peer_sock = accept(listener_socket, (sockaddr*)&peer_addr, &addr_len);
        
        if (peer_sock < 0) {
            continue;
        }
        
        char peer_host[INET_ADDRSTRLEN];
        inet_ntop(AF_INET, &peer_addr.sin_addr, peer_host, INET_ADDRSTRLEN);
        int peer_port = ntohs(peer_addr.sin_port);
        
        std::thread(handle_incoming_peer, peer_sock, std::string(peer_host), peer_port).detach();
    }
    
    close(listener_socket);
}

/**
 * Připojení k peeru
 */
bool connect_to_peer(const std::string& host, int port) {
    std::pair<std::string, int> peer_address = std::make_pair(host, port);
    
    {
        std::lock_guard<std::mutex> lock(peers_mutex);
        if (connected_peers.find(peer_address) != connected_peers.end()) {
            std::cout << "Již jste připojeni k " << host << ":" << port << std::endl;
            return false;
        }
    }
    
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        return false;
    }
    
    sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    
    if (inet_pton(AF_INET, host.c_str(), &server_addr.sin_addr) <= 0) {
        close(sock);
        return false;
    }
    
    if (connect(sock, (sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        close(sock);
        std::cout << "Chyba: Nelze se připojit k " << host << ":" << port << std::endl;
        return false;
    }
    
    send_message(sock, "USERNAME:" + username);
    
    std::string welcome = receive_message(sock);
    if (!welcome.empty()) {
        std::cout << "✓ " << welcome << std::endl;
    }
    
    {
        std::lock_guard<std::mutex> lock(peers_mutex);
        PeerInfo info;
        info.socket = sock;
        info.username = "Peer_" + std::to_string(port);
        info.last_heartbeat = time(nullptr);
        connected_peers[peer_address] = info;
    }
    
    return true;
}

/**
 * Broadcast všem peerům
 */
int broadcast_to_all_peers(const std::string& message) {
    int sent_count = 0;
    
    std::lock_guard<std::mutex> lock(peers_mutex);
    for (auto& pair : connected_peers) {
        if (send_message(pair.second.socket, message)) {
            sent_count++;
        }
    }
    
    return sent_count;
}

/**
 * Hlavní funkce
 */
int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "C++ P2P Aplikace" << std::endl;
    std::cout << "========================================" << std::endl;
    
    std::cout << "Zadejte vaše jméno (nebo Enter pro výchozí): ";
    std::string username_input;
    std::getline(std::cin, username_input);
    if (!username_input.empty()) {
        username = username_input.substr(0, 20);
    }
    
    // Spuštění listeneru
    std::thread listener_thread(listener_thread_func);
    listener_thread.detach();
    
    std::this_thread::sleep_for(std::chrono::milliseconds(500));
    
    std::cout << "\nVaše jméno: " << username << std::endl;
    std::cout << "Nasloucháte na portu: " << DEFAULT_PORT << std::endl;
    std::cout << "\nDostupné příkazy:" << std::endl;
    std::cout << "  /connect <host> <port>  - Připojení k peeru" << std::endl;
    std::cout << "  /list                  - Seznam peerů" << std::endl;
    std::cout << "  /broadcast <msg>       - Broadcast zpráva" << std::endl;
    std::cout << "  /quit                  - Ukončení" << std::endl;
    std::cout << "========================================" << std::endl << std::endl;
    
    std::string command;
    while (peer_running) {
        std::cout << "> ";
        std::getline(std::cin, command);
        
        if (command.empty()) continue;
        
        if (command == "/quit" || command == "quit") {
            break;
        } else if (command.find("/connect ") == 0) {
            size_t pos1 = command.find(' ', 9);
            size_t pos2 = command.find(' ', pos1 + 1);
            if (pos1 != std::string::npos && pos2 != std::string::npos) {
                std::string host = command.substr(9, pos1 - 9);
                int port = std::stoi(command.substr(pos1 + 1, pos2 - pos1 - 1));
                connect_to_peer(host, port);
            }
        } else if (command == "/list") {
            std::lock_guard<std::mutex> lock(peers_mutex);
            std::cout << "\nPřipojení peery:" << std::endl;
            for (const auto& pair : connected_peers) {
                std::cout << "  - " << pair.second.username << " (" 
                          << pair.first.first << ":" << pair.first.second << ")" << std::endl;
            }
            std::cout << std::endl;
        } else if (command.find("/broadcast ") == 0) {
            std::string msg = command.substr(11);
            int count = broadcast_to_all_peers(msg);
            std::cout << "Zpráva odeslána " << count << " peerům" << std::endl;
        } else {
            // Broadcast jako výchozí
            int count = broadcast_to_all_peers(command);
            if (count > 0) {
                std::cout << "Zpráva odeslána " << count << " peerům" << std::endl;
            }
        }
    }
    
    peer_running = false;
    
    {
        std::lock_guard<std::mutex> lock(peers_mutex);
        for (auto& pair : connected_peers) {
            close(pair.second.socket);
        }
        connected_peers.clear();
    }
    
    if (listener_socket >= 0) {
        close(listener_socket);
    }
    
    std::cout << "Aplikace ukončena" << std::endl;
    return 0;
}
