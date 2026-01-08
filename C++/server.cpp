#include <iostream>
#include <thread>
#include <vector>
#include <mutex>
#include <algorithm>
#include <cstring>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

// Sdílený seznam socketů pro všechny klienty
std::vector<int> clients;
std::mutex clients_mutex; // Mutex pro synchronizaci přístupu k seznamu klientů

/**
 * Funkce pro obsluhu jednoho klienta
 * @param client_fd Deskriptor socketu klienta
 */
void handle_client(int client_fd) {
    char buffer[1024];
    
    // Přidání klienta do seznamu (thread-safe)
    {
        std::lock_guard<std::mutex> lock(clients_mutex);
        clients.push_back(client_fd);
        std::cout << "Klient připojen. Celkem klientů: " << clients.size() << std::endl;
    }
    
    // Hlavní smyčka pro komunikaci s klientem
    while (true) {
        // Přijetí zprávy od klienta
        ssize_t bytes_received = recv(client_fd, buffer, sizeof(buffer) - 1, 0);
        
        if (bytes_received <= 0) {
            // Klient se odpojil nebo došlo k chybě
            break;
        }
        
        buffer[bytes_received] = '\0';
        std::cout << "Přijato od klienta " << client_fd << ": " << buffer << std::endl;
        
        // Echo - odeslání zprávy zpět klientovi
        std::string response = "Echo: ";
        response += buffer;
        send(client_fd, response.c_str(), response.length(), 0);
    }
    
    // Odstranění klienta ze seznamu (thread-safe)
    {
        std::lock_guard<std::mutex> lock(clients_mutex);
        clients.erase(std::remove(clients.begin(), clients.end(), client_fd), clients.end());
        std::cout << "Klient odpojen. Celkem klientů: " << clients.size() << std::endl;
    }
    
    close(client_fd);
}

/**
 * Hlavní funkce serveru
 */
int main() {
    // Vytvoření socketu
    // AF_INET = IPv4, SOCK_STREAM = TCP, 0 = default protokol
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
    addr.sin_family = AF_INET;           // IPv4
    addr.sin_port = htons(8080);         // Port 8080 (htons = host to network short)
    addr.sin_addr.s_addr = INADDR_ANY;   // Přijímat na všech rozhraních
    
    // Navázání socketu na adresu a port
    if (bind(server_fd, (sockaddr*)&addr, sizeof(addr)) < 0) {
        std::cerr << "Chyba při navázání socketu" << std::endl;
        close(server_fd);
        return 1;
    }
    
    // Naslouchání příchozím připojením (max 10 čekajících)
    if (listen(server_fd, 10) < 0) {
        std::cerr << "Chyba při naslouchání" << std::endl;
        close(server_fd);
        return 1;
    }
    
    std::cout << "Server naslouchá na portu 8080..." << std::endl;
    
    // Hlavní smyčka - přijímání nových klientů
    while (true) {
        // Přijetí nového klienta
        int client = accept(server_fd, nullptr, nullptr);
        
        if (client < 0) {
            std::cerr << "Chyba při přijímání klienta" << std::endl;
            continue;
        }
        
        // Vytvoření nového vlákna pro obsluhu klienta
        // detach() = vlákno běží nezávisle, není potřeba ho join()
        std::thread(handle_client, client).detach();
    }
    
    // Tento kód se nikdy neprovede, ale pro úplnost:
    close(server_fd);
    return 0;
}
