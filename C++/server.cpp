/**
 * Rozšířená socket server implementace v C++
 * Používá thread-per-client architekturu s length-prefixed protokolem
 * 
 * Kompatibilní s: Python, Java, C# klienty
 * 
 * Kompilace:
 *   g++ -std=c++11 -pthread server.cpp -o server
 */

#include <iostream>
#include <thread>
#include <vector>
#include <mutex>
#include <algorithm>
#include <cstring>
#include <cstdint>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

// Konfigurace
const int PORT = 8080;
const int MAX_CLIENTS = 100;
const size_t BUFFER_SIZE = 4096;
const uint32_t MAX_MESSAGE_SIZE = 40960; // 40KB

// Struktura pro uložení informací o klientovi
struct ClientInfo {
    int socket;
    std::string username;
};

// Sdílený seznam klientů
std::vector<ClientInfo> clients;
std::mutex clients_mutex; // Mutex pro synchronizaci přístupu k seznamu klientů

/**
 * Odešle zprávu s prefixem délky (kompatibilní s Python/Java/C#)
 * Formát: [4 byty délka (big-endian)][zpráva]
 */
bool send_message(int sock, const std::string& message) {
    // Převod délky zprávy na big-endian (network byte order)
    uint32_t message_length = htonl(static_cast<uint32_t>(message.length()));
    
    // Odeslání délky zprávy (4 byty)
    ssize_t sent = send(sock, &message_length, 4, 0);
    if (sent != 4) {
        return false;
    }
    
    // Odeslání samotné zprávy
    if (message.length() > 0) {
        sent = send(sock, message.c_str(), message.length(), 0);
        if (sent != static_cast<ssize_t>(message.length())) {
            return false;
        }
    }
    
    return true;
}

/**
 * Přijme zprávu s prefixem délky (kompatibilní s Python/Java/C#)
 */
std::string receive_message(int sock) {
    // Přijetí délky zprávy (4 byty)
    uint32_t message_length_net;
    ssize_t received = recv(sock, &message_length_net, 4, MSG_WAITALL);
    
    if (received != 4) {
        return ""; // Spojení ukončeno nebo chyba
    }
    
    // Převod z network byte order na host byte order
    uint32_t message_length = ntohl(message_length_net);
    
    // Validace délky
    if (message_length > MAX_MESSAGE_SIZE) {
        std::cerr << "Chyba: Příliš dlouhá zpráva: " << message_length << " bytů" << std::endl;
        return "";
    }
    
    // Přijetí samotné zprávy
    std::string message(message_length, '\0');
    if (message_length > 0) {
        received = recv(sock, &message[0], message_length, MSG_WAITALL);
        if (received != static_cast<ssize_t>(message_length)) {
            return "";
        }
    }
    
    return message;
}

/**
 * Broadcast zprávy všem klientům
 */
void broadcast_message(const std::string& message, int exclude_socket = -1) {
    std::lock_guard<std::mutex> lock(clients_mutex);
    std::vector<int> disconnected;
    
    for (auto& client : clients) {
        if (client.socket == exclude_socket) {
            continue;
        }
        
        if (!send_message(client.socket, message)) {
            disconnected.push_back(client.socket);
        }
    }
    
    // Odstranění odpojených klientů
    clients.erase(
        std::remove_if(clients.begin(), clients.end(),
            [&disconnected](const ClientInfo& c) {
                return std::find(disconnected.begin(), disconnected.end(), c.socket) != disconnected.end();
            }),
        clients.end()
    );
}

/**
 * Funkce pro obsluhu jednoho klienta
 * @param client_fd Deskriptor socketu klienta
 */
