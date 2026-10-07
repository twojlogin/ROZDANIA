#!/usr/bin/env python3
"""
ROZDANIA - weryfikacja: czy oferta naprawde jest darmowa.

Osobny plik od sprawdz.py, bo to zadanie inne i wolne:
sprawdz.py liczy rekordy, to otwiera strone kazdej oferty i czyta ja.

CO ROBI - po kolei, bez zgadywania:
  1. pobiera strone oferty
  2. szuka slow oznaczajacych, ze cos kosztuje  ("add to cart", "$19.99")
  3. szuka slow oznaczajacych darmowy pobieranie ("claim", "add to library")
  4. jezeli cena wygrywa - stan = 'platne'
     jezeli darmowy pobieranie wygrywa - stan = 'darmowe'
     jesli strona jest zpaywall/login i nie wiem - 'nie_wiem'
  5. jak nie da sie pobrac strony - stan zostaje, dostajesz 'blad_pobrania'

Ostateczny werdykt to zawsze tresc strony, nie nazwa zrodla.
GamerPower nazywa cos "giveaway" takze wtedy, gdy to klucz do skina -
dlatego samo zrodlo nie wystarcza.

WAZNE: to nie jest test napisany przez model, ktory napisal ten kod.
To jest odczyt cudzej strony. Jesli strona klamie, my tez przejdziemy
do konca - dlatego wynik zapisuje sie z linkiem i dlugoscia odpowiedzi,
zeby mozna bylo pozniej sprawdzic recznie.

Uruchom:  ./weryfikuj.py [--limit 20] [--tylko-do-sprawdzenia]
"""
import argparse
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import baza
import zrodla

KATALOG = Path(__file__).resolve().parent

# Sygnaly ze cos kosztuje. "add to cart" jest jednoznaczne - sklep nie
# pokazuje koszyka przy darmowej pozycji.
KOSZTUJE = re.compile(
    r"(add to cart|add to basket|dodaj do koszyka|buy now|kup teraz|"
    r"purchase for|owned at|originally \$?\s?[\d]+|"
    r"[$€£]\s?\d+[.,]\d{2}|\d+[.,]\d{2}\s?(?:USD|EUR|PLN))", re.I)

# Sygnaly darmowego pobrania. "claim" jest tego samego typu co koszyk:
# sklep pokazuje go tylko wtedy, gdy da sie cos wziac.
DARMOWE_SIGNAŁY = re.compile(
    r"(claim (?:it|now|your|the (?:game|reward|key))|add to (?:your )?library|"
    r"get (?:it )?for free|free download|download for free|"
    r"claim free|darmowa|darmowe|za darmo|add to steam library)", re.I)

# Strona logowania/paywall - nie da sie orzec
ZA_LOGOWANIEM = re.compile(
    r"(sign in to continue|log in to continue|zaloguj sie|"
    r"please log in|create an account to)", re.I)


def _ua():
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")


