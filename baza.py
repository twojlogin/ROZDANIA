"""
ROZDANIA - baza. Nowy plik, nowy schemat, zero migracji.

Dwie tabele:
  pakiety  - paczki ROM-ow z archive.org (a NIE tytuly gier - patrz zrodla.py)
  darmowe  - publiczne promocje (giveaway), z oznaczonym stanem

Stan w darmowe jest KLUCZOWY i nigdy nie jest zgadywany:
  'do_sprawdzenia' - wstawione, nigdy nie weryfikowane
  'darmowe'        - strona sklepu zawiera slowo 'claim'/'add to library'
  'platne'         - strona sklepu zawiera 'add to cart'/cene
  'nie_wiem'       - strona nie daje jednoznacznej odpowiedzi
"""
import sqlite3
from pathlib import Path

KATALOG = Path(__file__).resolve().parent
DB = KATALOG / "dane" / "rozdania.db"

SCHEMAT = """
CREATE TABLE IF NOT EXISTS pakiety (
    id          TEXT PRIMARY KEY,
    platforma   TEXT NOT NULL,
    tytul       TEXT,
    rok         INTEGER,
    bajty       INTEGER,
    plikow      INTEGER,
    opis        TEXT,
    pobrano     TEXT
);

CREATE TABLE IF NOT EXISTS darmowe (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    zrodlo      TEXT NOT NULL,
    tytul       TEXT NOT NULL,
    adres       TEXT NOT NULL,
    opis        TEXT,
    stan        TEXT NOT NULL DEFAULT 'do_sprawdzenia',
    klucz       TEXT UNIQUE,
    znaleziono  TEXT
);

CREATE INDEX IF NOT EXISTS idx_pakiety_platforma ON pakiety(platforma);
CREATE INDEX IF NOT EXISTS idx_darmowe_stan       ON darmowe(stan);
CREATE INDEX IF NOT EXISTS idx_darmowe_zrodlo     ON darmowe(zrodlo);
"""


def polacz():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(SCHEMAT)
    con.commit()
    return con


def wstaw_pakiety(con, rekordy):
    """rekordy: lista slownikow z zrodla.archiwum_pakiety()."""
    con.executemany(
        """INSERT INTO pakiety (id, platforma, tytul, rok, bajty, plikow, opis, pobrano)
           VALUES (:id, :platforma, :tytul, :rok, :bajty, :plikow, :opis, :pobrano)
           ON CONFLICT(id) DO UPDATE SET
             platforma=excluded.platforma,
             tytul=excluded.tytul,
             rok=excluded.rok,
             bajty=excluded.bajty,
             plikow=excluded.plikow,
             opis=excluded.opis,
             pobrano=excluded.pobrano""",
        rekordy)


def wstaw_darmowe(con, rekordy):
    """Nadpisuje stan tylko jesli nowy jest 'okreslony' - inaczej nie niszczy
    poprzedniego wyniku weryfikacji slowem 'do_sprawdzenia'."""
    for r in rekordy:
        stary = con.execute(
            "SELECT stan FROM darmowe WHERE klucz=?", (r["klucz"],)).fetchone()
        stan = r["stan"]
        if stary and stary["stan"] in ("darmowe", "platne") and stan == "do_sprawdzenia":
            stan = stary["stan"]
        con.execute(
            """INSERT INTO darmowe (zrodlo, tytul, adres, opis, stan, klucz, znaleziono)
               VALUES (:zrodlo, :tytul, :adres, :opis, :stan, :klucz, :znaleziono)
               ON CONFLICT(klucz) DO UPDATE SET
                 tytul=excluded.tytul,
                 opis=excluded.opis,
                 stan=excluded.stan,
                 znaleziono=excluded.znaleziono""",
            {**r, "stan": stan})


def statystyki(con):
    s = {}
    s["pakiety_razem"] = con.execute("SELECT COUNT(*) c FROM pakiety").fetchone()["c"]
    s["pakiety_gb"] = (con.execute(
        "SELECT COALESCE(SUM(bajty),0) c FROM pakiety").fetchone()["c"] or 0) / 1e9
    s["darmowe_razem"] = con.execute("SELECT COUNT(*) c FROM darmowe").fetchone()["c"]
    for row in con.execute(
            "SELECT stan, COUNT(*) c FROM darmowe GROUP BY stan ORDER BY 2 DESC"):
        s[f"darmowe_{row['stan']}"] = row["c"]
    s["w_police"] = {}
    for row in con.execute(
            "SELECT platforma, COUNT(*) c FROM pakiety GROUP BY platforma ORDER BY 2 DESC"):
        s["w_police"][row["platforma"]] = row["c"]
    return s
