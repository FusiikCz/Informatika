"""
Peer-to-Peer (P2P) socket implementace v Pythonu
Každý peer může současně fungovat jako server i klient

Vlastnosti:
- Hybridní architektura (server + klient)
- Připojení k jiným peerům
- Přijímání připojení od jiných peerů
- Message protocol s délkou zprávy
- Peer discovery a správa připojení
- Robustní error handling
- Logging systém
- Graceful shutdown
"""

import socket
import threading
import logging
import struct
import time
import sys
from typing import List, Tuple, Optional, Dict
from collections import defaultdict

# Konfigurace
DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 8081  # Jiný port než server, aby mohly běžet současně
BUFFER_SIZE = 4096
MAX_PEERS = 50
CONNECTION_TIMEOUT = 10.0
MESSAGE_TIMEOUT = 60.0
HEARTBEAT_INTERVAL = 30.0

# Nastavení logování
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Globální stav
connected_peers: Dict[Tuple[str, int], Tuple[socket.socket, str, float]] = {}  # address -> (socket, username, last_heartbeat)
peers_lock = threading.Lock()
peer_running = threading.Event()
peer_running.set()
listener_socket: Optional[socket.socket] = None
listener_thread: Optional[threading.Thread] = None
username = "Peer"


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
        return None
    except Exception as e:
        logger.error(f"Chyba při přijímání zprávy: {e}")
        return None


def handle_incoming_peer(peer_socket: socket.socket, peer_address: Tuple[str, int]):
    """
    Obsluha příchozího peera
    
    Args:
        peer_socket: Socket příchozího peera
        peer_address: Adresa peera
    """
    peer_username = f"Peer_{peer_address[1]}"
    
    try:
        peer_socket.settimeout(CONNECTION_TIMEOUT)
        
        # Přijetí uživatelského jména
        welcome_msg = receive_message(peer_socket, timeout=10.0)
        if welcome_msg and welcome_msg.startswith("USERNAME:"):
            peer_username = welcome_msg.split(":", 1)[1].strip()[:20]
            logger.info(f"Peer {peer_address} nastavil jméno: {peer_username}")
        
        # Přidání peera do seznamu
        with peers_lock:
            if len(connected_peers) >= MAX_PEERS:
                send_message(peer_socket, "ERROR: Maximální počet peerů dosažen")
                peer_socket.close()
                return
            
            connected_peers[peer_address] = (peer_socket, peer_username, time.time())
            logger.info(f"Peer připojen: {peer_username} ({peer_address}). Celkem peerů: {len(connected_peers)}")
        
        # Odeslání uvítací zprávy
        send_message(peer_socket, f"Vítejte v P2P síti, {peer_username}! Jste připojeni k {username}.")
        
        # Hlavní smyčka pro komunikaci
        while peer_running.is_set():
            message = receive_message(peer_socket, timeout=HEARTBEAT_INTERVAL)
            
            if not message:
                break
            
            # Aktualizace heartbeat
            with peers_lock:
                if peer_address in connected_peers:
                    sock, uname, _ = connected_peers[peer_address]
                    connected_peers[peer_address] = (sock, uname, time.time())
            
            # Speciální příkazy
            if message.startswith("/"):
                command = message.split()[0] if message.split() else message
                
                if command == "/quit":
                    send_message(peer_socket, "Odpojování...")
                    break
                elif command == "/ping":
                    send_message(peer_socket, "PONG")
                elif command == "/list":
                    with peers_lock:
                        peer_list = ", ".join([f"{u} ({a[0]}:{a[1]})" for a, (_, u, _) in connected_peers.items()])
                    send_message(peer_socket, f"Připojení peery: {peer_list}")
                else:
                    send_message(peer_socket, f"Echo: {message}")
            else:
                # Echo nebo zpracování zprávy
                logger.info(f"Zpráva od {peer_username} ({peer_address}): {message}")
                send_message(peer_socket, f"Echo: {message}")
    
    except Exception as e:
        logger.error(f"Chyba při komunikaci s peerem {peer_address}: {e}", exc_info=True)
    
    finally:
        # Odstranění peera ze seznamu
        with peers_lock:
            if peer_address in connected_peers:
                del connected_peers[peer_address]
                logger.info(f"Peer odpojen: {peer_username} ({peer_address}). Celkem peerů: {len(connected_peers)}")
        
        try:
            peer_socket.close()
        except:
            pass


