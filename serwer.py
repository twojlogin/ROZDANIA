#!/usr/bin/env python3
"""
ROZDANIA - serwer. Uruchom ./start.sh
Nie ma zaleznosci poza standardowa biblioteka. Zero Flask, zero npm.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

import baza
import zrodla

PORT = 8770
KATALOG = __import__("pathlib").Path(__file__).resolve().parent


class Obsluga(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass                      # bez smieci w terminalu

    def _json(self, dane, kod=200):
        body = json.dumps(dane, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        sciezka = urlparse(self.path).path
        if sciezka in ("/", "/ui.html"):
            return self._plik("ui.html")
        if sciezka == "/api/darmowe":
            con = baza.polacz()
            w = [dict(r) for r in con.execute(
                "SELECT zrodlo,tytul,adres,opis,stan FROM darmowe ORDER BY stan, tytul")]
            con.close()
            return self._json(w)
        if sciezka == "/api/pakiety":
            con = baza.polacz()
            plat = (parse_qs(urlparse(self.path).query).get("platforma") or [None])[0]
            if plat:
                w = [dict(r) for r in con.execute(
                    "SELECT * FROM pakiety WHERE platforma=? ORDER BY bajty DESC", (plat,))]
            else:
                w = [dict(r) for r in con.execute(
                    "SELECT * FROM pakiety ORDER BY platforma, bajty DESC")]
            for r in w:
                r["kategoria"] = zrodla.klasyfikuj_wpis(r.get("tytul"), int(r.get("bajty") or 0))
                r["tytul_czysty"] = zrodla.czysty_tytul(r.get("tytul"))
            con.close()
            return self._json(w)
        if sciezka == "/api/gry":
            con = baza.polacz()
            plat = (parse_qs(urlparse(self.path).query).get("platforma") or [None])[0]
            q = (parse_qs(urlparse(self.path).query).get("q") or [""])[0].strip()
            if q:
                # FTS5: wyszukiwanie pelnotekstowe (tytul, gatunek, opis, platforma)
                sql = ("SELECT g.* FROM gry g JOIN gry_fts f ON g.rowid = f.rowid "
                       "WHERE gry_fts MATCH ?")
                params = [q]
                if plat:
                    sql += " AND g.platforma = ?"
                    params.append(plat)
                sql += " ORDER BY g.pobrania DESC"
                try:
                    w = [dict(r) for r in con.execute(sql, params)]
                except Exception:
                    # fallback gdy FTS nie dziala
                    w = [dict(r) for r in con.execute(
                        "SELECT * FROM gry WHERE lower(tytul) LIKE ?" + (" AND platforma=?" if plat else "") + " ORDER BY pobrania DESC",
                        [f"%{q.lower()}%"] + ([plat] if plat else []))]
            elif plat:
                w = [dict(r) for r in con.execute(
                    "SELECT * FROM gry WHERE platforma=? ORDER BY pobrania DESC", (plat,))]
            else:
                w = [dict(r) for r in con.execute(
                    "SELECT * FROM gry ORDER BY platforma, pobrania DESC")]
            con.close()
            return self._json(w)
        if sciezka == "/api/summary":
            con = baza.polacz()
            s = baza.statystyki(con)
            con.close()
            return self._json(s)
        self._json({"error": "nie ma takiej trasy"}, 404)

    def _plik(self, nazwa):
        body = (KATALOG / nazwa).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    con = baza.polacz()
    n = baza.statystyki(con)
    con.close()
    print(f"  ROZDANIA -> http://127.0.0.1:{PORT}")
    print(f"  baza: {n['pakiety_razem']} paczek, {n['darmowe_razem']} darmowych ofert")
    if not n["pakiety_razem"] and not n["darmowe_razem"]:
        print("  baza pusta - najpierw ./pobierz.sh")
    try:
        HTTPServer(("127.0.0.1", PORT), Obsluga).serve_forever()
    except KeyboardInterrupt:
        print("\n  zatrzymane")
