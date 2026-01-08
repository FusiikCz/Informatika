# C# Socket Server/Client

## Základní vlastnosti

Tato implementace používá .NET třídy pro vytvoření síťové komunikace.

### Hlavní charakteristiky:

- **TcpListener** - třída pro vytvoření TCP serveru
- **TcpClient** - třída pro komunikaci s klienty
- **Thread nebo Task** - pro asynchronní obsluhu klientů
- **Thread-per-client** - každý klient je obsluhován samostatným vláknem

### Hlavní metody:

1. `new TcpListener(IPAddress, port)` - vytvoření TCP listeneru
2. `listener.Start()` - spuštění naslouchání
3. `listener.AcceptTcpClient()` - přijetí nového klienta
4. `client.GetStream()` - získání síťového streamu
5. `stream.Read()` / `stream.Write()` - čtení a zápis dat

### Kompilace:

```bash
# Kompilace pomocí .NET CLI
dotnet build

# Nebo pomocí csc.exe (Visual Studio)
csc Server.cs
csc Client.cs
```

### Spuštění:

```bash
# Server (port 8080)
dotnet run Server.cs
# nebo
Server.exe

# Klient
dotnet run Client.cs
# nebo
Client.exe
```

### Poznámky:

- Vyžaduje .NET Framework nebo .NET Core/.NET 5+
- Kód je multiplatformní (Windows, Linux, macOS s .NET Core)
- Používá using statements pro automatické uvolnění zdrojů
- Moderní C# syntax s async/await možnostmi