def listener_thread_func():
    """
    Vlákno pro naslouchání příchozím připojením
    """
    global listener_socket
    
    try:
        listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener_socket.bind((DEFAULT_HOST, DEFAULT_PORT))
        listener_socket.listen(MAX_PEERS)
        
        logger.info(f"P2P listener naslouchá na {DEFAULT_HOST}:{DEFAULT_PORT}")
        
        while peer_running.is_set():
            try:
                listener_socket.settimeout(1.0)  # Krátký timeout pro kontrolu peer_running
                peer_socket, peer_address = listener_socket.accept()
                
                logger.info(f"Nové připojení od peera: {peer_address}")
                
                # Vytvoření vlákna pro obsluhu peera
                thread = threading.Thread(
                    target=handle_incoming_peer,
                    args=(peer_socket, peer_address),
                    daemon=True,
                    name=f"PeerHandler-{peer_address[1]}"
                )
                thread.start()
                
            except socket.timeout:
                continue
            except OSError:
                if peer_running.is_set():
                    logger.error("Chyba při přijímání peera")
                break
            except Exception as e:
                logger.error(f"Neočekávaná chyba v listeneru: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Kritická chyba listeneru: {e}", exc_info=True)


def connect_to_peer(host: str, port: int) -> bool:
    """
    Připojení k jinému peeru
    
    Args:
        host: Hostname nebo IP adresa peera
        port: Port peera
        
    Returns:
        True pokud úspěšné, False jinak
    """
    peer_address = (host, port)
    
    # Kontrola, zda už není připojen
    with peers_lock:
        if peer_address in connected_peers:
            print(f"Již jste připojeni k {host}:{port}")
            return False
    
    try:
        print(f"Připojování k peeru {host}:{port}...")
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.settimeout(CONNECTION_TIMEOUT)
        peer_socket.connect((host, port))
        
        # Odeslání uživatelského jména
        send_message(peer_socket, f"USERNAME:{username}")
        
        # Přijetí uvítací zprávy
        welcome = receive_message(peer_socket, timeout=5.0)
        if welcome:
            print(f"✓ {welcome}")
        
        # Přidání do seznamu
        with peers_lock:
            connected_peers[peer_address] = (peer_socket, f"Peer_{port}", time.time())
            logger.info(f"Připojeno k peeru {host}:{port}. Celkem peerů: {len(connected_peers)}")
        
        # Spuštění vlákna pro přijímání zpráv od tohoto peera
        def receive_from_peer():
            while peer_running.is_set():
                try:
                    message = receive_message(peer_socket, timeout=1.0)
                    if message:
                        print(f"\n[{host}:{port}] {message}")
                        print("> ", end="", flush=True)
                    elif message is None:
                        break
                except:
                    if peer_running.is_set():
                        continue
                    break
            
            # Odstranění při odpojení
            with peers_lock:
                if peer_address in connected_peers:
                    del connected_peers[peer_address]
                    logger.info(f"Odpojeno od peera {host}:{port}")
        
        thread = threading.Thread(target=receive_from_peer, daemon=True)
        thread.start()
        
        return True
    
    except ConnectionRefusedError:
        print(f"Chyba: Nelze se připojit k {host}:{port}. Peer neběží nebo port není otevřený.")
        return False
    except socket.timeout:
        print(f"Chyba: Timeout při připojování k {host}:{port}")
        return False
    except Exception as e:
        print(f"Chyba při připojování: {e}")
        logger.error(f"Chyba při připojování k {host}:{port}: {e}")
        return False


