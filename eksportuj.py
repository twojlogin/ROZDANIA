#!/usr/bin/env python3
"""
ROZDANIA - eksport katalogu retro do Markdown ("awesome-retro", lokalnie).

Czyta tylko bazę SQLite. Nic nie pobiera z sieci, nic nie uruchamia.
Wynik: katalog/README.md + katalog/<platforma>.md

Uwaga: to katalog metadanych/linków do archive.org. Zawartość archiwów jest
niezaufana - nie pobieraj i nie uruchamiaj plików bez weryfikacji.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import baza
import zrodla

KATALOG = Path(__file__).resolve().parent
DOMYSLNY_OUT = KATALOG / "katalog"


def _md(s: str | None) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def _link(tytul: str, url: str) -> str:
    t = _md(tytul) or url
    u = (url or "").strip()
    return f"[{t}]({u})" if u else t


def eksportuj(out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    con = baza.polacz()
    gry = [dict(r) for r in con.execute(
        """SELECT platforma, tytul, rok, gatunek, region, opis, okladka, pobrania, adres
           FROM gry ORDER BY platforma, pobrania DESC, tytul""").fetchall()]
    pakiety = [dict(r) for r in con.execute(
        """SELECT platforma, tytul, rok, bajty, plikow, opis
           FROM pakiety ORDER BY platforma, bajty DESC, tytul""").fetchall()]
    stat = baza.statystyki(con)
    con.close()

    by_plat: dict[str, list[dict]] = {}
    for g in gry:
        by_plat.setdefault(g["platforma"], []).append(g)
    pak_by_plat: dict[str, list[dict]] = {}
    for p in pakiety:
        pak_by_plat.setdefault(p["platforma"], []).append(p)

    platformy = sorted(set(by_plat) | set(pak_by_plat),
                       key=lambda k: (-len(by_plat.get(k, [])), -len(pak_by_plat.get(k, [])), k))

    # indeks
    lines = [
        "# Awesome Retro (katalog lokalny)",
        "",
        "> Wygenerowane z lokalnej bazy ROZDANIA. To katalog metadanych i linków,",
        "> nie zweryfikowane oprogramowanie. Pliki na archive.org mogą być uszkodzone,",
        "> nielegalne w Twojej jurysdykcji lub złośliwe. **Nie pobieraj i nie uruchamiaj**",
        "> niczego bez własnej weryfikacji (hash, źródło, sandbox).",
        "",
        "## Platformy",
        "",
        "| Platforma | Gry | Paczki | Plik |",
        "|---|---:|---:|---|",
    ]
    for p in platformy:
        nazwa = zrodla.PLATFORMY.get(p, {}).get("nazwa", p)
        pg = len(by_plat.get(p, []))
        pp = len(pak_by_plat.get(p, []))
        lines.append(f"| {_md(nazwa)} (`{p}`) | {pg} | {pp} | [katalog/{p}.md]({p}.md) |")
    if not platformy:
        lines.append("| _(brak danych)_ | 0 | 0 | uruchom `./pobierz.sh --gry` |")

    lines += [
        "",
        "## Bezpieczeństwo",
        "",
        "- Katalog zawiera **tylko metadane/linki**. ROZDANIA nie pobiera ROM-ów ani plików wykonywalnych.",
        "- Archive.org to archiwum publiczne: zawartość paczek jest **niezaufana**.",
        "- Przed użyciem: sprawdź źródło, hash, format, skanuj w izolacji/sandboxie.",
        "- Nie traktuj wpisu jako potwierdzenia legalności, kompletności ani bezpieczeństwa.",
        "",
        f"_Stan bazy: gry={stat.get('gry_razem', 0)}, paczki={stat.get('pakiety_razem', 0)}, darmowe={stat.get('darmowe_razem', 0)}._",
        "",
    ]
    (out / "README.md").write_text("\n".join(lines), encoding="utf-8")

    # pliki per platforma
    for p in platformy:
        nazwa = zrodla.PLATFORMY.get(p, {}).get("nazwa", p)
        plines = [
            f"# {nazwa} (`{p}`)",
            "",
            "> Metadane z archive.org. Zawartość niezaufana - weryfikuj przed użyciem.",
            "",
        ]
        gs = by_plat.get(p, [])
        if gs:
            plines += [
                "## Gry (pojedyncze wpisy)",
                "",
                "| Tytuł | Rok | Gatunek | Region | Pobrań | Link |",
                "|---|---:|---|---|---:|---|",
            ]
            for g in gs:
                plines.append(
                    f"| {_md(g['tytul'])} | {g.get('rok') or ''} | {_md(g.get('gatunek'))} | "
                    f"{_md(g.get('region'))} | {int(g.get('pobrania') or 0)} | {_link('archive', g.get('adres',''))} |"
                )
            plines.append("")
        ps = pak_by_plat.get(p, [])
        if ps:
            normalne, ryzykowne = [], []
            for pk in ps:
                kat = zrodla.klasyfikuj_wpis(pk.get("tytul"), int(pk.get("bajty") or 0))
                pk2 = dict(pk)
                pk2["_kat"] = kat
                pk2["_tytul"] = zrodla.czysty_tytul(pk.get("tytul"))
                (ryzykowne if kat in ("ryzyko", "system_narzedzia") else normalne).append(pk2)

            if normalne:
                plines += [
                    "## Paczki/archiwa (metadane)",
                    "",
                    "> Paczki mogą być duże i zawierać niezweryfikowane pliki. Nie pobieraj automatycznie.",
                    "",
                    "| Tytuł | Rok | Rozmiar GB | Plików | Kategoria | Link |",
                    "|---|---:|---:|---:|---|---|",
                ]
                for pk in normalne[:200]:
                    gb = (int(pk.get('bajty') or 0) / 1e9)
                    plines.append(
                        f"| {_md(pk['_tytul'])} | {pk.get('rok') or ''} | {gb:.2f} | "
                        f"{pk.get('plikow') or ''} | {_md(pk['_kat'])} | {_link('archive', pk.get('opis',''))} |"
                    )
                if len(normalne) > 200:
                    plines.append(f"\n_... i {len(normalne)-200} więcej paczek w bazie._\n")
                plines.append("")

            if ryzykowne:
                plines += [
                    "## System / narzędzia / niezweryfikowane ryzyko",
                    "",
                    "> Wpisy nie są katalogiem gier. Mogą zawierać BIOS/SDK/homebrew/crack/jailbreak lub inne ryzykowne treści. Nie pobieraj ani nie uruchamiaj.",
                    "",
                    "| Tytuł | Kategoria | Rozmiar GB | Link |",
                    "|---|---|---:|---|",
                ]
                for pk in ryzykowne[:100]:
                    gb = (int(pk.get('bajty') or 0) / 1e9)
                    plines.append(
                        f"| {_md(pk['_tytul'])} | {_md(pk['_kat'])} | {gb:.2f} | {_link('archive', pk.get('opis',''))} |"
                    )
                if len(ryzykowne) > 100:
                    plines.append(f"\n_... i {len(ryzykowne)-100} więcej wpisów ryzykownych/narzędziowych._\n")
                plines.append("")

        plines += ["[← indeks](README.md)", ""]
        (out / f"{p}.md").write_text("\n".join(plines), encoding="utf-8")

    return {"out": str(out), "platformy": len(platformy), "gry": len(gry), "pakiety": len(pakiety)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Eksportuj katalog retro do Markdown")
    ap.add_argument("--out", default=str(DOMYSLNY_OUT), help="katalog wyjściowy (domyślnie ./katalog)")
    args = ap.parse_args()
    info = eksportuj(Path(args.out))
    print(f"  wyeksportowano: {info['platformy']} platform, {info['gry']} gier, {info['pakiety']} paczek")
    print(f"  katalog: {info['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
