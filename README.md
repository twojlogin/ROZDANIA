# ROZDANIA

Zbiera **rozdania (giveaway) i darmowe pakiety** z kilku źródeł i — co jest
istotne — **weryfikuje**, czy oferta naprawdę jest darmowa. Osobno: zbieranie
to jedno zadanie, sprawdzanie drugie, więc są dwa osobne programy.

| Stan na 6 października 2026 | |
|---|---|
| paczek w bazie | **624** (39 520 GB) |
| darmowych ofert | **49** |
| kontrola danych (`sprawdz.py`) | **10/10** |
| zależności zewnętrzne | **zero** — standardowa biblioteka |

## Uruchomienie

```bash
./pobierz.sh      # pobiera pakiety i oferty (limity świadome, patrz niżej)
./sprawdz.sh      # 10 kontroli na danych: duplikaty, puste tytuły, śmieci
./weryfikuj.sh    # otwiera stronę każdej oferty i czyta — wolne, osobno
./start.sh        # serwer do podglądania
```

Wszystkie skrypty uruchamiają własny `python3` i korzystają wyłącznie ze
standardowej biblioteki.

## Uczciwie o tym, co to potwierdza

`sprawdz.sh` zalicza **10/10**, ale to znaczy „sprawdzone na danych", nie
„na pewno działa". Weryfikacja ceny wymaga otwarcia każdej strony sklepu —
dlatego `weryfikuj.sh` jest osobnym, wolnym krokiem, a nie częścią pobierania.

Nie ma tu testów jednostkowych. I to jest świadome, z komentarzem w kodzie
(`sprawdz.py`):

> Nie jest to test „czy kod jest poprawny". Test napisany przez tego samego
> model, który napisał kod, potwierdza tylko to, co ten model już wiedział.

## Limity pobierania (świadome, nie opcjonalne)

- **cache 24 h** — inaczej każde uruchomienie odpytuje archiwum od nowa
- **1,2 s przerwy** między zapytaniami (konfigurowalne: `--przerwa 2.0`, min 1.0s)
- **retry z backoffem** przy HTTP 429/503 (2s, 4s, 8s + Retry-After)
- **limit requestów** (domyślnie 200, `--max-requestow 0` = bez limitu)
- **limit gier na platformę** (domyślnie 40)
- **`--gry`** — pobiera pojedyncze gry z archive.org (metadane, okładki)
- **User-Agent** identyfikuje ROZDANIA (nie udaje przeglądarki)

## Szanowanie infrastruktury (archive.org)

ROZDANIA jest „uprzejmym obywatelem” (polite citizen):
- nie pobiera więcej niż potrzeba (limit + cache + deduplikacja),
- czeka między requestami (1.2s domyślnie),
- ponawia z backoffem przy 429 (nie zalewa serwera),
- szanuje `Retry-After` z nagłówka,
- cache 24h — nie odpytuje tego samego dwa razy,
- limit 200 requestów na uruchomienie (zabezpieczenie przed runaway).

Nie używamy `curl | bash`, nie scrapujemy HTML z Wayback Machine bez potrzeby.
Metadata pobieramy z oficjalnego API archive.org (advancedsearch + metadata).

## Źródła

Wszystkie adresy są w jednym miejscu: `zrodla.py`. Nic nie jest kopiowane
z innego projektu — to jedyne miejsce, które trzeba edytować, gdy źródło się
zmieni.

- `archive.org` — pakiety (wolumeny, roczne wydania)
- `freebies.indiegala.com`, `store.epicgames.com`, `www.gamerpower.com` — oferty

## Struktura

| Plik | Rola |
|---|---|
| `pobierz.py` | pobiera do `dane/`, cache 24 h, limity |
| `zrodla.py` | jedyne miejsce z adresami źródeł |
| `baza.py` | schemat bazy (dwie tabele), zero migracji |
| `sprawdz.py` | 10 kontroli na danych |
| `weryfikuj.py` | otwiera stronę każdej oferty, czyta treść |
| `serwer.py` / `ui.html` | podgląd |
| `srodowisko/` | skrypty pomocnicze środowiska |

Baza i cache są generowane i **nie są w repo** (`.gitignore`).
