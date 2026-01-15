/**
 * Rozšířená socket server implementace v C++
 * Používá thread-per-client architekturu s length-prefixed protokolem
 * 
 * Kompatibilní s: Python klienty
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
#include <ctime>
#include <iomanip>
#include <sstream>
#include <chrono>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>

// Konfigurace
const int PORT = 8080;
const int MAX_CLIENTS = 100;
const size_t BUFFER_SIZE = 4096;
const uint32_t MAX_MESSAGE_SIZE = 40960; // 40KB
const double HEARTBEAT_INTERVAL = 300.0;  // Interval pro heartbeat (sekundy)
const double HEARTBEAT_TIMEOUT = 100.0;   // Timeout pro heartbeat odpověď (sekundy)
const int RATE_LIMIT_MESSAGES = 10;      // Maximální počet zpráv
const double RATE_LIMIT_WINDOW = 1.0;    // Časové okno v sekundách

// Struktura pro uložení informací o klientovi
struct ClientInfo {
    int socket;
    std::string username;
    int p2p_port;  // Port pro P2P připojení
    double last_heartbeat;  // Čas posledního úspěšného heartbeat
    double last_message_time;  // Čas poslední zprávy pro rate limiting
    int message_count;  // Počet zpráv v aktuálním okně
};

// Sdílený seznam klientů
std::vector<ClientInfo> clients;
std::mutex clients_mutex; // Mutex pro synchronizaci přístupu k seznamu klientů

/**
 * Odešle zprávu s prefixem délky (kompatibilní s Python)
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
 * Přijme zprávu s prefixem délky (kompatibilní s Python)
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
 * Získání aktuálního času ve formátu HH:MM
 */
std::string get_current_time() {
    std::time_t now = std::time(nullptr);
    std::tm* timeinfo = std::localtime(&now);
    std::ostringstream oss;
    oss << std::setfill('0') << std::setw(2) << timeinfo->tm_hour << ":"
        << std::setw(2) << timeinfo->tm_min;
    return oss.str();
}

/**
 * Získání aktuálního času jako double (sekundy od epochy)
 */
double get_current_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto duration = now.time_since_epoch();
    return std::chrono::duration<double>(duration).count();
}

/**
 * Kontrola rate limitingu pro klienta
 */
bool check_rate_limit(int client_fd) {
    double current_time = get_current_timestamp();
    std::lock_guard<std::mutex> lock(clients_mutex);
    
    for (auto& client : clients) {
        if (client.socket == client_fd) {
            // Kontrola, zda uplynulo dost času pro reset okna
            if (current_time - client.last_message_time >= RATE_LIMIT_WINDOW) {
                // Reset okna
                client.last_message_time = current_time;
                client.message_count = 1;
                return true;
            } else if (client.message_count < RATE_LIMIT_MESSAGES) {
                // Zvýšení počtu zpráv
                client.message_count++;
                return true;
            } else {
                // Rate limit překročen
                return false;
            }
        }
    }
    return true;
}

/**
 * Aktualizace času posledního heartbeat pro klienta
 */
void update_heartbeat(int client_fd) {
    double current_time = get_current_timestamp();
    std::lock_guard<std::mutex> lock(clients_mutex);
    
    for (auto& client : clients) {
        if (client.socket == client_fd) {
            client.last_heartbeat = current_time;
            break;
        }
    }
}

/**
 * Heartbeat monitor - kontroluje připojení klientů
 */