def send_to_peer(peer_address: Tuple[str, int], message: str) -> bool:
    """
    Odeslání zprávy konkrétnímu peeru
    
    Args:
        peer_address: Adresa peera
        message: Zpráva k odeslání
        
    Returns:
        True pokud úspěšné, False jinak
    """
    with peers_lock:
        if peer_address not in connected_peers:
            print(f"Nejste připojeni k {peer_address[0]}:{peer_address[1]}")
            return False
        
        peer_socket, _, _ = connected_peers[peer_address]
    
    return send_message(peer_socket, message)


def broadcast_to_all_peers(message: str) -> int:
    """
    Odeslání zprávy všem připojeným peerům
    
    Args:
        message: Zpráva k odeslání
        
    Returns:
        Počet úspěšně odeslaných zpráv
    """
    sent_count = 0
    disconnected_peers = []
    
    with peers_lock:
        peers_copy = list(connected_peers.items())
    
    for peer_address, (peer_socket, peer_username, _) in peers_copy:
        try:
            if send_message(peer_socket, message):
                sent_count += 1
            else:
                disconnected_peers.append(peer_address)
        except Exception as e:
            logger.error(f"Chyba při broadcastu k {peer_address}: {e}")
            disconnected_peers.append(peer_address)
    
    # Odstranění odpojených peerů
    with peers_lock:
        for peer_address in disconnected_peers:
            if peer_address in connected_peers:
                del connected_peers[peer_address]
    
    return sent_count


def cleanup_disconnected_peers():
    """
    Vyčištění neaktivních peerů (heartbeat check)
    """
    current_time = time.time()
    disconnected = []
    
    with peers_lock:
        for peer_address, (peer_socket, peer_username, last_heartbeat) in list(connected_peers.items()):
            if current_time - last_heartbeat > HEARTBEAT_INTERVAL * 3:
                disconnected.append(peer_address)
        
        for peer_address in disconnected:
            if peer_address in connected_peers:
                sock, _, _ = connected_peers[peer_address]
                try:
                    sock.close()
                except:
                    pass
                del connected_peers[peer_address]
                logger.info(f"Peer {peer_address} odstraněn kvůli neaktivitě")


