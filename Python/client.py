
import socket
import struct
import logging
import sys
import threading
import time
import re
from typing import Optional

# ANSI escape kódy pro barvy
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    # Barvy textu
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    # Světlé barvy
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'

# Konfigurace
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8080
CONNECTION_TIMEOUT = 10.0
MESSAGE_TIMEOUT = 60.0
BUFFER_SIZE = 4096

# Nastavení logování
logging.basicConfig(
    level=logging.INFO,  # Stejné jako server pro konzistenci
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


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
        # Timeout je normální při čekání na zprávy - nepotřebujeme warning
        return None
    except Exception as e:
        logger.error(f"Chyba při přijímání zprávy: {e}")
        return None


def receive_messages_thread(sock: socket.socket, running: threading.Event):
    """
    Vlákno pro přijímání zpráv ze serveru na pozadí
    
    Args:
        sock: Socket pro přijetí
        running: Event pro kontrolu běhu vlákna
    """
    while running.is_set():
        try:
            # Kontrola, zda je socket stále platný
            if sock.fileno() == -1:
                # Socket je uzavřen
                break
            
            # Použijeme kratší timeout pro kontrolu, ale neukončíme spojení při timeoutu
            message = receive_message(sock, timeout=2.0)
            if message:
                # Zpracování heartbeat ping
                if message == "PING":
                    # Odpověď na ping
                    send_message(sock, "PONG")
                    continue
                
                # Zpracování P2P informací
                if message.startswith("PEER_INFO:"):
                    # Formát: PEER_INFO:username:ip:port
                    parts = message.split(":")
                    if len(parts) >= 4:
                        peer_username = parts[1]
                        peer_ip = parts[2]
                        peer_port = parts[3]
                        print(f"\n[INFO] P2P informace o {peer_username}:")
                        print(f"  IP: {peer_ip}")
                        print(f"  Port: {peer_port}")
                        print(f"  Pro připojení použijte P2P aplikaci:")
                        print(f"    cd P2P/Python")
                        print(f"    python peer2peer.py")
                        print(f"    /connect {peer_ip} {peer_port}")
                elif message.startswith("[PM od"):
                    # Soukromá zpráva přes server (magenta)
                    print(f"\n{Colors.MAGENTA}{message}{Colors.RESET}")
                elif message.startswith("Server:"):
                    # Systémové zprávy (modře)
                    print(f"\n{Colors.BRIGHT_BLUE}[SYSTEM] {message}{Colors.RESET}")
                elif message.startswith("P2P informace:"):
                    # Seznam P2P informací (cyan)
                    print(f"\n{Colors.CYAN}{message}{Colors.RESET}")
                elif message.startswith("[COLOR:") and ":" in message:
                    # Chat zpráva s barvou uživatele
                    # Formát: "[COLOR:XX][HH:MM] Uživatel: zpráva"
                    import re
                    color_match = re.match(r'\[COLOR:(\d+)\]', message)
                    if color_match:
                        color_code = color_match.group(1)
                        # Odstranění [COLOR:XX] prefixu
                        message_without_color = re.sub(r'\[COLOR:\d+\]', '', message)
                        # Použití barvy uživatele
                        user_color = f'\033[{color_code}m'
                        print(f"\n{user_color}{message_without_color}{Colors.RESET}")
                    else:
                        print(f"\n{message}")
                elif message.startswith("[") and ":" in message and not message.startswith("ERROR") and not message.startswith("INFO"):
                    # Chat zpráva od uživatele s časovým razítkem (zeleně) - fallback
                    # Formát: "[HH:MM] Uživatel: zpráva"
                    print(f"\n{Colors.BRIGHT_GREEN}{message}{Colors.RESET}")
                elif ":" in message and not message.startswith("ERROR") and not message.startswith("INFO"):
                    # Chat zpráva od uživatele bez časového razítka (zeleně) - fallback
                    print(f"\n{Colors.BRIGHT_GREEN}{message}{Colors.RESET}")
                elif message.startswith("ERROR"):
                    # Chyby (červeně)
                    print(f"\n{Colors.RED}{message}{Colors.RESET}")
                elif message.startswith("INFO"):
                    # Info zprávy (žlutě)
                    print(f"\n{Colors.BRIGHT_YELLOW}{message}{Colors.RESET}")
                else:
                    # Jiné zprávy (bíle)
                    print(f"\n{Colors.WHITE}[Server] {message}{Colors.RESET}")
                print("> ", end="", flush=True)
            # Timeout (message is None) je normální - pokračujeme v čekání
        except socket.timeout:
            # Timeout je normální, pokračujeme
            continue
        except (OSError, ConnectionResetError, ConnectionAbortedError) as e:
            # Spojení bylo skutečně ukončeno
            if running.is_set():
                # Nezobrazujeme chybu, pokud jsme to ukončili sami
                if "10038" not in str(e):  # Ignorujeme chybu uzavřeného socketu
                    print(f"\nSpojení ukončeno")
                running.clear()
            break
        except Exception as e:
            # Jiná chyba - pouze pokud je socket stále otevřený
            if running.is_set() and sock.fileno() != -1:
                # Ignorujeme chyby uzavřeného socketu
                if "10038" not in str(e) and "10053" not in str(e):
                    logger.debug(f"Chyba v receive thread: {e}")
                continue
            break


def main():
    """
    Hlavní funkce klienta
    """
    client = None
    receive_thread = None
    running = threading.Event()
    
    try:
        # Vytvoření socketu
        # AF_INET = IPv4, SOCK_STREAM = TCP
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Nastavení timeoutu pro připojení (pouze pro connect)
        client.settimeout(CONNECTION_TIMEOUT)
        
        print("=" * 50)
        print("Socket Klient")
        print("=" * 50)
        print(f"Připojování k serveru {DEFAULT_HOST}:{DEFAULT_PORT}...")
        
        # Připojení k serveru
        try:
            client.connect((DEFAULT_HOST, DEFAULT_PORT))
        except socket.timeout:
            print(f"Chyba: Timeout při připojování k serveru")
            return
        except ConnectionRefusedError:
            print(f"Chyba: Nelze se připojit k serveru {DEFAULT_HOST}:{DEFAULT_PORT}")
            print("Ujistěte se, že server běží.")
            return
        
        print(f"✓ Připojeno k serveru na {DEFAULT_HOST}:{DEFAULT_PORT}")
        
        # Volitelné: Odeslání uživatelského jména a P2P portu
        username = input("Zadejte vaše jméno (nebo Enter pro výchozí): ").strip()
        if not username:
            username = "Guest"
        
        p2p_port_input = input("Zadejte P2P port pro soukromé zprávy (nebo Enter pro výchozí 8081): ").strip()
        try:
            p2p_port = int(p2p_port_input) if p2p_port_input else 8081
        except ValueError:
            p2p_port = 8081
            print(f"Neplatný port, použiji výchozí {p2p_port}")
        
        # Odeslání informací serveru
        send_message(client, f"SETUP:{username}:{p2p_port}")
        
        # Spuštění vlákna pro přijímání zpráv (před zobrazením promptu)
        running.set()
        receive_thread = threading.Thread(
            target=receive_messages_thread,
            args=(client, running),
            daemon=True
        )
        receive_thread.start()
        
        # Počkat chvíli, aby se přijala uvítací zpráva
        import time
        time.sleep(0.2)
        
        print("\n=== Chat připojen ===")
        print("Napište zprávu a stiskněte Enter pro odeslání všem uživatelům")
        print("Použijte '/help' pro nápovědu, '/quit' pro odpojení\n")
        
        # Hlavní smyčka pro komunikaci
        while running.is_set():
            try:
                # Čtení zprávy od uživatele
                message = input("> ").strip()
                
                if not message:
                    continue
                
                # Speciální příkazy
                if message.lower() in ['quit', 'exit', '/quit', '/exit']:
                    send_message(client, "/quit")
                    print("Odpojování...")
                    break
                elif message.startswith("/getpeer ") and len(message.split()) >= 2:
                    # Získání P2P informací o uživateli
                    send_message(client, message)
                elif message.startswith("/pm ") and len(message.split()) >= 3:
                    # Soukromá zpráva přes server
                    send_message(client, message)
                elif message == "/peers":
                    # Seznam všech uživatelů s P2P informacemi
                    send_message(client, message)
                elif message.startswith("/p2p ") and len(message.split()) >= 2:
                    # Automatické připojení přes P2P
                    target_username = message.split()[1]
                    print(f"Získávám P2P informace o {target_username}...")
                    send_message(client, f"/getpeer {target_username}")
                else:
                    # Odeslání zprávy serveru (server ji automaticky pošle všem v chatu)
                    if not send_message(client, message):
                        print("Chyba: Nepodařilo se odeslat zprávu")
                        break
                
                # V chat módu všechny zprávy přicházejí přes receive thread
                # (včetně vlastní zprávy, která se broadcastuje zpět)
                
            except EOFError:
                # Ctrl+D nebo konec vstupu
                print("\nUkončování...")
                send_message(client, "/quit")
                break
            except KeyboardInterrupt:
                # Ctrl+C
                print("\n\nUkončování...")
                send_message(client, "/quit")
                break
            except Exception as e:
                logger.error(f"Chyba při komunikaci: {e}")
                break
    
    except Exception as e:
        print(f"Kritická chyba: {e}")
        logger.error(f"Kritická chyba klienta: {e}", exc_info=True)
    
    finally:
        # Ukončení vlákna
        running.clear()
        
        # Počkat na dokončení receive thread
        if receive_thread and receive_thread.is_alive():
            receive_thread.join(timeout=0.5)
        
        # Uzavření socketu
        if client:
            try:
                # Zkontrolovat, zda je socket stále otevřený
                if client.fileno() != -1:
                    client.shutdown(socket.SHUT_RDWR)
                client.close()
            except (OSError, AttributeError):
                # Socket už je uzavřený nebo není platný
                pass
        
        print("\nOdpojeno od serveru")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nProgram ukončen uživatelem")
        sys.exit(0)