void heartbeat_monitor() {
    while (true) {
        sleep(static_cast<unsigned int>(HEARTBEAT_INTERVAL));
        double current_time = get_current_timestamp();
        std::vector<int> disconnected;
        
        {
            std::lock_guard<std::mutex> lock(clients_mutex);
            for (const auto& client : clients) {
                // Kontrola, zda klient neodpovídá příliš dlouho
                if (current_time - client.last_heartbeat > HEARTBEAT_TIMEOUT * 2) {
                    std::cout << "Klient " << client.username << " neodpovídá na heartbeat - odpojování" << std::endl;
                    disconnected.push_back(client.socket);
                } else {
                    // Odeslání ping zprávy
                    if (!send_message(client.socket, "PING")) {
                        disconnected.push_back(client.socket);
                    }
                }
            }
        }
        
        // Odstranění odpojených klientů
        if (!disconnected.empty()) {
            std::lock_guard<std::mutex> lock(clients_mutex);
            clients.erase(
                std::remove_if(clients.begin(), clients.end(),
                    [&disconnected](const ClientInfo& c) {
                        return std::find(disconnected.begin(), disconnected.end(), c.socket) != disconnected.end();
                    }),
                clients.end()
            );
            
            for (int fd : disconnected) {
                close(fd);
            }
        }
    }
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
    int p2p_port = 8081;  // Výchozí P2P port
    
    try {
        // Přijetí uživatelského jména a P2P portu (volitelné)
        std::string welcome_msg = receive_message(client_fd);
        if (!welcome_msg.empty()) {
            if (welcome_msg.find("SETUP:") == 0) {
                // Formát: SETUP:username:p2p_port
                size_t pos1 = welcome_msg.find(":", 6);
                size_t pos2 = welcome_msg.find(":", pos1 + 1);
                if (pos1 != std::string::npos) {
                    username = welcome_msg.substr(6, pos1 - 6);
                    if (username.length() > 20) username = username.substr(0, 20);
                }
                if (pos2 != std::string::npos) {
                    try {
                        p2p_port = std::stoi(welcome_msg.substr(pos2 + 1));
                    } catch (...) {
                        p2p_port = 8081;
                    }
                }
                std::cout << "Klient nastavil jméno: " << username << ", P2P port: " << p2p_port << std::endl;
            } else if (welcome_msg.find("USERNAME:") == 0) {
                username = welcome_msg.substr(9);
                if (username.length() > 20) username = username.substr(0, 20);
                std::cout << "Klient nastavil jméno: " << username << std::endl;
            }
        }
        
        // Přidání klienta do seznamu (thread-safe)
        {
            std::lock_guard<std::mutex> lock(clients_mutex);
            if (clients.size() >= MAX_CLIENTS) {
                send_message(client_fd, "ERROR: Server je plný");
                close(client_fd);
                return;
            }
            double current_time = get_current_timestamp();
            clients.push_back({client_fd, username, p2p_port, current_time, current_time, 0});
            std::cout << "Klient připojen: " << username << ". Celkem klientů: " << clients.size() << std::endl;
        }
        
        // Získání počtu připojených uživatelů
        int user_count;
        {
            std::lock_guard<std::mutex> lock(clients_mutex);
            user_count = clients.size();
        }
        
        // Odeslání uvítací zprávy s počtem uživatelů
        std::string user_text = (user_count > 1) ? "uživatelé" : "uživatel";
        send_message(client_fd, "Vítejte v chatu, " + username + "! [" + std::to_string(user_count) + " " + user_text + " online] Napište zprávu a stiskněte Enter. Použijte /help pro nápovědu.");
        
        // Broadcast o novém připojení
        std::string current_time = get_current_time();
        broadcast_message("[" + current_time + "] Server: " + username + " se připojil k chatu", client_fd);
        
        // Hlavní smyčka pro komunikaci s klientem
        while (true) {
            std::string message = receive_message(client_fd);
            
            if (message.empty()) {
                // Klient se odpojil
                break;
            }
            
            // Zpracování PONG odpovědi na heartbeat
            if (message == "PONG") {
                update_heartbeat(client_fd);
                continue;
            }
            
            // Kontrola rate limitingu (kromě systémových příkazů)
            if (message.length() == 0 || message[0] != '/') {
                if (!check_rate_limit(client_fd)) {
                    send_message(client_fd, "ERROR: Příliš mnoho zpráv! Maximálně " + std::to_string(RATE_LIMIT_MESSAGES) + " zpráv za " + std::to_string(RATE_LIMIT_WINDOW) + " sekund.");
                    std::cout << "Rate limit překročen pro " << username << " (" << client_fd << ")" << std::endl;
                    continue;
                }
            }
            
            // Aktualizace heartbeat při jakékoli aktivitě
            update_heartbeat(client_fd);
            
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
                } else if (message.find("/getpeer ") == 0 && message.length() > 9) {
                    // Získání P2P informací o uživateli
                    std::string target_username = message.substr(9);
                    std::lock_guard<std::mutex> lock(clients_mutex);
                    bool found = false;
                    for (const auto& client : clients) {
                        if (client.username == target_username) {
                            // Získání IP adresy z socketu (zjednodušené - použijeme localhost)
                            send_message(client_fd, "PEER_INFO:" + client.username + ":127.0.0.1:" + std::to_string(client.p2p_port));
                            found = true;
                            break;
                        }
                    }
                    if (!found) {
                        send_message(client_fd, "ERROR: Uživatel '" + target_username + "' není připojen");
                    }
                } else if (message.find("/pm ") == 0) {
                    // Soukromá zpráva přes server
                    size_t pos1 = message.find(" ", 4);
                    size_t pos2 = message.find(" ", pos1 + 1);
                    if (pos1 != std::string::npos && pos2 != std::string::npos) {
                        std::string target_username = message.substr(4, pos1 - 4);
                        std::string pm_message = message.substr(pos2 + 1);
                        std::lock_guard<std::mutex> lock(clients_mutex);
                        bool found = false;
                        for (auto& client : clients) {
                            if (client.username == target_username) {
                                send_message(client.socket, "[PM od " + username + "] " + pm_message);
                                send_message(client_fd, "INFO: Soukromá zpráva odeslána " + target_username);
                                found = true;
                                std::cout << "Soukromá zpráva od " << username << " k " << target_username << ": " << pm_message << std::endl;
                                break;
                            }
                        }
                        if (!found) {
                            send_message(client_fd, "ERROR: Uživatel '" + target_username + "' není připojen");
                        }
                    }
                } else if (message == "/peers") {
                    // Seznam všech uživatelů s P2P informacemi
                    std::lock_guard<std::mutex> lock(clients_mutex);
                    std::string peer_list = "P2P informace:\n";
                    for (const auto& client : clients) {
                        peer_list += client.username + " (127.0.0.1:" + std::to_string(client.p2p_port) + ")\n";
                    }
                    send_message(client_fd, peer_list);
                } else if (message == "/help") {
                    send_message(client_fd, "=== Chat Server - Nápověda ===\nVšechny vaše zprávy se automaticky posílají všem uživatelům v chatu.\n\nDostupné příkazy:\n/quit - Odpojení ze serveru\n/list - Seznam připojených uživatelů\n/pm <uživatel> <zpráva> - Soukromá zpráva přes server\n/getpeer <uživatel> - Získání P2P informací\n/peers - Seznam všech s P2P informacemi\n/help - Zobrazení této nápovědy\n\nPro odeslání zprávy jednoduše napište text a stiskněte Enter.");
                } else {
                    send_message(client_fd, "ERROR: Neznámý příkaz. Použijte /help");
                }
            } else {
                // Chat zpráva - broadcast všem klientům s časovým razítkem
                std::string current_time = get_current_time();
                std::string chat_message = "[" + current_time + "] " + username + ": " + message;
                std::cout << "Chat zpráva od " << username << ": " << message << std::endl;
                broadcast_message(chat_message);
            }
        }
    } catch (...) {
        std::cerr << "Chyba při komunikaci s klientem " << client_fd << std::endl;
    }
    
    // Broadcast o odpojení
    std::string current_time = get_current_time();
    broadcast_message("[" + current_time + "] Server: " + username + " opustil chat");
    
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
    std::cout << "Heartbeat interval: " << HEARTBEAT_INTERVAL << "s, Timeout: " << HEARTBEAT_TIMEOUT << "s" << std::endl;
    std::cout << "Rate limit: " << RATE_LIMIT_MESSAGES << " zpráv za " << RATE_LIMIT_WINDOW << "s" << std::endl;
    std::cout << "Kompatibilní s: Python klienty" << std::endl;
    std::cout << "Stiskněte Ctrl+C pro ukončení" << std::endl;
    std::cout << "========================================" << std::endl;
    
    // Spuštění heartbeat monitor thread
    std::thread heartbeat_thread(heartbeat_monitor);
    heartbeat_thread.detach();
    std::cout << "Heartbeat monitor spuštěn" << std::endl;
    
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
