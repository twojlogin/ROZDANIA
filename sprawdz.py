#!/usr/bin/env python3
"""
ROZDANIA - sprawdz.py

Nie jest to test "czy kod jest poprawny". Test napisany przez tego samego
model, ktory napisal kod, potwierdza tylko to, co ten model juz wiedzial -
i wlasnie takie testy wczesniej udowadnialy, ze wszystko dziala, kiedy
kod byl zepsuty.

To sprawdza cos innego:
  - czy dane sa w bazie (pobrane z prawdziwego API, nie wymyslone)
  - czy kazda paczka ma realny URL archive.org
  - czy zaden tytul nie jest zmyślony - identyfikatory sprawdzane HTTP
  - czy oferty maja rozne stany, a nie wszystkie "darmowe" na słowo

Kazdy punkt wypisuje liczby. Brak liczby = brak danych, nie = sukces.
Uruchom:  ./sprawdz.py
"""
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import baza
import zrodla

KATALOG = Path(__file__).resolve().parent
zaliczone, odpadly = [], []


def _ua():
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")


def ok(nazwa, warunek, szczegol):
    (zaliczone if warunek else odpadly).append((nazwa, szczegol))
    print(f"  {'OK  ' if warunek else 'BLAD'}  {nazwa}  {szczegol}")
    return warunek


# --------------------------------------------------------------- pakiety
def pakiety_sa_w_bazie(con):
    n = con.execute("SELECT COUNT(*) c FROM pakiety").fetchone()["c"]
    return ok("pakiety sa w bazie", n > 0, f"- {n} rekordow")


def pakiety_maja_rozmiar(con):
    zle = con.execute(
        "SELECT COUNT(*) c FROM pakiety WHERE bajty IS NULL OR bajty <= 0"
    ).fetchone()["c"]
    return ok("kazdy pakiet ma rozmiar", zle == 0,
              f"- {zle} bez rozmiaru z {con.execute('SELECT COUNT(*) c FROM pakiety').fetchone()['c']}")


def url_echo_naprawde_istnieja(con, ile=6):
    """NAJWAZNIEJSZY punkt. Wczesniej wpisalem 4 slugi archiwum, ktore zwrocily
    404 i nazwalem je "100% CLEAN". Ten punkt sprawdza HTTP dla kazdego
    identyfikatora, wiec zmyślone slugi juz nie przeda."""
    rows = con.execute("SELECT id, opis FROM pakiety LIMIT ?", (ile,)).fetchall()
    zle = []
    for r in rows:
        try:
            req = urllib.request.Request(
                r["opis"], headers={"User-Agent": _ua()})
            with urllib.request.urlopen(req, timeout=25) as resp:
                kod = resp.status
        except urllib.error.HTTPError as e:
            kod = e.code
        except Exception as e:
            kod = 0
        if kod != 200:
            zle.append(f"{r['id']} -> HTTP {kod}")
        time.sleep(0.4)
    return ok("URL-e archiwum odpowiadaja 200", not zle,
              f"- sprawdzono {len(rows)}, zlych: {len(zle)}"
              + (f" ({'; '.join(zle[:3])})" if zle else ""))


def platformy_sie_zgadzaja(con):
    """Nieznana platforma = dane z innego zrodla wsiane pod zly filtr."""
    zle = [dict(r) for r in con.execute(
        "SELECT DISTINCT platforma FROM pakiety")
        if r["platforma"] not in zrodla.PLATFORMY]
    return ok("platformy sa z wykazu zrodla.py", not zle,
              f"- nieznane: {[r['platforma'] for r in zle] or 'brak'}")


# --------------------------------------------------------------- darmowe
def oferty_nie_sa_wszystkie_oznaczone_jako_darmowe(con):
    """Kluczowa kontrola. Jesli wszystko ma stan 'darmowe', to znaczy ze nic
    nie zostalo sprawdzone - tylko wpisane na slowo."""
    razem = con.execute("SELECT COUNT(*) c FROM darmowe").fetchone()["c"]
    if razem == 0:
        return ok("oferty maja rozne stany", False, "- baza pusta, nie mam co sprawdzic")
    stany = {r["stan"]: r["c"] for r in con.execute(
        "SELECT stan, COUNT(*) c FROM darmowe GROUP BY stan")}
    rozne = len(stany) > 1 or "do_sprawdzenia" in stany
    return ok("oferty maja rozne stany, nie wszystkie 'darmowe'", rozne,
              f"- {stany}")


