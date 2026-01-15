/**
 * Rozšířená socket klient implementace v C++
 * Používá length-prefixed protokol (kompatibilní s Python servery)
 * 
 * Kompilace:
 *   g++ -std=c++11 client.cpp -o client
 */

#include <iostream>
#include <string>
#include <cstring>
#include <cstdint>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

// ANSI escape kódy pro barvy
namespace Colors {
    const char* RESET = "\033[0m";
    const char* BOLD = "\033[1m";
    // Barvy textu
    const char* RED = "\033[31m";
    const char* GREEN = "\033[32m";
    const char* YELLOW = "\033[33m";
    const char* BLUE = "\033[34m";
    const char* MAGENTA = "\033[35m";
    const char* CYAN = "\033[36m";
    const char* WHITE = "\033[37m";
    // Světlé barvy
    const char* BRIGHT_BLUE = "\033[94m";
    const char* BRIGHT_GREEN = "\033[92m";
    const char* BRIGHT_YELLOW = "\033[93m";
}

// Konfigurace
const char* HOST = "127.0.0.1";
const int PORT = 8080;

/**
 * Odešle zprávu s prefixem délky (kompatibilní s Python servery)
 */
bool send_message(int sock, const std::string& message) {
    uint32_t message_length = htonl(static_cast<uint32_t>(message.length()));
    
    ssize_t sent = send(sock, &message_length, 4, 0);
    if (sent != 4) {
        std::cerr << "Chyba při odesílání délky zprávy" << std::endl;
        return false;
    }
    
    if (message.length() > 0) {
        sent = send(sock, message.c_str(), message.length(), 0);
        if (sent != static_cast<ssize_t>(message.length())) {
            std::cerr << "Chyba při odesílání zprávy" << std::endl;
            return false;
        }
    }
    
    return true;
}

/**
 * Přijme zprávu s prefixem délky (kompatibilní s Python servery)
 */
