# Java Socket Server/Client

## Základní vlastnosti

Tato implementace používá standardní Java třídy pro vytvoření síťové komunikace.

### Hlavní charakteristiky:

- **Třída ServerSocket** - pro vytvoření serverového socketu
- **Třída Socket** - pro komunikaci s klienty
- **Thread-per-client** - každý klient je obsluhován samostatným vláknem
- **Object-oriented přístup** - čistá Java architektura s třídami

### Hlavní metody:

1. `new ServerSocket(port)` - vytvoření serverového socketu
2. `server.accept()` - přijetí nového klienta
3. `socket.getInputStream()` - získání vstupního streamu
4. `socket.getOutputStream()` - získání výstupního streamu
5. `read()` / `write()` - čtení a zápis dat

### Kompilace:

```bash
# Kompilace všech .java souborů
javac *.java

# Nebo jednotlivě:
javac Server.java
javac Client.java
```

### Spuštění:

```bash
# Server (port 8080)
java Server

# Klient
java Client
```

### Poznámky:

- Vyžaduje Java 8 nebo novější
- Kód je multiplatformní (Windows, Linux, macOS)
- Automatická správa paměti pomocí Garbage Collectoru
- Používá try-with-resources pro automatické uzavření zdrojů
