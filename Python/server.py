import socket
import threading
import logging
import struct
import time
from typing import List, Tuple, Optional

# Konfigurace
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
BUFFER_SIZE = 4096
MAX_CLIENTS = 100
CONNECTION_TIMEOUT = 30.0
MESSAGE_TIMEOUT = 60.0

# Nastavení logování
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Seznam všech připojených klientů
clients: List[Tuple[socket.socket, Tuple[str, int], str]] = []  # (socket, address, username)
clients_lock = threading.Lock()  # Zámek pro thread-safe přístup
server_running = threading.Event()
server_running.set()


def send_message(sock: socket.socket, message: str) -> bool:
    """
    Odešle zprávu s prefixem délky pro spolehlivou komunikaci
    
    Args:
        sock: Socket pro odeslání
        message: Zpráva k odeslání
        
    Returns:
        True pokud úspěšné, False jinak
    """
    try:
        message_bytes = message.encode('utf-8')
        message_length = len(message_bytes)
        
        # Odeslání délky zprávy (4 byty, big-endian)
        length_prefix = struct.pack('>I', message_length)
        sock.sendall(length_prefix)
        
        # Odeslání samotné zprávy
        sock.sendall(message_bytes)
        return True
    except Exception as e:
        logger.error(f"Chyba při odesílání zprávy: {e}")
        return False


def receive_message(sock: socket.socket, timeout: float = MESSAGE_TIMEOUT) -> Optional[str]:
    """
    Přijme zprávu s prefixem délky
    
    Args:
        sock: Socket pro přijetí
        timeout: Timeout v sekundách
        
    Returns:
        Přijatá zpráva nebo None při chybě
    """
    try:
        sock.settimeout(timeout)
        
        # Přijetí délky zprávy (4 byty)
        length_data = b''
        while len(length_data) < 4:
            chunk = sock.recv(4 - len(length_data))
            if not chunk:
                return None
            length_data += chunk
        
        message_length = struct.unpack('>I', length_data)[0]
        
        # Validace délky zprávy
        if message_length > BUFFER_SIZE * 10:  # Max 40KB zpráva
            logger.warning(f"Příliš dlouhá zpráva: {message_length} bytů")
            return None
        
        # Přijetí samotné zprávy
        message_data = b''
        while len(message_data) < message_length:
            chunk = sock.recv(min(message_length - len(message_data), BUFFER_SIZE))
            if not chunk:
                return None
            message_data += chunk
        
        return message_data.decode('utf-8')
    
    except socket.timeout:
        # Timeout je normální při čekání na zprávy
        return None
    except Exception as e:
        logger.error(f"Chyba při přijímání zprávy: {e}")
        return None


def broadcast_message(message: str, exclude_socket: Optional[socket.socket] = None) -> int:
    """
    Odešle zprávu všem připojeným klientům
    
    Args:
        message: Zpráva k odeslání
        exclude_socket: Socket, který má být vynechán (např. odesílatel)
        
    Returns:
        Počet úspěšně odeslaných zpráv
    """
    sent_count = 0
    disconnected_clients = []
    
    with clients_lock:
        for client_sock, address, username in clients:
            if exclude_socket and client_sock == exclude_socket:
                continue
            
            try:
                if send_message(client_sock, message):
                    sent_count += 1
                else:
                    disconnected_clients.append((client_sock, address, username))
            except Exception as e:
                logger.error(f"Chyba při broadcastu klientovi {address}: {e}")
                disconnected_clients.append((client_sock, address, username))
        
        # Odstranění odpojených klientů
        for client_info in disconnected_clients:
            if client_info in clients:
                clients.remove(client_info)
                logger.info(f"Klient {client_info[1]} odstraněn z broadcastu")
    
    return sent_count


