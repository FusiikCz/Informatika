import socket
import threading
import logging
import struct
import time
from datetime import datetime
from typing import List, Tuple, Optional

# Konfigurace
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8080
BUFFER_SIZE = 4096
MAX_CLIENTS = 100
CONNECTION_TIMEOUT = 300.0
MESSAGE_TIMEOUT = 60.0
HEARTBEAT_INTERVAL = 300.0  # Interval pro heartbeat (sekundy)
HEARTBEAT_TIMEOUT = 100.0  # Timeout pro heartbeat odpověď (sekundy)
RATE_LIMIT_MESSAGES = 10  # Maximální počet zpráv
RATE_LIMIT_WINDOW = 1.0  # Časové okno v sekundách

# Nastavení logování
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Paleta barev pro uživatele (ANSI escape kódy)
USER_COLORS = [
    '\033[31m',  # Červená
    '\033[32m',  # Zelená
    '\033[33m',  # Žlutá
    '\033[34m',  # Modrá
    '\033[35m',  # Magenta
    '\033[36m',  # Cyan
    '\033[91m',  # Světle červená
    '\033[92m',  # Světle zelená
    '\033[93m',  # Světle žlutá
    '\033[94m',  # Světle modrá
    '\033[95m',  # Světle magenta
    '\033[96m',  # Světle cyan
]

# Struktura pro uložení informací o klientovi
# (socket, address, username, p2p_port, last_heartbeat, last_message_time, message_count, color_code)
# address je (IP, port) - port, na kterém se klient připojil k serveru
# p2p_port je port, na kterém klient naslouchá pro P2P připojení
# last_heartbeat je čas posledního úspěšného heartbeat
# last_message_time je čas poslední zprávy pro rate limiting
# message_count je počet zpráv v aktuálním okně
# color_code je ANSI escape kód pro barvu uživatele
clients: List[Tuple[socket.socket, Tuple[str, int], str, int, float, float, int, str]] = []  # (socket, address, username, p2p_port, last_heartbeat, last_message_time, message_count, color_code)
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


def get_user_color(client_index: int) -> str:
    """
    Získá barvu pro uživatele na základě indexu (cyklicky)
    
    Args:
        client_index: Index klienta v seznamu
        
    Returns:
        ANSI escape kód pro barvu
    """
    return USER_COLORS[client_index % len(USER_COLORS)]


def check_rate_limit(client_socket: socket.socket) -> bool:
    """
    Kontrola rate limitingu pro klienta
    
    Args:
        client_socket: Socket klienta
        
    Returns:
        True pokud je zpráva povolena, False pokud je rate limit překročen
    """
    current_time = time.time()
    with clients_lock:
        for i, (sock, addr, uname, p2p_port, last_hb, last_msg_time, msg_count, color) in enumerate(clients):
            if sock == client_socket:
                # Kontrola, zda uplynulo dost času pro reset okna
                if current_time - last_msg_time >= RATE_LIMIT_WINDOW:
                    # Reset okna
                    clients[i] = (sock, addr, uname, p2p_port, last_hb, current_time, 1, color)
                    return True
                elif msg_count < RATE_LIMIT_MESSAGES:
                    # Zvýšení počtu zpráv
                    clients[i] = (sock, addr, uname, p2p_port, last_hb, last_msg_time, msg_count + 1, color)
                    return True
                else:
                    # Rate limit překročen
                    return False
    return True


def update_heartbeat(client_socket: socket.socket):
    """
    Aktualizace času posledního heartbeat pro klienta
    
    Args:
        client_socket: Socket klienta
    """
    current_time = time.time()
    with clients_lock:
        for i, (sock, addr, uname, p2p_port, last_hb, last_msg_time, msg_count, color) in enumerate(clients):
            if sock == client_socket:
                clients[i] = (sock, addr, uname, p2p_port, current_time, last_msg_time, msg_count, color)
                break


