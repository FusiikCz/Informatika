#include <iostream>
#include <string>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

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
    server_addr.sin_port = htons(8080);
    
    // Převod IP adresy z textového formátu
    if (inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr) <= 0) {
        std::cerr << "Chyba při převodu IP adresy" << std::endl;
        close(sock);
        return 1;
    }
    
    // Připojení k serveru
    if (connect(sock, (sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        std::cerr << "Chyba při připojování k serveru" << std::endl;
        close(sock);
        return 1;
    }
    
    std::cout << "Připojeno k serveru na 127.0.0.1:8080" << std::endl;
    std::cout << "Zadejte zprávy (pro ukončení zadejte 'quit'):" << std::endl;
    
    char buffer[1024];
    std::string message;
    
    // Hlavní smyčka pro komunikaci
    while (true) {
        // Čtení zprávy od uživatele
        std::cout << "> ";
        std::getline(std::cin, message);
        
        if (message == "quit") {
            break;
        }
        
        // Odeslání zprávy serveru
        send(sock, message.c_str(), message.length(), 0);
        
        // Přijetí odpovědi od serveru
        ssize_t bytes_received = recv(sock, buffer, sizeof(buffer) - 1, 0);
        
        if (bytes_received <= 0) {
            std::cerr << "Server ukončil spojení" << std::endl;
            break;
        }
        
        buffer[bytes_received] = '\0';
        std::cout << "Odpověď serveru: " << buffer << std::endl;
    }
    
    close(sock);
    std::cout << "Odpojeno od serveru" << std::endl;
    return 0;
}
