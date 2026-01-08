# Python Socket Server/Client

## Základní vlastnosti

Tato implementace používá standardní Python moduly pro vytvoření síťové komunikace.

### Hlavní charakteristiky:

- **Modul socket** - základní síťové operace
- **Modul threading** - vlákna pro obsluhu více klientů současně
- **Jednoduchý a čitelný kód** - Python syntax je přehledná a snadno pochopitelná
- **Thread-per-client** - každý klient je obsluhován samostatným vláknem

### Hlavní metody:

1. `socket.socket()` - vytvoření socketu
2. `bind()` - navázání socketu na adresu a port
3. `listen()` - naslouchání příchozím připojením
4. `accept()` - přijetí nového klienta
5. `recv()` - přijímání dat od klienta
6. `sendall()` - odesílání dat klientovi (zajišťuje odeslání všech dat)

### Spuštění:

```bash
# Server (port 8080)
python server.py

# Klient
python client.py
```

### Poznámky:

- Vyžaduje Python 3.x
- Kód je multiplatformní (Windows, Linux, macOS)
- Automatická správa paměti - není potřeba ručně uvolňovat zdroje