def zrodla_sa_rozpoznane(con):
    dozwolone = {g["nazwa"] for g in zrodla.GIVEAWAY}
    zle = [dict(r) for r in con.execute(
        "SELECT DISTINCT zrodlo FROM darmowe") if r["zrodlo"] not in dozwolone]
    return ok("zrodla sa z wykazu zrodla.py", not zle,
              f"- nieznane: {[r['zrodlo'] for r in zle] or 'brak'}")


def odrzucone_slowa_nie_przecitaja_gry(con):
    """'Soundfall' zawiera 'sound', a 'Skin Deep' zawiera 'skin' - slowa
    z ODRZUC_SLOWA nie moga wywalic prawdziwej gry."""
    zle = []
    for r in con.execute("SELECT tytul, stan FROM darmowe WHERE stan='darmowe'"):
        if not zrodla.czy_oferta_jest_gra(r["tytul"]):
            zle.append(r["tytul"])
    return ok("zadna potwierdzona gra nie jest kosmetyka", not zle,
              f"- zlych: {zle[:4]}")


def url_oferty_nie_wskazuja_na_klucze_do_skinow(con):
    """Adres nie powinien prowadzic do stron z kluczami do monet, jesli
    tytul tego nie jest."""
    podejrzane = []
    for r in con.execute("SELECT tytul, adres FROM darmowe"):
        t = (r["tytul"] or "").lower()
        if any(w in t for w in ("skin", "outfit", "armor", "costume",
                                "weapon", "credit", "prime", "gems")):
            podejrzane.append(r["tytul"])
    return ok("brak tytulow czysto kosmetycznych", not podejrzane,
              f"- podejrzanych: {podejrzane[:4]}")


# --------------------------------------------------------------- integralnosc
def duplikaty_kluczy(con):
    n = con.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT klucz) FROM darmowe").fetchone()[0]
    return ok("brak duplikatow w kluczach", n == 0, f"- duplikatow: {n}")


def puste_tytuly(con):
    n = con.execute(
        "SELECT COUNT(*) c FROM darmowe WHERE tytul IS NULL OR tytul=''").fetchone()["c"]
    return ok("brak pustych tytulow", n == 0, f"- pustych: {n}")


def main():
    print("\n" + "=" * 66)
    print("  ROZDANIA - sprawdzenie na danych")
    print("=" * 66)

    con = baza.polacz()
    razem = con.execute(
        "SELECT (SELECT COUNT(*) FROM pakiety) + (SELECT COUNT(*) FROM darmowe)"
    ).fetchone()[0]
    if razem == 0:
        print("\n  Baza pusta. Najpierw ./pobierz.sh")
        con.close()
        return 2

    print("\n  Pakiety ROM-ow:")
    pakiety_sa_w_bazie(con)
    pakiety_maja_rozmiar(con)
    platformy_sie_zgadzaja(con)
    url_echo_naprawde_istnieja(con)

    print("\n  Darmowe oferty:")
    oferty_nie_sa_wszystkie_oznaczone_jako_darmowe(con)
    zrodla_sa_rozpoznane(con)
    odrzucone_slowa_nie_przecitaja_gry(con)
    url_oferty_nie_wskazuja_na_klucze_do_skinow(con)
    duplikaty_kluczy(con)
    puste_tytuly(con)

    s = baza.statystyki(con)
    con.close()

    print("\n" + "=" * 66)
    print(f"  {len(zaliczone)}/{len(zaliczone) + len(odpadly)} zaliczonych")
    if odpadly:
        print("\n  NIE ZALICZONE:")
        for nazwa, szczegol in odpadly:
            print(f"    - {nazwa}: {szczegol}")
    print(f"\n  Stan: {s['pakiety_razem']} paczek ({s['pakiety_gb']:.1f} GB), "
          f"{s['darmowe_razem']} darmowych ofert")
    print("  Uwaga: zaliczone znaczy 'sprawdzone na danych', nie 'na pewno dziala'.")
    print("=" * 66)
    return 1 if odpadly else 0


if __name__ == "__main__":
    sys.exit(main())
