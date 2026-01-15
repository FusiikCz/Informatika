# Jak to funguje? - Jednoduché vysvětlení

## Co jsme vytvořili?

Vytvořili jsme **chat server** - program, který umožňuje více lidem chatovat současně přes síť.

## Základní pojmy

### Server
- **Co to je?** Program, který "naslouchá" a čeká na připojení
- **Co dělá?** Přijímá zprávy od klientů a posílá je všem ostatním
- **Příklad:** Jako moderátor ve skupině - dostává zprávy a přeposílá je všem

### Klient
- **Co to je?** Program, který se připojuje k serveru
- **Co dělá?** Posílá zprávy serveru a přijímá zprávy od ostatních
- **Příklad:** Jako účastník ve skupině - píše zprávy a čte zprávy od ostatních

## Jak to funguje krok za krokem?

### 1. Spuštění serveru
```
Server se spustí → Čeká na připojení na portu 8080
```

### 2. Připojení klientů
```
Klient 1 se připojí → Zadá jméno "Alice"
Klient 2 se připojí → Zadá jméno "Bob"
Klient 3 se připojí → Zadá jméno "Charlie"
```

### 3. Chatování
```
Alice napíše: "Ahoj všichni!"
    ↓
Server přijme zprávu
    ↓
Server pošle zprávu VŠEM klientům (včetně Alice)
    ↓
Všichni vidí: "Alice: Ahoj všichni!"
```

### 4. Odpojení
```
Alice napíše: "/quit"
    ↓
Server pošle všem: "Server: Alice opustil chat"
    ↓
Alice se odpojí
```

## Protokol komunikace

### Co je to protokol?
Je to "jazyk", kterým spolu programy mluví. Všechny naše programy používají **stejný protokol**, takže mohou spolu komunikovat.

### Jak vypadá zpráva?
```
[4 byty: délka zprávy][zpráva v textu]
```

**Příklad:**
- Zpráva: "Ahoj"
- Délka: 4 znaky
- Formát: `[0x00 0x00 0x00 0x04][A][h][o][j]`

### Proč délka zprávy?
- Zajišťuje, že se přijme celá zpráva
- Funguje i s dlouhými zprávami
- Spolehlivější než prosté posílání textu

## Cross-language kompatibilita

### Co to znamená?
Programy v různých jazycích mohou spolu komunikovat!

### Jak to funguje?
Všechny programy používají **stejný protokol**:
- Python server ↔ C++ klient
- C++ server ↔ Python klient
- Python server ↔ Python klient
- C++ server ↔ C++ klient

### Proč je to užitečné?
- Každý může použít svůj oblíbený jazyk
- Můžete kombinovat různé technologie
- Flexibilita při vývoji

## Architektura

### Server-Client model
```
┌─────────┐
│ Server  │ ← Centrální bod
└────┬────┘
     │
     ├──→ Klient 1 (Python)
     └──→ Klient 2 (C++)
```

### Jak server zpracovává klienty?
```
Nový klient se připojí
    ↓
Server vytvoří nové vlákno (thread)
    ↓
Každý klient má své vlastní vlákno
    ↓
Všechny vlákna běží současně
```

**Proč vlákna?**
- Server může obsluhovat více klientů najednou
- Jeden klient neblokuje ostatní
- Rychlejší a efektivnější

## Chat funkcionalita

### Co se stane, když někdo napíše zprávu?

1. **Klient odešle zprávu serveru**
   ```
   Klient → Server: "Ahoj"
   ```

2. **Server přijme zprávu**
   ```
   Server: "Přijato od Alice: Ahoj"
   ```

3. **Server pošle zprávu všem**
   ```
   Server → Všichni klienti: "Alice: Ahoj"
   ```

4. **Všichni klienti zobrazí zprávu**
   ```
   Klient 1 vidí: "Alice: Ahoj"
   Klient 2 vidí: "Alice: Ahoj"
   Klient 3 vidí: "Alice: Ahoj"
   ```

### Broadcast
- **Co to je?** Odeslání zprávy všem klientům najednou
- **Kdy se používá?** Při každé chat zprávě
- **Proč?** Aby všichni viděli všechny zprávy

## Technické detaily

### Port
- **Co to je?** Číslo, které identifikuje službu na počítači
- **Náš port:** 8080
- **Příklad:** Jako číslo dveří v hotelu

### Socket
- **Co to je?** Koncový bod pro síťovou komunikaci
- **Příklad:** Jako telefonní linka mezi dvěma lidmi

### Thread (Vlákno)
- **Co to je?** Nezávislý tok provádění programu
- **V našem případě:** Každý klient má své vlastní vlákno
- **Příklad:** Jako více lidí pracujících současně

## Příkazy

### `/quit`
- Ukončí připojení
- Server pošle ostatním: "Server: [jméno] opustil chat"

### `/list`
- Zobrazí seznam všech připojených uživatelů

### `/help`
- Zobrazí nápovědu s dostupnými příkazy

## Jak to spustit?

### 1. Spusťte server
```bash
# Python
python server.py

# C++
g++ -std=c++11 -pthread server.cpp -o server
./server
```

### 2. Spusťte klienty (v jiných terminálech)
```bash
# Python
python client.py

# C++
g++ -std=c++11 client.cpp -o client
./client
```

### 3. Chatujte!
- Zadejte jméno
- Pište zprávy
- Všichni uvidí vaše zprávy

## Soukromé zprávy a P2P přepínání

### Problém se soukromými zprávami v Server-Client modelu

V klasickém Server-Client modelu by soukromé zprávy fungovaly takto:
```
Alice → Server: "/pm Bob Ahoj!"
Server → Bob: "Alice: Ahoj!"
```