def pobierz_strone(adres, timeout=25):
    """Zwraca (tekst|None, info). info ma kod HTTP i dlugosc - do dziennika."""
    req = urllib.request.Request(adres, headers={
        "User-Agent": _ua(),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            surowe = r.read(900_000)
            kod = r.status
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, type(e).__name__
    for kodowanie in ("utf-8", "windows-1250", "latin-1"):
        try:
            return surowe.decode(kodowanie), f"HTTP {kod}, {len(surowe)}B"
        except UnicodeDecodeError:
            continue
    return None, f"nieczytelne, {len(surowe)}B"


def osadz_ilosc(html, slowo):
    """Ile razy wystapilo slowo. 'add to cart' w stopce i w menu to nie
    to samo co 'add to cart' przy tytule gry - liczymy, bo liczba
    rozroznia oferte od sklepu z calym katalogiem."""
    return len(slowo.findall(html))


def oceń(html):
    """Zwraca (stan, uzasadnienie). Kolejnosc ma znaczenie - najpierw
    koszyk, potem darmowe, potem zaloguj."""
    n_koszt, n_darmowe = osadz_ilosc(html, KOSZTUJE), osadz_ilosc(html, DARMOWE_SIGNAŁY)

    if n_koszt and not n_darmowe:
        return "platne", f"koszyk x{n_koszt}, brak 'claim'"
    if n_darmowe and not n_koszt:
        return "darmowe", f"'claim' x{n_darmowe}, brak koszyka"
    if n_darmowe and n_koszt:
        # Oba. Nie zgadujemy - sklep moze pokazywac koszyke obok darmowej
        # pozycji. Traktujemy jako "nie wiadomo" zamiast wybrac korzystniej.
        return "nie_wiem", f"oba: koszyk x{n_koszt}, claim x{n_darmowe}"
    if ZA_LOGOWANIEM.search(html):
        return "nie_wiem", "strona wymaga logowania, nie da sie orzec"
    return "nie_wiem", "brak jednoznacznego sygnalu"


def dziennik(linia):
    print(linia, flush=True)


def main():
    ap = argparse.ArgumentParser(description="Weryfikacja: czy oferta jest darmowa")
    ap.add_argument("--limit", type=int, default=20, help="ile ofert na bieg")
    ap.add_argument("--tylko-do-sprawdzenia", action="store_true",
                    help="sprawdzaj tylko te z nieustalonym stanem")
    ap.add_argument("--przerwa", type=float, default=1.5, help="sekundy miedzy stronami")
    a = ap.parse_args()

    con = baza.polacz()
    if a.tylko_do_sprawdzenia:
        kolejka = con.execute(
            "SELECT id, zrodlo, tytul, adres FROM darmowe WHERE stan='do_sprawdzenia' "
            "ORDER BY id LIMIT ?", (a.limit,)).fetchall()
    else:
        kolejka = con.execute(
            "SELECT id, zrodlo, tytul, adres FROM darmowe ORDER BY id LIMIT ?",
            (a.limit,)).fetchall()

    if not kolejka:
        s = baza.statystyki(con)
        print(f"\n  Nie ma nic do sprawdzenia. Stan: {s['darmowe_razem']} ofert.")
        con.close()
        return 0

    print(f"\n  Weryfikuję {len(kolejka)} ofert (przerwa {a.przerwa}s)\n")
    zmienione, bledy = 0, 0

    for i, r in enumerate(kolejka, 1):
        html, info = pobierz_strone(r["adres"]) if r["adres"] else (None, "brak adresu")
        if not html:
            bledy += 1
            dziennik(f"  [{i}/{len(kolejka)}] nie pobrano: {r['tytul'][:40]} ({info})")
            con.execute("UPDATE darmowe SET stan='nie_wiem' WHERE id=? AND stan='do_sprawdzenia'",
                        (r["id"],))
            con.commit()
            time.sleep(a.przerwa)
            continue

        stan, uzasadnienie = oceń(html)
        con.execute("UPDATE darmowe SET stan=? WHERE id=?", (stan, r["id"]))
        con.commit()
        if stan != "do_sprawdzenia":
            zmienione += 1
        dziennik(f"  [{i}/{len(kolejka)}] {stan:10} {r['tytul'][:40]:42} {uzasadnienie}")
        time.sleep(a.przerwa)

    s = baza.statystyki(con)
    con.close()
    print("\n" + "=" * 64)
    print(f"  zmieniono stan: {zmienione} / {len(kolejka)}   (nie pobrano: {bledy})")
    print(f"  teraz: {s.get('darmowe_darmowe',0)} darmowych, "
          f"{s.get('darmowe_platne',0)} platnych, "
          f"{s.get('darmowe_nie_wiem',0)} nie wiadomo, "
          f"{s.get('darmowe_do_sprawdzenia',0)} do sprawdzenia")
    print("  'darmowe' znaczy: na stronie było 'claim' i nie było koszyka.")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