void handle_client(int client_fd) {
    std::string username = "User";
    
    try {
        // Přijetí uživatelského jména (volitelné)
        std::string welcome_msg = receive_message(client_fd);
        if (!welcome_msg.empty() && welcome_msg.find("USERNAME:") == 0) {
            username = welcome_msg.substr(9);
            if (username.length() > 20) username = username.substr(0, 20);
            std::cout << "Klient nastavil jméno: " << username << std::endl;
        }
        
        // Přidání klienta do seznamu (thread-safe)
        {
            std::lock_guard<std::mutex> lock(clients_mutex);
            if (clients.size() >= MAX_CLIENTS) {
                send_message(client_fd, "ERROR: Server je plný");
                close(client_fd);
                return;
            }
            clients.push_back({client_fd, username});
            std::cout << "Klient připojen: " << username << ". Celkem klientů: " << clients.size() << std::endl;
        }
        
        // Odeslání uvítací zprávy
        send_message(client_fd, "Vítejte v chatu, " + username + "! Napište zprávu a stiskněte Enter. Použijte /help pro nápovědu.");
        
        // Broadcast o novém připojení
        broadcast_message("Server: " + username + " se připojil k chatu", client_fd);
        
        // Hlavní smyčka pro komunikaci s klientem
        while (true) {
            std::string message = receive_message(client_fd);
            
            if (message.empty()) {
                // Klient se odpojil
                break;
            }
            
            std::cout << "Přijato od " << username << " (" << client_fd << "): " << message << std::endl;
            
            // Speciální příkazy
            if (message.length() > 0 && message[0] == '/') {
                if (message == "/quit") {
                    send_message(client_fd, "Odpojování...");
                    break;
                } else if (message == "/list") {
                    std::lock_guard<std::mutex> lock(clients_mutex);
                    std::string user_list = "Připojení uživatelé: ";
                    for (size_t i = 0; i < clients.size(); ++i) {
                        if (i > 0) user_list += ", ";
                        user_list += clients[i].username;
                    }
                    send_message(client_fd, user_list);
                } else if (message == "/help") {
                    send_message(client_fd, "=== Chat Server - Nápověda ===\nVšechny vaše zprávy se automaticky posílají všem uživatelům v chatu.\n\nDostupné příkazy:\n/quit - Odpojení ze serveru\n/list - Seznam připojených uživatelů\n/help - Zobrazení této nápovědy\n\nPro odeslání zprávy jednoduše napište text a stiskněte Enter.");
                } else {
                    send_message(client_fd, "ERROR: Neznámý příkaz. Použijte /help");
                }
            } else {
                // Chat zpráva - broadcast všem klientům
                std::string chat_message = username + ": " + message;
                std::cout << "Chat zpráva od " << username << ": " << message << std::endl;
                broadcast_message(chat_message);
            }
        }
    } catch (...) {
        std::cerr << "Chyba při komunikaci s klientem " << client_fd << std::endl;
    }
    
    // Broadcast o odpojení
    broadcast_message("Server: " + username + " opustil chat");
    
    // Odstranění klienta ze seznamu (thread-safe)
    {
        std::lock_guard<std::mutex> lock(clients_mutex);
        clients.erase(
            std::remove_if(clients.begin(), clients.end(),
                [client_fd](const ClientInfo& c) { return c.socket == client_fd; }),
            clients.end()
        );
        std::cout << "Klient odpojen: " << username << ". Celkem klientů: " << clients.size() << std::endl;
    }
    
    close(client_fd);
}

/**
 * Hlavní funkce serveru
 */
int main() {
    // Vytvoření socketu
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    
    if (server_fd < 0) {
        std::cerr << "Chyba při vytváření socketu" << std::endl;
        return 1;
    }
    
    // Nastavení socketu pro opakované použití adresy
    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));
    
    // Konfigurace adresy serveru
    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PORT);
    addr.sin_addr.s_addr = INADDR_ANY;
    
    // Navázání socketu na adresu a port
    if (bind(server_fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "Chyba při navázání socketu" << std::endl;
        close(server_fd);
        return 1;
    }
    
    // Naslouchání příchozím připojením
    if (listen(server_fd, MAX_CLIENTS) < 0) {
        std::cerr << "Chyba při naslouchání" << std::endl;
        close(server_fd);
        return 1;
    }
    
    std::cout << "========================================" << std::endl;
    std::cout << "C++ Chat Server" << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << "Server naslouchá na portu " << PORT << "..." << std::endl;
    std::cout << "Maximální počet klientů: " << MAX_CLIENTS << std::endl;
    std::cout << "Kompatibilní s: Python, Java, C# klienty" << std::endl;
    std::cout << "Stiskněte Ctrl+C pro ukončení" << std::endl;
    std::cout << "========================================" << std::endl;
    
    // Hlavní smyčka - přijímání nových klientů
    while (true) {
        // Přijetí nového klienta
        int client = accept(server_fd, nullptr, nullptr);
        
        if (client < 0) {
            std::cerr << "Chyba při přijímání klienta" << std::endl;
            continue;
        }
        
        // Vytvoření nového vlákna pro obsluhu klienta
        std::thread(handle_client, client).detach();
    }
    
    // Tento kód se nikdy neprovede, ale pro úplnost:
    close(server_fd);
    return 0;
}