**Nevýhody:**
- Server vidí všechny soukromé zprávy
- Všechny zprávy procházejí přes server (vyšší zátěž)
- Server je jediný bod selhání
- Méně soukromé (server má přístup ke všem zprávám)

### Řešení: Přepnutí na P2P pro soukromé zprávy

**Peer-to-Peer (P2P)** umožňuje přímou komunikaci mezi klienty bez serveru:

```
Alice se připojí k serveru (pro veřejný chat)
    ↓
Alice zjistí IP adresu a port Boba (ze serveru)
    ↓
Alice se přímo připojí k Bobovi (P2P spojení)
    ↓
Alice → Bob (přímo): "Soukromá zpráva"
    ↓
Bob → Alice (přímo): "Odpověď"
```

### Hybridní přístup

**Nejlepší řešení kombinuje oba modely:**

1. **Server-Client pro veřejný chat**
   - Všichni se připojí k serveru
   - Veřejné zprávy jdou přes server
   - Server koordinuje a zobrazuje seznam uživatelů

2. **P2P pro soukromé zprávy**
   - Když chce Alice poslat soukromou zprávu Bobovi:
     - Server poskytne IP adresu a port Boba
     - Alice se přímo připojí k Bobovi
     - Komunikace probíhá přímo mezi Alicí a Bobem
     - Server nevidí obsah soukromých zpráv

### Jak to funguje v praxi?

**Krok 1: Připojení k serveru**
```
Alice → Server: Připojení
Server → Alice: "Vítejte! Seznam uživatelů: Bob (127.0.0.1:8081), Charlie (127.0.0.1:8082)"
```

**Krok 2: Požádání o soukromou zprávu**
```
Alice → Server: "/pm Bob"
Server → Alice: "Bob je na 127.0.0.1:8081"
```

**Krok 3: Přepnutí na P2P**
```
Alice se odpojí od serveru (nebo zůstane připojená pro veřejný chat)
    ↓
Alice se připojí přímo k Bobovi (P2P)
    ↓
Alice ↔ Bob: Přímá komunikace
```

**Krok 4: Soukromá komunikace**
```
Alice → Bob (přímo): "Soukromá zpráva"
Bob → Alice (přímo): "Odpověď"
```

### Výhody P2P pro soukromé zprávy

- **Soukromí:** Server nevidí obsah zpráv
- **Rychlost:** Přímá komunikace je rychlejší
- **Zátěž serveru:** Server není zatížen soukromými zprávami
- **Škálovatelnost:** Server nemusí zpracovávat všechny zprávy

### Implementace

V našem projektu máme:
- **Server-Client implementace** (Python, C++) - pro veřejný chat
- **P2P implementace** (v adresáři P2P/) - pro přímou komunikaci

**Použití:**
1. Spusťte server pro veřejný chat
2. Klienti se připojí k serveru
3. Pro soukromé zprávy použijte P2P aplikaci
4. P2P aplikace může běžet současně se server-klient aplikací

### Příklad scénáře

**Terminál 1: Server**
```bash
python server.py
```

**Terminál 2: Alice (Server-Client)**
```bash
python client.py
# Připojí se k serveru, vidí veřejný chat
```

**Terminál 3: Bob (Server-Client)**
```bash
python client.py
# Připojí se k serveru, vidí veřejný chat
```

**Terminál 4: Alice (P2P pro soukromé zprávy)**
```bash
cd P2P/Python
python peer2peer.py
# Připojí se přímo k Bobovi pro soukromou komunikaci
/connect 127.0.0.1 8081
```

**Terminál 5: Bob (P2P pro soukromé zprávy)**
```bash
cd P2P/Python
python peer2peer.py
# Naslouchá na portu 8081, přijme připojení od Alice
```

## Možná vylepšení

- **Soukromé zprávy přes P2P** - Přepnutí na peer-to-peer pro soukromou komunikaci
- **Místnosti (Rooms)** - Více chat místností současně
- **Šifrování** - Bezpečnější komunikace
- **Historie zpráv** - Uložení zpráv pro pozdější čtení
- **Emoji a formátování** - Bohatší zprávy
- **Soubory** - Posílání souborů mezi uživateli

## Časté otázky

**Q: Proč potřebujeme server?**
A: Server koordinuje komunikaci mezi všemi klienty a zajišťuje, že všichni dostanou všechny zprávy. Pro soukromé zprávy můžeme použít P2P.

**Q: Můžu použít jiný port?**
A: Ano, stačí změnit číslo portu v kódu (ale všichni musí používat stejný port).

**Q: Funguje to přes internet?**
A: Ano, pokud změníte IP adresu z `127.0.0.1` (localhost) na skutečnou IP adresu serveru. Pro P2P může být potřeba otevřít porty ve firewallu.

**Q: Kolik klientů může být připojeno najednou?**
A: Výchozí limit je 100, ale můžete ho změnit v kódu.

**Q: Jak přepnout na P2P pro soukromé zprávy?**
A: Spusťte P2P aplikaci (v adresáři P2P/) a připojte se přímo k druhému uživateli. Můžete mít otevřené obě aplikace současně - jednu pro veřejný chat, druhou pro soukromé zprávy.

**Q: Je P2P bezpečnější než Server-Client?**
A: Pro soukromé zprávy ano, protože server nevidí obsah zpráv. Ale stále potřebujete server pro koordinaci a zjištění IP adres ostatních uživatelů.

## Související koncepty

- **TCP/IP** - Protokol, který používáme
- **Socket programming** - Programování síťových aplikací
- **Multithreading** - Současné zpracování více úloh
- **Client-Server model** - Architektura síťových aplikací
- **Peer-to-Peer (P2P)** - Přímá komunikace mezi uzly
- **Hybridní architektura** - Kombinace Server-Client a P2P

---

**Vytvořeno pro vzdělávací účely**
