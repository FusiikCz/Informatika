"""
Socket server implementace v Pythonu
Používá thread-per-client architekturu
"""

import socket
import threading

# Seznam všech připojených klientů
clients = []
clients_lock = threading.Lock()  # Zámek pro thread-safe přístup


def handle_client(client_socket, address):
    """
    Funkce pro obsluhu jednoho klienta
    
    Args:
        client_socket: Socket objekt klienta
        address: Tuple (IP adresa, port) klienta
    """
    print(f"Klient připojen: {address}")
    
    # Přidání klienta do seznamu (thread-safe)
    with clients_lock:
        clients.append(client_socket)
        print(f"Celkem klientů: {len(clients)}")
    
    try:
        # Hlavní smyčka pro komunikaci s klientem
        while True:
            # Přijetí zprávy od klienta (max 1024 bytů)
            data = client_socket.recv(1024)
            
            if not data:
                # Klient se odpojil (prázdná zpráva)
                break
            
            # Dekódování zprávy z bytů na string
            message = data.decode('utf-8')
            print(f"Přijato od {address}: {message}")
            
            # Echo - odeslání zprávy zpět klientovi
            response = f"Echo: {message}"
            client_socket.sendall(response.encode('utf-8'))
            
    except Exception as e:
        print(f"Chyba při komunikaci s klientem {address}: {e}")
    
    finally:
        # Odstranění klienta ze seznamu (thread-safe)
        with clients_lock:
            if client_socket in clients:
                clients.remove(client_socket)
            print(f"Klient odpojen: {address}. Celkem klientů: {len(clients)}")
        
        # Uzavření socketu
        client_socket.close()


def main():
    """
    Hlavní funkce serveru
    """
    # Vytvoření socketu
    # AF_INET = IPv4, SOCK_STREAM = TCP
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Nastavení socketu pro opakované použití adresy
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Navázání socketu na adresu a port
    # '0.0.0.0' = přijímat na všech rozhraních, port 8080
    server.bind(('0.0.0.0', 8080))
    
    # Naslouchání příchozím připojením (max 10 čekajících)
    server.listen(10)
    
    print("Server naslouchá na portu 8080...")
    
    # Hlavní smyčka - přijímání nových klientů
    while True:
        try:
            # Přijetí nového klienta
            # accept() vrací tuple (socket, address)
            client, address = server.accept()
            
            # Vytvoření nového vlákna pro obsluhu klienta
            # daemon=True = vlákno se ukončí s hlavním programem
            thread = threading.Thread(
                target=handle_client,
                args=(client, address),
                daemon=True
            )
            thread.start()
            
        except KeyboardInterrupt:
            # Uzavření serveru při Ctrl+C
            print("\nUkončování serveru...")
            break
        except Exception as e:
            print(f"Chyba při přijímání klienta: {e}")
    
    # Uzavření serveru
    server.close()
    print("Server ukončen")


if __name__ == "__main__":
    main()
