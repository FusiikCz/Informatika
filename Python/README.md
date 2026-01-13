# Python Socket Server/Client

## Rozšířená implementace

Tato implementace používá standardní Python moduly pro vytvoření robustní síťové komunikace s pokročilými funkcemi.

### Hlavní charakteristiky:

- **Modul socket** - základní síťové operace
- **Modul threading** - vlákna pro obsluhu více klientů současně
- **Thread-per-client** - každý klient je obsluhován samostatným vláknem
- **Message protocol** - spolehlivá komunikace s prefixem délky zprávy
- **Logging systém** - strukturované logování událostí
- **Error handling** - robustní zpracování chyb
- **Broadcast funkcionalita** - odesílání zpráv všem klientům
- **Konfigurovatelné nastavení** - snadná úprava parametrů
- **Graceful shutdown** - korektní ukončení serveru
- **Connection timeouts** - ochrana proti zablokování
- **Příkazy** - interaktivní příkazy pro klienty

### Nové vylepšení:

#### Server (`server.py`):
- ✅ **Robustní error handling** - kompletní zpracování všech typů chyb
- ✅ **Logging systém** - strukturované logování s časovými razítky
- ✅ **Message protocol** - prefix délky zprávy pro spolehlivou komunikaci
- ✅ **Broadcast** - odesílání zpráv všem připojeným klientům
- ✅ **Uživatelská jména** - podpora uživatelských jmen
- ✅ **Příkazy** - `/quit`, `/list`, `/broadcast`, `/help`
- ✅ **Max klienti** - limit na maximální počet připojených klientů
- ✅ **Connection timeout** - automatické odpojení neaktivních klientů
- ✅ **Graceful shutdown** - korektní ukončení všech připojení

#### Klient (`client.py`):
- ✅ **Asynchronní přijímání** - samostatné vlákno pro přijímání zpráv
- ✅ **Lepší UX** - přehledné uživatelské rozhraní
- ✅ **Timeout support** - ochrana proti zablokování
- ✅ **Uživatelské jméno** - možnost nastavit vlastní jméno
- ✅ **Error handling** - robustní zpracování chyb připojení
- ✅ **Příkazy** - podpora všech serverových příkazů

### Hlavní metody:

1. `socket.socket()` - vytvoření socketu
2. `bind()` - navázání socketu na adresu a port
3. `listen()` - naslouchání příchozím připojením
4. `accept()` - přijetí nového klienta
5. `send_message()` - odeslání zprávy s prefixem délky
6. `receive_message()` - přijetí zprávy s prefixem délky
7. `broadcast_message()` - odeslání zprávy všem klientům

### Spuštění:

```bash
# Server (port 8080)
python server.py

# Klient (v jiném terminálu)
python client.py
```

### Příkazy klienta:

- `/quit` nebo `quit` - odpojení ze serveru
- `/list` - seznam všech připojených uživatelů
- `/broadcast <zpráva>` - odeslání zprávy všem uživatelům
- `/help` - zobrazení nápovědy

### Testování:

Pro ověření funkcionality můžete použít testovací skript:

```bash
# V jednom terminálu spusťte server
python server.py

# V druhém terminálu spusťte testy
python test_client_server.py
```

Testovací skript ověří:
- Základní připojení a komunikaci
- Funkčnost příkazů
- Současné připojení více klientů

### Konfigurace:

V souborech `server.py` a `client.py` můžete upravit následující konstanty:

```python
DEFAULT_HOST = '0.0.0.0'  # Server host
DEFAULT_PORT = 8080        # Port
BUFFER_SIZE = 4096         # Velikost bufferu
MAX_CLIENTS = 100          # Max počet klientů
CONNECTION_TIMEOUT = 30.0  # Timeout připojení (sekundy)
MESSAGE_TIMEOUT = 60.0     # Timeout zprávy (sekundy)
```

### Poznámky:

- Vyžaduje Python 3.x
- Kód je multiplatformní (Windows, Linux, macOS)
- Automatická správa paměti - není potřeba ručně uvolňovat zdroje
- Message protocol zajišťuje spolehlivou komunikaci i při velkých zprávách
- Thread-safe implementace pro bezpečnou práci s více klienty současně