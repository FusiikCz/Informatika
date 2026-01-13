/**
 * Rozšířená socket klient implementace v C++
 * Používá length-prefixed protokol (kompatibilní s Python/Java/C# servery)
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

// Konfigurace
const char* HOST = "127.0.0.1";
const int PORT = 8080;

/**
 * Odešle zprávu s prefixem délky (kompatibilní s Python/Java/C# servery)
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
 * Přijme zprávu s prefixem délky (kompatibilní s Python/Java/C# servery)
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
    
    // Volitelné: Odeslání uživatelského jména
    std::string username;
    std::cout << "Zadejte vaše jméno (nebo Enter pro výchozí): ";
    std::getline(std::cin, username);
    
    if (!username.empty()) {
        send_message(sock, "USERNAME:" + username);
    } else {
        send_message(sock, "USERNAME:Guest");
    }
    
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
        }
        
        if (!send_message(sock, message)) {
            std::cerr << "Chyba při odesílání zprávy" << std::endl;
            break;
        }
        
        // V chat módu zprávy přicházejí asynchronně
        // Pro jednoduchost čekáme na odpověď, ale v produkci by bylo lepší použít thread
        std::string response = receive_message(sock);
        
        if (response.empty()) {
            std::cerr << "Server ukončil spojení" << std::endl;
            break;
        }
        
        // Rozlišení mezi systémovými zprávami a chat zprávami
        if (response.find("Server:") == 0) {
            std::cout << "[SYSTEM] " << response << std::endl;
        } else if (response.find(":") != std::string::npos && 
                   response.find("ERROR") == std::string::npos && 
                   response.find("INFO") == std::string::npos) {
            // Chat zpráva od uživatele
            std::cout << response << std::endl;
        } else {
            // Jiné zprávy
            std::cout << "[Server] " << response << std::endl;
        }
    }
    
    close(sock);
    std::cout << "Odpojeno od serveru" << std::endl;
    return 0;
}