def main():
    """
    Hlavní funkce P2P aplikace
    """
    global username, listener_thread
    
    logger.info("=" * 60)
    logger.info("Spouštění P2P aplikace")
    logger.info("=" * 60)
    
    # Nastavení uživatelského jména
    username_input = input("Zadejte vaše jméno (nebo Enter pro výchozí): ").strip()
    if username_input:
        username = username_input[:20]
    
    # Spuštění listeneru
    listener_thread = threading.Thread(target=listener_thread_func, daemon=True)
    listener_thread.start()
    
    # Počkat na spuštění listeneru
    time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print("P2P Aplikace")
    print("=" * 60)
    print(f"Vaše jméno: {username}")
    print(f"Nasloucháte na portu: {DEFAULT_PORT}")
    print(f"\nDostupné příkazy:")
    print("  /connect <host> <port>  - Připojení k peeru")
    print("  /list                  - Seznam připojených peerů")
    print("  /send <host> <port> <msg> - Odeslání zprávy konkrétnímu peeru")
    print("  /broadcast <msg>       - Odeslání zprávy všem peerům")
    print("  /disconnect <host> <port> - Odpojení od peera")
    print("  /help                  - Zobrazení nápovědy")
    print("  /quit                  - Ukončení aplikace")
    print("=" * 60 + "\n")
    
    # Vlákno pro cleanup
    def cleanup_thread():
        while peer_running.is_set():
            time.sleep(HEARTBEAT_INTERVAL)
            cleanup_disconnected_peers()
    
    cleanup_thread_obj = threading.Thread(target=cleanup_thread, daemon=True)
    cleanup_thread_obj.start()
    
    # Hlavní smyčka pro uživatelský vstup
    try:
        while peer_running.is_set():
            try:
                command = input("> ").strip()
                
                if not command:
                    continue
                
                parts = command.split()
                cmd = parts[0] if parts else command
                
                if cmd == "/quit" or cmd == "quit":
                    print("Ukončování...")
                    break
                
                elif cmd == "/connect" and len(parts) >= 3:
                    try:
                        host = parts[1]
                        port = int(parts[2])
                        connect_to_peer(host, port)
                    except ValueError:
                        print("Chyba: Neplatný port")
                    except Exception as e:
                        print(f"Chyba: {e}")
                
                elif cmd == "/list":
                    with peers_lock:
                        if connected_peers:
                            print("\nPřipojení peery:")
                            for (host, port), (_, peer_username, last_hb) in connected_peers.items():
                                time_ago = time.time() - last_hb
                                print(f"  - {peer_username} ({host}:{port}) - aktivní před {int(time_ago)}s")
                        else:
                            print("Žádní připojení peery")
                        print()
                
                elif cmd == "/send" and len(parts) >= 4:
                    try:
                        host = parts[1]
                        port = int(parts[2])
                        message = " ".join(parts[3:])
                        if send_to_peer((host, port), message):
                            print(f"Zpráva odeslána k {host}:{port}")
                        else:
                            print(f"Chyba: Nelze odeslat zprávu")
                    except ValueError:
                        print("Chyba: Neplatný port")
                
                elif cmd == "/broadcast" and len(parts) >= 2:
                    message = " ".join(parts[1:])
                    count = broadcast_to_all_peers(message)
                    print(f"Zpráva odeslána {count} peerům")
                
                elif cmd == "/disconnect" and len(parts) >= 3:
                    try:
                        host = parts[1]
                        port = int(parts[2])
                        peer_address = (host, port)
                        with peers_lock:
                            if peer_address in connected_peers:
                                sock, _, _ = connected_peers[peer_address]
                                send_message(sock, "/quit")
                                sock.close()
                                del connected_peers[peer_address]
                                print(f"Odpojeno od {host}:{port}")
                            else:
                                print(f"Nejste připojeni k {host}:{port}")
                    except ValueError:
                        print("Chyba: Neplatný port")
                
                elif cmd == "/help":
                    print("""
Dostupné příkazy:
  /connect <host> <port>     - Připojení k peeru
  /list                      - Seznam připojených peerů
  /send <host> <port> <msg>  - Odeslání zprávy konkrétnímu peeru
  /broadcast <msg>           - Odeslání zprávy všem peerům
  /disconnect <host> <port>  - Odpojení od peera
  /help                      - Zobrazení této nápovědy
  /quit                      - Ukončení aplikace

Příklad použití:
  /connect 127.0.0.1 8081    - Připojení k peeru na localhost:8081
  /send 127.0.0.1 8081 Ahoj  - Odeslání zprávy "Ahoj"
  /broadcast Hello everyone  - Odeslání všem
                    """)
                
                else:
                    # Odeslání zprávy všem peerům (pokud není příkaz)
                    if not command.startswith("/"):
                        count = broadcast_to_all_peers(command)
                        if count > 0:
                            print(f"Zpráva odeslána {count} peerům")
                        else:
                            print("Žádní připojení peery pro odeslání zprávy")
            
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\nUkončování...")
                break
            except Exception as e:
                logger.error(f"Chyba při zpracování příkazu: {e}", exc_info=True)
    
    finally:
        # Graceful shutdown
        peer_running.clear()
        
        # Uzavření všech připojení
        print("\nUzavírání připojení...")
        with peers_lock:
            for peer_address, (peer_socket, _, _) in list(connected_peers.items()):
                try:
                    send_message(peer_socket, "Peer se ukončuje...")
                    peer_socket.close()
                except:
                    pass
            connected_peers.clear()
        
        # Uzavření listeneru
        if listener_socket:
            try:
                listener_socket.close()
            except:
                pass
        
        logger.info("P2P aplikace ukončena")
        print("Aplikace ukončena")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram ukončen uživatelem")
        sys.exit(0)