def handle_client(client_socket: socket.socket, address: Tuple[str, int]):
    """
    Funkce pro obsluhu jednoho klienta
    
    Args:
        client_socket: Socket objekt klienta
        address: Tuple (IP adresa, port) klienta
    """
    username = f"User_{address[1]}"
    logger.info(f"Klient připojen: {address}")
    
    try:
        # Nastavení timeoutu pro připojení
        client_socket.settimeout(CONNECTION_TIMEOUT)
        
        # Přijetí uživatelského jména (volitelné)
        welcome_msg = receive_message(client_socket, timeout=10.0)
        if welcome_msg and welcome_msg.startswith("USERNAME:"):
            username = welcome_msg.split(":", 1)[1].strip()[:20]  # Max 20 znaků
            logger.info(f"Klient {address} nastavil jméno: {username}")
        
        # Přidání klienta do seznamu (thread-safe)
        with clients_lock:
            if len(clients) >= MAX_CLIENTS:
                send_message(client_socket, "ERROR: Server je plný")
                client_socket.close()
                return
            
            clients.append((client_socket, address, username))
            logger.info(f"Celkem klientů: {len(clients)}")
        
        # Odeslání uvítací zprávy
        send_message(client_socket, f"Vítejte v chatu, {username}! Napište zprávu a stiskněte Enter. Použijte /help pro nápovědu.")
        
        # Broadcast o novém připojení všem ostatním klientům
        broadcast_message(f"Server: {username} se připojil k chatu", exclude_socket=client_socket)
        
        # Hlavní smyčka pro komunikaci s klientem
        while server_running.is_set():
            message = receive_message(client_socket)
            
            if not message:
                # Klient se odpojil
                break
            
            # Validace zprávy
            if len(message.strip()) == 0:
                continue
            
            logger.info(f"Přijato od {username} ({address}): {message}")
            
            # Speciální příkazy
            if message.startswith("/"):
                command = message.split()[0] if message.split() else message
                
                if command == "/quit":
                    try:
                        send_message(client_socket, "Odpojování...")
                    except (ConnectionResetError, ConnectionAbortedError, OSError):
                        # Klient už ukončil spojení - to je v pořádku
                        pass
                    break
                elif command == "/list":
                    with clients_lock:
                        user_list = ", ".join([u for _, _, u in clients])
                    send_message(client_socket, f"Připojení uživatelé: {user_list}")
                elif command == "/broadcast" and len(message.split()) > 1:
                    # /broadcast je nyní zbytečný, protože všechny zprávy se automaticky broadcastují
                    send_message(client_socket, "INFO: Všechny zprávy se automaticky posílají všem uživatelům. Stačí napsat zprávu.")
                elif command == "/help":
                    help_text = """=== Chat Server - Nápověda ===
Všechny vaše zprávy se automaticky posílají všem uživatelům v chatu.

Dostupné příkazy:
/quit - Odpojení ze serveru
/list - Seznam připojených uživatelů
/help - Zobrazení této nápovědy

Pro odeslání zprávy jednoduše napište text a stiskněte Enter."""
                    send_message(client_socket, help_text)
                else:
                    send_message(client_socket, f"ERROR: Neznámý příkaz. Použijte /help")
            else:
                # Chat zpráva - broadcast všem klientům (včetně odesílatele, aby viděl svou zprávu)
                chat_message = f"{username}: {message}"
                logger.info(f"Chat zpráva od {username}: {message}")
                
                # Broadcast všem klientům (včetně odesílatele)
                try:
                    broadcast_message(chat_message)  # Bez exclude_socket, takže všichni včetně odesílatele dostanou zprávu
                except Exception as e:
                    logger.error(f"Chyba při broadcastu: {e}")
    
    except socket.timeout:
        logger.warning(f"Timeout pro klienta {address}")
    except (ConnectionResetError, ConnectionAbortedError, OSError) as e:
        # Klient ukončil spojení - to je normální
        logger.info(f"Klient {address} ukončil spojení: {e}")
    except Exception as e:
        logger.error(f"Chyba při komunikaci s klientem {address}: {e}", exc_info=True)
    
    finally:
        # Odstranění klienta ze seznamu (thread-safe)
        with clients_lock:
            clients_to_remove = [c for c in clients if c[0] == client_socket]
            for client_info in clients_to_remove:
                clients.remove(client_info)
                logger.info(f"Klient odpojen: {client_info[2]} ({address}). Celkem klientů: {len(clients)}")
        
        # Broadcast o odpojení všem ostatním klientům
        try:
            broadcast_message(f"Server: {username} opustil chat")
        except:
            pass
        
        # Uzavření socketu
        try:
            client_socket.close()
        except:
            pass


def main():
    """
    Hlavní funkce serveru
    """
    global server_running
    
    logger.info("=" * 50)
    logger.info("Spouštění Chat Serveru")
    logger.info("=" * 50)
    
    server = None
    try:
        # Vytvoření socketu
        # AF_INET = IPv4, SOCK_STREAM = TCP
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Nastavení socketu pro opakované použití adresy
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        # Navázání socketu na adresu a port
        server.bind((DEFAULT_HOST, DEFAULT_PORT))
        
        # Naslouchání příchozím připojením
        server.listen(MAX_CLIENTS)
        
        logger.info(f"Server naslouchá na {DEFAULT_HOST}:{DEFAULT_PORT}")
        logger.info(f"Maximální počet klientů: {MAX_CLIENTS}")
        logger.info("Stiskněte Ctrl+C pro ukončení")
        
        # Hlavní smyčka - přijímání nových klientů
        while server_running.is_set():
            try:
                # Přijetí nového klienta
                client, address = server.accept()
                
                logger.info(f"Nové připojení z {address}")
                
                # Vytvoření nového vlákna pro obsluhu klienta
                # daemon=True = vlákno se ukončí s hlavním programem
                thread = threading.Thread(
                    target=handle_client,
                    args=(client, address),
                    daemon=True,
                    name=f"ClientHandler-{address[1]}"
                )
                thread.start()
                
            except OSError as e:
                if server_running.is_set():
                    logger.error(f"Chyba při přijímání klienta: {e}")
                break
            except Exception as e:
                logger.error(f"Neočekávaná chyba: {e}", exc_info=True)
    
    except KeyboardInterrupt:
        logger.info("\nUkončování serveru...")
    except Exception as e:
        logger.error(f"Kritická chyba serveru: {e}", exc_info=True)
    finally:
        # Graceful shutdown
        server_running.clear()
        
        # Uzavření všech připojení
        logger.info("Uzavírání připojení klientů...")
        with clients_lock:
            for client_sock, address, username in clients[:]:
                try:
                    send_message(client_sock, "Server se ukončuje...")
                    client_sock.close()
                except:
                    pass
            clients.clear()
        
        # Uzavření serveru
        if server:
            try:
                server.close()
            except:
                pass
        
        logger.info("Server ukončen")


if __name__ == "__main__":
    main()