def heartbeat_monitor():
    """
    Vlákno pro monitoring heartbeat - kontroluje připojení klientů
    """
    while server_running.is_set():
        time.sleep(HEARTBEAT_INTERVAL)
        current_time = time.time()
        disconnected = []
        
        with clients_lock:
            for client_sock, address, username, p2p_port, last_heartbeat, last_msg_time, msg_count, color in clients:
                # Kontrola, zda klient neodpovídá příliš dlouho
                if current_time - last_heartbeat > HEARTBEAT_TIMEOUT * 2:
                    logger.warning(f"Klient {username} ({address}) neodpovídá na heartbeat - odpojování")
                    disconnected.append((client_sock, address, username, p2p_port, last_heartbeat, last_msg_time, msg_count, color))
                else:
                    # Odeslání ping zprávy
                    try:
                        send_message(client_sock, "PING")
                    except Exception as e:
                        logger.warning(f"Nelze odeslat ping klientovi {username} ({address}): {e}")
                        disconnected.append((client_sock, address, username, p2p_port, last_heartbeat, last_msg_time, msg_count, color))
        
        # Odstranění odpojených klientů
        if disconnected:
            with clients_lock:
                for client_info in disconnected:
                    if client_info in clients:
                        clients.remove(client_info)
                        try:
                            client_info[0].close()
                        except:
                            pass
                        logger.info(f"Klient {client_info[2]} odpojen kvůli timeoutu heartbeat")


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
        for client_sock, address, username, p2p_port, last_heartbeat, last_msg_time, msg_count, color in clients:
            if exclude_socket and client_sock == exclude_socket:
                continue
            
            try:
                if send_message(client_sock, message):
                    sent_count += 1
                else:
                    disconnected_clients.append((client_sock, address, username, p2p_port, last_heartbeat, last_msg_time, msg_count, color))
            except Exception as e:
                logger.error(f"Chyba při broadcastu klientovi {address}: {e}")
                disconnected_clients.append((client_sock, address, username, p2p_port, last_heartbeat, last_msg_time, msg_count, color))
        
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
    p2p_port = 8081  # Výchozí P2P port
    logger.info(f"Klient připojen: {address}")
    
    try:
        # Nastavení timeoutu pro připojení
        client_socket.settimeout(CONNECTION_TIMEOUT)
        
        # Přijetí uživatelského jména a P2P portu (volitelné)
        welcome_msg = receive_message(client_socket, timeout=10.0)
        if welcome_msg:
            if welcome_msg.startswith("USERNAME:"):
                parts = welcome_msg.split(":", 1)
                username = parts[1].strip()[:20]  # Max 20 znaků
                logger.info(f"Klient {address} nastavil jméno: {username}")
            elif welcome_msg.startswith("SETUP:"):
                # Formát: SETUP:username:p2p_port
                parts = welcome_msg.split(":")
                if len(parts) >= 2:
                    username = parts[1].strip()[:20]
                if len(parts) >= 3:
                    try:
                        p2p_port = int(parts[2].strip())
                    except ValueError:
                        p2p_port = 8081
                logger.info(f"Klient {address} nastavil jméno: {username}, P2P port: {p2p_port}")
        
        # Přidání klienta do seznamu (thread-safe)
        current_time = time.time()
        with clients_lock:
            if len(clients) >= MAX_CLIENTS:
                send_message(client_socket, "ERROR: Server je plný")
                client_socket.close()
                return
            
            # Přiřazení barvy uživateli (cyklicky z palety)
            user_color = get_user_color(len(clients))
            color_code = user_color.replace('\033[', '').replace('m', '')  # Extrahujeme číslo barvy
            
            # Přidání s heartbeat, rate limiting a barvou
            clients.append((client_socket, address, username, p2p_port, current_time, current_time, 0, color_code))
            logger.info(f"Celkem klientů: {len(clients)}, barva pro {username}: {color_code}")
        
        # Získání počtu připojených uživatelů
        with clients_lock:
            user_count = len(clients)
        
        # Odeslání uvítací zprávy s počtem uživatelů
        send_message(client_socket, f"Vítejte v chatu, {username}! [{user_count} uživatel{'é' if user_count > 1 else ''} online] Napište zprávu a stiskněte Enter. Použijte /help pro nápovědu.")
        
        # Broadcast o novém připojení všem ostatním klientům
        current_time = datetime.now().strftime("%H:%M")
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
            
            # Zpracování PONG odpovědi na heartbeat (před ostatními kontrolami)
            if message == "PONG":
                update_heartbeat(client_socket)
                continue
            
            # Kontrola rate limitingu (kromě systémových příkazů)
            if not message.startswith("/"):
                if not check_rate_limit(client_socket):
                    send_message(client_socket, f"ERROR: Příliš mnoho zpráv! Maximálně {RATE_LIMIT_MESSAGES} zpráv za {RATE_LIMIT_WINDOW} sekund.")
                    logger.warning(f"Rate limit překročen pro {username} ({address})")
                    continue
            
            # Aktualizace heartbeat při jakékoli aktivitě
            update_heartbeat(client_socket)
            
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
                        user_list = ", ".join([u for _, _, u, _, _, _, _, _ in clients])
                    send_message(client_socket, f"Připojení uživatelé: {user_list}")
                elif command == "/getpeer" and len(message.split()) >= 2:
                    # Získání P2P informací o uživateli
                    target_username = message.split()[1]
                    with clients_lock:
                        found = False
                        for sock, (ip, port), uname, peer_port, _, _, _, _ in clients:
                            if uname.lower() == target_username.lower():
                                send_message(client_socket, f"PEER_INFO:{uname}:{ip}:{peer_port}")
                                found = True
                                break
                        if not found:
                            send_message(client_socket, f"ERROR: Uživatel '{target_username}' není připojen")
                elif command == "/pm" and len(message.split()) >= 3:
                    # Soukromá zpráva přes server (fallback, pokud P2P nefunguje)
                    parts = message.split(" ", 2)
                    target_username = parts[1]
                    pm_message = parts[2] if len(parts) > 2 else ""
                    
                    with clients_lock:
                        found = False
                        for sock, addr, uname, _, _, _, _, _ in clients:
                            if uname.lower() == target_username.lower():
                                send_message(sock, f"[PM od {username}] {pm_message}")
                                send_message(client_socket, f"INFO: Soukromá zpráva odeslána {uname}")
                                found = True
                                logger.info(f"Soukromá zpráva od {username} k {uname}: {pm_message}")
                                break
                        if not found:
                            send_message(client_socket, f"ERROR: Uživatel '{target_username}' není připojen")
                elif command == "/peers":
                    # Seznam všech uživatelů s jejich P2P informacemi
                    with clients_lock:
                        peer_list = []
                        for sock, (ip, port), uname, peer_port, _, _, _, _ in clients:
                            peer_list.append(f"{uname} ({ip}:{peer_port})")
                        send_message(client_socket, f"P2P informace:\n" + "\n".join(peer_list))
                elif command == "/broadcast" and len(message.split()) > 1:
                    # /broadcast je nyní zbytečný, protože všechny zprávy se automaticky broadcastují
                    send_message(client_socket, "INFO: Všechny zprávy se automaticky posílají všem uživatelům. Stačí napsat zprávu.")
                elif command == "/help":
                    help_text = """=== Chat Server - Nápověda ===
Všechny vaše zprávy se automaticky posílají všem uživatelům v chatu.

Dostupné příkazy:
/quit - Odpojení ze serveru
/list - Seznam připojených uživatelů
/pm <uživatel> <zpráva> - Soukromá zpráva přes server
/getpeer <uživatel> - Získání P2P informací (IP:port) o uživateli
/peers - Seznam všech uživatelů s P2P informacemi
/help - Zobrazení této nápovědy

Pro soukromé zprávy:
1. Použijte /getpeer <uživatel> pro získání P2P informací
2. Spusťte P2P aplikaci a připojte se přímo k uživateli
3. Nebo použijte /pm <uživatel> <zpráva> pro soukromou zprávu přes server

Pro odeslání zprávy jednoduše napište text a stiskněte Enter."""
                    send_message(client_socket, help_text)
                else:
                    send_message(client_socket, f"ERROR: Neznámý příkaz. Použijte /help")
            else:
                # Chat zpráva - broadcast všem klientům (včetně odesílatele, aby viděl svou zprávu)
                current_time = datetime.now().strftime("%H:%M")
                
                # Získání barvy uživatele
                user_color_code = "37"  # Výchozí bílá
                with clients_lock:
                    for sock, _, uname, _, _, _, _, color in clients:
                        if sock == client_socket:
                            user_color_code = color
                            break
                
                # Přidání informace o barvě do zprávy
                chat_message = f"[COLOR:{user_color_code}][{current_time}] {username}: {message}"
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
            current_time = datetime.now().strftime("%H:%M")
            broadcast_message(f"[{current_time}] Server: {username} opustil chat")
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
        logger.info(f"Heartbeat interval: {HEARTBEAT_INTERVAL}s, Timeout: {HEARTBEAT_TIMEOUT}s")
        logger.info(f"Rate limit: {RATE_LIMIT_MESSAGES} zpráv za {RATE_LIMIT_WINDOW}s")
        logger.info("Stiskněte Ctrl+C pro ukončení")
        
        # Spuštění heartbeat monitor thread
        heartbeat_thread = threading.Thread(
            target=heartbeat_monitor,
            daemon=True,
            name="HeartbeatMonitor"
        )
        heartbeat_thread.start()
        logger.info("Heartbeat monitor spuštěn")
        
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
            for client_sock, address, username, p2p_port, _, _, _ in clients[:]:
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
