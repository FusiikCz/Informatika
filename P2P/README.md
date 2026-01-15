
# Peer-to-Peer (P2P) Implementace

Tento adresář obsahuje P2P (Peer-to-Peer) implementace v Pythonu a C++.

## Přehled

P2P architektura umožňuje každému uzlu současně fungovat jako server i klient. Na rozdíl od klasického server-klient modelu, peery komunikují přímo mezi sebou bez centrálního serveru.

## Struktura

```
P2P/
├── Python/      # Python P2P implementace
├── C++/         # C++ P2P implementace
└── README.md    # Tento soubor
```

## Kompatibilita

Všechny P2P implementace používají **stejný protokol** (length-prefixed messages), takže peery v různých jazycích mohou komunikovat mezi sebou:

- ✅ Python peer ↔ C++ peer
- ✅ Python peer ↔ Python peer
- ✅ C++ peer ↔ C++ peer

### Příkazy

Všechny implementace podporují stejné příkazy:

- `/connect <host> <port>` - Připojení k peeru
- `/list` - Seznam připojených peerů
- `/broadcast <zpráva>` - Odeslání zprávy všem peerům
- `/quit` - Ukončení aplikace

## Protokol

Všechny implementace používají **length-prefixed message protocol**:

```
[4 byty: délka zprávy v big-endian][zpráva v UTF-8]
```

Toto zajišťuje:
- Spolehlivou komunikaci mezi různými jazyky
- Podporu velkých zpráv
- Ochranu proti fragmentaci

## Vlastnosti

### Společné vlastnosti všech implementací:

- ✅ Hybridní architektura (server + klient)
- ✅ Přímá komunikace mezi peery
- ✅ Broadcast funkcionalita
- ✅ Správa připojení
- ✅ Heartbeat mechanismus
- ✅ Graceful shutdown
- ✅ Cross-language kompatibilita

### Python specifické:

- ✅ Pokročilé logging
- ✅ Rozšířené příkazy (`/send`, `/disconnect`)
- ✅ Detailní error handling

### C++ specifické:

- ✅ Nízká latence
- ✅ Efektivní správa paměti
- ✅ POSIX sockety


## Příklad cross-language komunikace

```bash
# Terminal 1: Python peer na portu 8081
python peer2peer.py

# Terminal 2: C++ peer na portu 8082
./peer2peer

# Z C++ peera se připojte k Python peeru:
/connect 127.0.0.1 8081

# Odeslání broadcast zprávy z Python peera:
/broadcast Hello from Python!
```

## Poznámky

- Každý peer naslouchá na svém vlastním portu (výchozí 8081)
- Pro více peerů na stejném počítači změňte port v kódu
- P2P implementace jsou kompatibilní se server-klient implementacemi (stejný protokol)
- Pro produkční použití doporučujeme přidat šifrování a autentizaci

## Troubleshooting

**Problém: Nelze se připojit k peeru**
- Ověřte, že peer běží
- Zkontrolujte, zda port není blokován firewallem
- Ujistěte se, že používáte správnou IP adresu

**Problém: Zprávy se nedoručují**
- Ověřte, že peery používají stejný protokol
- Zkontrolujte logy pro chyby
- Ověřte, že jsou peery skutečně připojeni (`/list`)

## Rozšíření

Možná vylepšení pro všechny implementace:

- [ ] Automatický peer discovery
- [ ] Šifrování komunikace (TLS)
- [ ] Distributed hash table (DHT)
- [ ] Replikace dat
- [ ] Load balancing
- [ ] Metriky a monitoring