std::string receive_message(int sock) {
    uint32_t message_length_net;
    ssize_t received = recv(sock, &message_length_net, 4, MSG_WAITALL);
    
    if (received != 4) {
        if (received == 0) {
            return ""; // Spojení ukončeno
        }
        return "";
    }
    
    uint32_t message_length = ntohl(message_length_net);
    
    if (message_length > 40960) {
        std::cerr << "Chyba: Příliš dlouhá zpráva" << std::endl;
        return "";
    }
    
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
 * Hlavní funkce klienta
 */
int main() {
    // Vytvoření socketu
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    
    if (sock < 0) {
        std::cerr << "Chyba při vytváření socketu" << std::endl;
        return 1;
    }
    
    // Konfigurace adresy serveru
    sockaddr_in server_addr{};
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(PORT);
    
    if (inet_pton(AF_INET, HOST, &server_addr.sin_addr) <= 0) {
        std::cerr << "Chyba při převodu IP adresy" << std::endl;
        close(sock);
        return 1;
    }
    
    // Připojení k serveru
    std::cout << "Připojování k serveru na " << HOST << ":" << PORT << "..." << std::endl;
    if (connect(sock, (sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        std::cerr << "Chyba při připojování k serveru. Ujistěte se, že server běží." << std::endl;
        close(sock);
        return 1;
    }
    
    std::cout << "✓ Připojeno k serveru na " << HOST << ":" << PORT << std::endl;
    
    // Přijetí uvítací zprávy
    std::string welcome = receive_message(sock);
    if (!welcome.empty()) {
        std::cout << welcome << std::endl;
    }
    
    // Volitelné: Odeslání uživatelského jména a P2P portu
    std::string username;
    std::cout << "Zadejte vaše jméno (nebo Enter pro výchozí): ";
    std::getline(std::cin, username);
    if (username.empty()) {
        username = "Guest";
    }
    
    std::string p2p_port_str;
    std::cout << "Zadejte P2P port pro soukromé zprávy (nebo Enter pro výchozí 8081): ";
    std::getline(std::cin, p2p_port_str);
    int p2p_port = 8081;
    if (!p2p_port_str.empty()) {
        try {
            p2p_port = std::stoi(p2p_port_str);
        } catch (...) {
            p2p_port = 8081;
            std::cout << "Neplatný port, použiji výchozí " << p2p_port << std::endl;
        }
    }
    
    // Odeslání informací serveru
    send_message(sock, "SETUP:" + username + ":" + std::to_string(p2p_port));
    
    std::cout << "\n=== Chat připojen ===" << std::endl;
    std::cout << "Napište zprávu a stiskněte Enter pro odeslání všem uživatelům" << std::endl;
    std::cout << "Použijte '/help' pro nápovědu, '/quit' pro odpojení\n" << std::endl;
    
    // Hlavní smyčka pro komunikaci
    std::string message;
    while (true) {
        std::cout << "> ";
        std::getline(std::cin, message);
        
        if (message.empty()) {
            continue;
        }
        
        if (message == "quit" || message == "/quit" || message == "exit" || message == "/exit") {
            send_message(sock, "/quit");
            break;
        } else if (message.find("/getpeer ") == 0 || message.find("/pm ") == 0 || message == "/peers") {
            // P2P příkazy
            send_message(sock, message);
        } else {
            // Odeslání zprávy serveru
            if (!send_message(sock, message)) {
                std::cerr << "Chyba při odesílání zprávy" << std::endl;
                break;
            }
        }
        
        // V chat módu zprávy přicházejí asynchronně
        // Pro jednoduchost čekáme na odpověď, ale v produkci by bylo lepší použít thread
        std::string response = receive_message(sock);
        
        if (response.empty()) {
            std::cerr << "Server ukončil spojení" << std::endl;
            break;
        }
        
        // Zpracování heartbeat ping
        if (response == "PING") {
            // Odpověď na ping
            send_message(sock, "PONG");
            continue;
        }
        
        // Rozlišení mezi systémovými zprávami a chat zprávami s barvami
        if (response.find("PEER_INFO:") == 0) {
            // P2P informace (cyan)
            size_t pos1 = response.find(":", 10);
            size_t pos2 = response.find(":", pos1 + 1);
            size_t pos3 = response.find(":", pos2 + 1);
            if (pos1 != std::string::npos && pos2 != std::string::npos && pos3 != std::string::npos) {
                std::string peer_username = response.substr(10, pos1 - 10);
                std::string peer_ip = response.substr(pos1 + 1, pos2 - pos1 - 1);
                std::string peer_port = response.substr(pos2 + 1, pos3 - pos2 - 1);
                std::cout << "\n" << Colors::CYAN << "[INFO] P2P informace o " << peer_username << ":" << Colors::RESET << std::endl;
                std::cout << "  IP: " << peer_ip << std::endl;
                std::cout << "  Port: " << peer_port << std::endl;
                std::cout << "  Pro připojení použijte P2P aplikaci:" << std::endl;
                std::cout << "    cd P2P/C++" << std::endl;
                std::cout << "    ./peer2peer" << std::endl;
                std::cout << "    /connect " << peer_ip << " " << peer_port << std::endl;
            }
        } else if (response.find("[PM od") == 0) {
            // Soukromá zpráva přes server (magenta)
            std::cout << "\n" << Colors::MAGENTA << response << Colors::RESET << std::endl;
        } else if (response.find("Server:") == 0) {
            // Systémové zprávy (modře)
            std::cout << "\n" << Colors::BRIGHT_BLUE << "[SYSTEM] " << response << Colors::RESET << std::endl;
        } else if (response.find("P2P informace:") == 0) {
            // Seznam P2P informací (cyan)
            std::cout << "\n" << Colors::CYAN << response << Colors::RESET << std::endl;
        } else if (response.find("[") == 0 && response.find(":") != std::string::npos && 
                   response.find("ERROR") == std::string::npos && 
                   response.find("INFO") == std::string::npos) {
            // Chat zpráva od uživatele s časovým razítkem (zeleně)
            std::cout << "\n" << Colors::BRIGHT_GREEN << response << Colors::RESET << std::endl;
        } else if (response.find(":") != std::string::npos && 
                   response.find("ERROR") == std::string::npos && 
                   response.find("INFO") == std::string::npos) {
            // Chat zpráva od uživatele bez časového razítka (zeleně)
            std::cout << "\n" << Colors::BRIGHT_GREEN << response << Colors::RESET << std::endl;
        } else if (response.find("ERROR") == 0) {
            // Chyby (červeně)
            std::cout << "\n" << Colors::RED << response << Colors::RESET << std::endl;
        } else if (response.find("INFO") == 0) {
            // Info zprávy (žlutě)
            std::cout << "\n" << Colors::BRIGHT_YELLOW << response << Colors::RESET << std::endl;
        } else {
            // Jiné zprávy (bíle)
            std::cout << "\n" << Colors::WHITE << "[Server] " << response << Colors::RESET << std::endl;
        }
    }
    
    close(sock);
    std::cout << "Odpojeno od serveru" << std::endl;
    return 0;
}
