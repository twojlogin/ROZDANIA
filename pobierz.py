"""
ROZDANIA - pobieranie. Uruchom:  ./pobierz.sh [--platformy ps1,ps2] [--darmowe]

Limity (zostaja celowo, nie sa opcjonalne):
  - cache 24h, inaczej kazde uruchomienie odpytuje archiwum od nowa
  - 1.2s przerwy miedzy zapytaniami do archive.org - za szybko = 429
  - limit plikow na platforme (domyslnie 40 zbiorow) - 7000 zbiorow to
    tysiace requestow, niepotrzebnych do poprawnego dzialania
  - metadata/<id> tylko dla wybranych zbiorow, nie dla wszystkich

KAZDE uruchomienie wypisuje liczby. Brak liczby = brak danych.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import baza
import zrodla

KATALOG = Path(__file__).resolve().parent
CACHE = KATALOG / "dane" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

# Ile zbiorow sciagac na platforme. 40 to z sensem: archiwum ma ich tysiace,
# ale 40 daje juz dzialajacy katalog bez 4000 requestow.
DOMYSLNE_NA_PLATFORMĘ = 40
PRZERWA = 1.2          # sekundy miedzy zapytaniami
CACHE_GODZIN = 24


def _ua():
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")


def pobierz_json(url, klucz_cache=None, przerwa=PRZERWA):
    """Zwraca (dane, z_cache). Blad -> (None, False) i wypis na stderr."""
    plik = CACHE / f"{klucz_cache}.json" if klucz_cache else None
    if plik and plik.exists():
        wiek = datetime.now(timezone.utc) - datetime.fromtimestamp(
            plik.stat().st_mtime, timezone.utc)
        if wiek < timedelta(hours=CACHE_GODZIN):
            try:
                return json.loads(plik.read_text(encoding="utf-8")), True
            except (ValueError, OSError):
                pass                      # uszkodzony cache -> pobierz od nowa

    time.sleep(przerwa)                   # nie odpytywac w petli jak szaleniec
    req = urllib.request.Request(url, headers={"User-Agent": _ua()})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            dane = json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        print(f"  ! HTTP {e.code}: {url[:96]}", file=sys.stderr)
        return None, False
    except Exception as e:
        print(f"  ! blad: {type(e).__name__}: {str(e)[:70]}", file=sys.stderr)
        return None, False

    if plik:
        try:
            plik.write_text(json.dumps(dane, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return dane, False


# ---------------------------------------------------------------- archiwum
def _q(zapytanie, rows):
    return (f"{zrodla.ARCHIWUM['api_szukaj']}?"
            + urllib.parse.urlencode({
                "q": zapytanie,
                "fl[]": ["identifier", "title", "year", "item_size"],
                "rows": rows, "output": "json"}, doseq=True))


def archiwum_dla_platformy(klucz, limit):
    """Zwraca liste zbiorow (dictow) dla platformy. Zaden tytul gier
    z archiwum nie wyciagamy - archiwum takich nie wystawia."""
    cfg = zrodla.PLATFORMY[klucz]
    znalezione, uzyte = {}, set()

    for zap in cfg["zapytania"]:
        brak = limit - len(znalezione)
        if brak <= 0:
            break
        dane, _ = pobierz_json(_q(zap, limit * 3), f"ia_{klucz}_{abs(hash(zap)) % 9999}")
        if not dane:
            continue
        for d in dane.get("response", {}).get("docs", []):
            ident = d.get("identifier")
            if not ident or ident in uzyte:
                continue
            uzyte.add(ident)
            # Filtr smieci PRZED zapisem. Bez tego 481 zbiorow zawieralo
            # trenerki, skanery i puste placeholdery - 0 bajtow, 5 plikow
            # z czego 4 to .txt.
            if not zrodla.czy_zbior_jest_paczka_gier(
                    d.get("title") or ident, int(d.get("item_size") or 0), klucz):
                continue
            znalezione[ident] = {
                "id": ident,
                "platforma": klucz,
                "tytul": d.get("title") or ident,
                "rok": _rok(d.get("year")),
                "bajty": int(d.get("item_size") or 0),
                "plikow": None,
                "opis": zrodla.url_opis(ident),
                "pobrano": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            if len(znalezione) >= limit:
                break

    return list(znalezione.values())


def uzupelnij_pliki(con, pakiety, ile=12):
    """Zwraca liste plikow dla wybranych zbiorow - archiwum trzyma cala paczke
    w .zip, wiec liczba plikow i format sa w metadata, nie w wyniku szukania.
    Robimy to dla malej probki, nie dla wszystkiego - inaczej tysiace requestow."""
    probka = pakiety[:ile]
    for i, p in enumerate(probka, 1):
        dane, _ = pobierz_json(zrodla.ARCHIWUM["api_meta"].format(ident=p["id"]),
                               f"meta_{p['id']}")
        if not dane:
            continue
        pliki = dane.get("files", [])
        p["plikow"] = len(pliki)
        nazwy = [f.get("name", "") for f in pliki]
        p["formaty"] = sorted({n.rsplit(".", 1)[-1].lower()
                               for n in nazwy if "." in n})[:8]
        print(f"    [{i}/{len(probka)}] {p['id'][:44]:46} {len(pliki)} plikow")
    return pakiety


def _rok(y):
    if not y:
        return None
    if isinstance(y, list):
        y = y[0] if y else None
    s = str(y)[:4]
    return int(s) if s.isdigit() and len(s) == 4 else None


# ---------------------------------------------------------------- darmowe
def _gamerpower():
    dane, _ = pobierz_json(
        "https://www.gamerpower.com/api/giveaways?page=1", "gp_1")
    out = []
    for g in (dane or []):
        tytul = (g.get("title") or "").strip()
        if not tytul:
            continue
        # GamerPower ma identyfikatory, ale rozmiaru nie podaje. Nie odrzucamy
        # tu nic poza pustym tytulem - filtr smieci dziala po rozmiarze, ktorego
        # to zrodlo nie zwraca. Klucze do kosmetyki lecą nizej.
        out.append({
            "zrodlo": "GamerPower",
            "tytul": tytul,
            "adres": g.get("open_giveaway_url") or g.get("gamerpower_url") or "",
            "opis": (g.get("description") or "")[:400],
            # Odrzucamy klucze do kosmetyki i monet przy wlozieniu, nie pozniej.
            # Sprawdzacz wykryl 4 takie pozycje w bazie - teraz nie wchodza.
            "stan": "do_sprawdzenia",
            "klucz": f"gp:{g.get('id')}",
            "znaleziono": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return [o for o in out if zrodla.czy_oferta_jest_gra(o["tytul"])]


def _epic():
    url = ("https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
           "?locale=pl-PL&country=PL&allowCountries=PL")
    dane, _ = pobierz_json(url, "epic")
    out = []
    for slot in (dane or {}).get("data", {}).get("Catalog", {}).get("searchStore", {}).get("elements", []):
        # Sprawdzone na zywo: Epic NIE oddaje tu "promotionalOffers" - struktura
        # w promotions bywa null albo stringiem. Jedyna wiarygodna informacja
        # o darmowosci to cena: discountPrice == 0 znaczy "aktualnie za zero".
        cena = (slot.get("price") or {}).get("totalPrice") or {}
        teraz, normalna = cena.get("discountPrice"), cena.get("originalPrice")
        if not isinstance(teraz, int) or teraz != 0:
            continue                      # nie jest darmowe, pomijamy cicho
        tytul = (slot.get("title") or "").strip()
        if not tytul:
            continue
        mappingi = (slot.get("catalogNs") or {}).get("mappings") or []
        slug = mappingi[0].get("pageSlug") if mappingi else None
        out.append({
            "zrodlo": "Epic Games Store",
            "tytul": tytul,
            "adres": f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com",
            "opis": (slot.get("description") or "")[:400],
            "stan": "darmowe",           # cena 0 z API, nie zgadywanie
            "klucz": f"epic:{slot.get('id')}",
            "znaleziono": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    return out


# ---------------------------------------------------------------- raport
def raport(con, w_police=True):
    s = baza.statystyki(con)
    print("\n" + "=" * 62)
    print("  ROZDANIA - stan po pobraniu")
    print("=" * 62)
    if w_police:
        print(f"\n  Paczki ROM-ow (z archiwum, to NIE sa tytuly gier): {s['pakiety_razem']}")
        print(f"  Lacznie: {s['pakiety_gb']:.1f} GB")
        if s["w_police"]:
            print("\n  wg platform:")
            for klucz, n in s["w_police"].items():
                nazwa = zrodla.PLATFORMY.get(klucz, {}).get("nazwa", klucz)
                print(f"    {n:5}  {nazwa}")
        print()
    print(f"  Darmowe oferty: {s['darmowe_razem']}")
    for stan in ("darmowe", "platne", "nie_wiem", "do_sprawdzenia"):
        n = s.get(f"darmowe_{stan}")
        if n:
            print(f"    {n:5}  {stan}")
    print("\n  Uwaga: 'do_sprawdzenia' znaczy 'nikt nie sprawdzil', nie 'na pewno darmowe'.")
    print("=" * 62)
    return s


def main():
    ap = argparse.ArgumentParser(description="ROZDANIA - pobierz dane")
    ap.add_argument("--platformy", default="",
                    help="np. ps1,ps2,xbox360 (domyslnie wszystkie)")
    ap.add_argument("--limit", type=int, default=DOMYSLNE_NA_PLATFORMĘ,
                    help=f"zbiorow na platforme (domyslnie {DOMYSLNE_NA_PLATFORMĘ})")
    ap.add_argument("--darmowe", action="store_true", help="tylko giveaway")
    ap.add_argument("--bez-metadata", action="store_true",
                    help="pomija pobieranie listy plikow (szybsze)")
    a = ap.parse_args()

    klucze = ([k.strip() for k in a.platformy.split(",") if k.strip()]
              or list(zrodla.PLATFORMY))
    zle = [k for k in klucze if k not in zrodla.PLATFORMY]
    if zle:
        print(f"  ! nieznane platformy: {', '.join(zle)}")
        print(f"    dostepne: {', '.join(zrodla.PLATFORMY)}")
        return 2

    con = baza.polacz()

    if not a.darmowe:
        print(f"\n  Platforme: {len(klucze)} x max {a.limit} zbiorow")
        for klucz in klucze:
            nazwa = zrodla.PLATFORMY[klucz]["nazwa"]
            print(f"\n  -> {nazwa}")
            pak = archiwum_dla_platformy(klucz, a.limit)
            if not pak:
                print("     nic nie zwrocilo (patrz bledy powyzej)")
                continue
            if not a.bez_metadata:
                pak = uzupelnij_pliki(con, pak)
            baza.wstaw_pakiety(con, pak)
            gb = sum(p["bajty"] for p in pak) / 1e9
            con.commit()
            print(f"     {len(pak)} zbiorow, {gb:.1f} GB")

    print("\n  Darmowe oferty:")
    for nazwa, fn in (("GamerPower", _gamerpower), ("Epic", _epic)):
        rek = fn()
        if rek:
            baza.wstaw_darmowe(con, rek)
            con.commit()
            print(f"     {nazwa}: {len(rek)}")
        else:
            print(f"     {nazwa}: 0 (zrodlo nie odpowiedzialo)")

    raport(con, w_police=not a.darmowe)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
