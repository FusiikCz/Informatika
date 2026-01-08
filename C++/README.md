# C++ Socket Server/Client

## Základní vlastnosti

Tato implementace používá **POSIX sockety** pro vytvoření síťové komunikace mezi serverem a klienty.

### Hlavní charakteristiky:

- **POSIX sockety** - nízká úroveň síťového programování
- **Thread-per-client** - každý klient je obsluhován samostatným vláknem
- **Sdílený seznam socketů** - server udržuje seznam všech připojených klientů
- **Mutex pro synchronizaci** - zajišťuje thread-safe přístup ke sdíleným datům

### Hlavní kroky serveru:

1. `socket()` - vytvoření socketu
2. `bind()` - navázání socketu na adresu a port
3. `listen()` - naslouchání příchozím připojením
4. `accept()` - přijetí nového klienta
5. `recv()` - přijímání dat od klienta
6. `send()` - odesílání dat klientovi

### Kompilace:

```bash
# Server
g++ -std=c++11 -pthread server.cpp -o server

# Klient
g++ -std=c++11 client.cpp -o client
```

### Spuštění:

```bash
# Server (port 8080)
./server

# Klient
./client
```

### Poznámky:

- Vyžaduje C++11 nebo novější
- Na Windows může být potřeba použít Winsock místo POSIX socketů
- Pro Linux/Unix systémy je implementace přímo kompatibilní
