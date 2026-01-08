# Socket Server/Client Implementace

Tento repozitář obsahuje implementace socket serveru a klienta ve čtyřech různých programovacích jazycích. Všechny implementace používají **thread-per-client** architekturu, kde každý připojený klient je obsluhován samostatným vláknem.

## Struktura repozitáře
```
Informatika/
├── C++/          # POSIX socket implementace
├── Python/       # Python socket modul implementace
├── Java/         # Java ServerSocket/Socket implementace
├── C#/           # C# TcpListener/TcpClient implementace
└── ReadMe.md     # Tento soubor
```

## Přehled implementací

### C++
- **Soubory:** `server.cpp`, `client.cpp`
- **Technologie:** POSIX sockety, std::thread, mutex
- **Vlastnosti:** Nízká úroveň síťového programování, sdílený seznam socketů s mutexem

### Python
- **Soubory:** `server.py`, `client.py`
- **Technologie:** socket modul, threading modul
- **Vlastnosti:** Jednoduchý a čitelný kód, multiplatformní

### Java
- **Soubory:** `Server.java`, `Client.java`
- **Technologie:** ServerSocket, Socket, Thread
- **Vlastnosti:** Object-oriented přístup, try-with-resources

### C#
- **Soubory:** `Server.cs`, `Client.cs`
- **Technologie:** TcpListener, TcpClient, Thread
- **Vlastnosti:** .NET framework, moderní C# syntax

## Jak spustit

### C++

#### Kompilace:
```bash
cd C++

# Server
g++ -std=c++11 -pthread server.cpp -o server

# Klient
g++ -std=c++11 client.cpp -o client
```

#### Spuštění:
```bash
# Terminal 1 - Server
./server

# Terminal 2 - Klient
./client
```

**Poznámka:** Na Windows může být potřeba použít Winsock místo POSIX socketů.

---

### Python

#### Spuštění:
```bash
cd Python

# Terminal 1 - Server
python server.py

# Terminal 2 - Klient
python client.py
```

**Poznámka:** Vyžaduje Python 3.x

---

### Java

#### Kompilace:
```bash
cd Java

# Kompilace všech souborů
javac *.java

# Nebo jednotlivě
javac Server.java
javac Client.java
```

#### Spuštění:
```bash
# Terminal 1 - Server
java Server

# Terminal 2 - Klient
java Client
```

**Poznámka:** Vyžaduje Java 8 nebo novější

---

### C#

#### Kompilace a spuštění:
```bash
cd C#

# Pomocí .NET CLI
dotnet build
dotnet run Server.cs

# Nebo pomocí csc.exe (Visual Studio)
csc Server.cs
Server.exe

csc Client.cs
Client.exe
```

#### Spuštění:
```bash
# Terminal 1 - Server
dotnet run Server.cs
# nebo
Server.exe

# Terminal 2 - Klient
dotnet run Client.cs
# nebo
Client.exe
```

**Poznámka:** Vyžaduje .NET Framework nebo .NET Core/.NET 5+

## Konfigurace

Všechny implementace používají:
- **Port:** 8080
- **Adresa serveru:** 0.0.0.0 (přijímá na všech rozhraních)
- **Adresa klienta:** 127.0.0.1 (localhost)

Pro změnu portu upravte hodnotu v příslušném souboru serveru a klienta.

## Funkcionalita

Všechny implementace poskytují:

1. **Echo server** - server přijímá zprávy od klienta a odesílá je zpět s prefixem "Echo: "
2. **Multi-client podpora** - server může současně obsluhovat více klientů
3. **Thread-safe operace** - bezpečná synchronizace při práci s více vlákny
4. **Správné uzavírání zdrojů** - automatické nebo manuální uzavření socketů

## Použití

1. Spusťte server v jednom terminálu
2. Spusťte jeden nebo více klientů v dalších terminálech
3. Zadejte zprávy v klientovi - server je odešle zpět
4. Pro ukončení klienta zadejte `quit`

## Další informace

Pro detailnější informace o konkrétní implementaci se podívejte do README.md souboru v příslušné složce:
- [C++ README](C++/README.md)
- [Python README](Python/README.md)
- [Java README](Java/README.md)
- [C# README](C#/README.md)

## Poznámky

- Ujistěte se, že port 8080 není používán jinou aplikací
- Na některých systémech může být potřeba oprávnění správce pro binding na porty < 1024
- Všechny implementace jsou testovány na standardních konfiguracích

## Architektura

Všechny implementace používají stejnou architekturu:

```
┌─────────┐
│ Server  │
│ (Port   │
│  8080)  │
└────┬────┘
     │
     ├─── Thread 1 ─── Client 1
     ├─── Thread 2 ─── Client 2
     └─── Thread N ─── Client N
```

Každý klient má vlastní vlákno, které obsluhuje jeho požadavky nezávisle na ostatních.
