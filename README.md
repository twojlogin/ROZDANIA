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
./pobierz.sh      # domyślnie: pojedyncze gry (metadane) + darmowe oferty
./pobierz.sh --platformy nes,snes,ps1,ps2,n64  # gry z wybranych platform
./pobierz.sh --pakiety  # duże paczki/archiwa ROM-ów (ostrożnie, dużo śmieci/ryzyka)
./sprawdz.sh      # 10 kontroli na danych: duplikaty, puste tytuły, śmieci
./weryfikuj.sh    # otwiera stronę każdej oferty i czyta — wolne, osobno
./start.sh        # serwer do podglądania
python3 eksportuj.py  # eksport katalogu do Markdown (awesome-retro)
```

Wszystkie skrypty uruchamiają własny `python3` i korzystają wyłącznie ze
standardowej biblioteki.

## Bezpieczeństwo (ważne)

- **Tylko metadane/linki.** ROZDANIA nie pobiera ROM-ów, archiwów ani plików wykonywalnych.
- **Archive.org jest niezaufane.** Paczki mogą zawierać uszkodzone pliki, śmieci, nielegalne treści w Twojej jurysdykcji albo **złośliwe oprogramowanie**. To dotyczy też „normalnie wyglądających” paczek.
- **Nic nie uruchamiaj automatycznie.** Przed użyciem: weryfikuj hash/źródło, sprawdzaj formaty, skanuj w izolacji/sandboxie, używaj osobnego środowiska.
- **Brak gwarancji.** Wpis w katalogu nie oznacza, że coś jest bezpieczne, kompletne, legalne do pobrania/użycia ani warte uwagi.

## Katalog retro (awesome-retro)

Projekt może służyć jako lokalny katalog retro pogrupowany po konsolach/platformach:
metadane, rok, gatunek, region, link do archive.org. Eksport:

```bash
python3 eksportuj.py --out katalog
```

Tworzy `katalog/README.md` i `katalog/<platforma>.md`. To widok katalogu, nie
rekomendacja pobierania.

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
| `eksportuj.py` | eksport katalogu retro do Markdown (`katalog/`) |
| `serwer.py` / `ui.html` | podgląd |
| `srodowisko/` | skrypty pomocnicze środowiska |

Baza i cache są generowane i **nie są w repo** (`.gitignore`).
