"""
Socket klient implementace v Pythonu
"""

import socket


def main():
    """
    Hlavní funkce klienta
    """
    # Vytvoření socketu
    # AF_INET = IPv4, SOCK_STREAM = TCP
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        # Připojení k serveru
        # '127.0.0.1' = localhost, port 8080
        client.connect(('127.0.0.1', 8080))
        
        print("Připojeno k serveru na 127.0.0.1:8080")
        print("Zadejte zprávy (pro ukončení zadejte 'quit'):")
        
        # Hlavní smyčka pro komunikaci
        while True:
            # Čtení zprávy od uživatele
            message = input("> ")
            
            if message.lower() == 'quit':
                break
            
            # Odeslání zprávy serveru
            # encode() převede string na byty
            client.sendall(message.encode('utf-8'))
            
            # Přijetí odpovědi od serveru (max 1024 bytů)
            response = client.recv(1024)
            
            if not response:
                print("Server ukončil spojení")
                break
            
            # Dekódování odpovědi z bytů na string
            print(f"Odpověď serveru: {response.decode('utf-8')}")
            
    except ConnectionRefusedError:
        print("Chyba: Nelze se připojit k serveru. Ujistěte se, že server běží.")
    except Exception as e:
        print(f"Chyba: {e}")
    finally:
        # Uzavření socketu
        client.close()
        print("Odpojeno od serveru")


if __name__ == "__main__":
    main()
