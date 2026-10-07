"""
ROZDANIA - jedyne miejsce, gdzie sa adresy zrodel danych.

Napisane od zera. Nic nie jest kopiowane z innego projektu.
Kazde zrodlo ma tu jedna funkcje i jeden docelowy katalog w bazie.

UWAGA: to jest lista zrodel, nie biblioteka gier. Co zrodlo realnie
oddaje, jest opisane w jego slowniku "co_daje" - nie obiecujemy
wiecej niz archiwum oddaje.
"""
import urllib.parse

# ---------------------------------------------------------------- platformy
# Klucz wewnetrzny -> (etykieta, wzorce szukania w archive.org, rozszerzenia)
# Kolejnosc wazna: UI filtruje wg tego.
PLATFORMY = {
    "ps1": {
        "nazwa": "PlayStation",
        "zapytania": ["identifier:psx* AND mediatype:software",
                      "subject:PlayStation AND mediatype:software"],
        "rozszerzenia": (".bin", ".cue", ".pbp", ".ecm", ".iso", ".chd", ".m3u"),
    },
    "ps2": {
        "nazwa": "PlayStation 2",
        "zapytania": ["identifier:ps2* AND mediatype:software",
                      "title:(PlayStation 2) AND mediatype:software"],
        "rozszerzenia": (".iso", ".bin", ".cue"),
    },
    "ps3": {
        "nazwa": "PlayStation 3",
        "zapytania": ["identifier:ps3* AND mediatype:software",
                      "title:(PlayStation 3) AND mediatype:software"],
        "rozszerzenia": (".iso", ".pkg"),
    },
    "psp": {
        "nazwa": "PSP",
        "zapytania": ["identifier:psp* AND mediatype:software",
                      "title:(PlayStation Portable) AND mediatype:software"],
        "rozszerzenia": (".iso", ".cso", ".pbp"),
    },
    "xbox": {
        "nazwa": "Xbox",
        "zapytania": ["identifier:xbox* AND mediatype:software"],
        "rozszerzenia": (".iso", ".xex", ".bin", ".cue"),
    },
    "xbox360": {
        "nazwa": "Xbox 360",
        "zapytania": ["identifier:xbox360* AND mediatype:software",
                      "title:(Xbox 360) AND mediatype:software"],
        "rozszerzenia": (".iso", ".xex"),
    },
    "gc": {
        "nazwa": "GameCube",
        "zapytania": ["identifier:gamecube* AND mediatype:software"],
        "rozszerzenia": (".iso", ".gcm", ".gcz"),
    },
    "dc": {
        "nazwa": "Dreamcast",
        "zapytania": ["identifier:dreamcast* AND mediatype:software"],
        "rozszerzenia": (".iso", ".cdi", ".chd", ".gdi"),
    },
    "n64": {
        "nazwa": "Nintendo 64",
        "zapytania": ["identifier:n64* AND mediatype:software"],
        "rozszerzenia": (".z64", ".n64", ".v64", ".zip"),
    },
    "snes": {
        "nazwa": "SNES",
        "zapytania": ["identifier:snes* AND mediatype:software"],
        "rozszerzenia": (".sfc", ".smc", ".fig", ".swc"),
    },
    "nes": {
        "nazwa": "NES",
        "zapytania": ["identifier:nes* AND mediatype:software"],
        "rozszerzenia": (".nes", ".fds", ".unf", ".zip"),
    },
    "genesis": {
        "nazwa": "Mega Drive / Genesis",
        "zapytania": ["identifier:genesis* AND mediatype:software"],
        "rozszerzenia": (".md", ".gen", ".smd", ".bin", ".zip"),
    },
}

# ---------------------------------------------------------------- archiwum.org
# UWAGA KRYTYCZNE: advancedsearch.php zwraca ZBIORY, nie tytuly gier.
# Jeden zbior to zwykle jedna paczka .zip z cala platforma, np.
# "psp-roms-dvd" -> 2 paczki po 4.4 GB, 6 plikow. Tytul gry w srodku
# NIE jest osobnym polem. Ten katalog pokazuje paczki, nie gry.
ARCHIWUM = {
    "nazwa": "archive.org",
    "co_daje": "zbiory ROM-ow (paczki) per platforma: identyfikator, tytul zbioru, "
               "rok, rozmiar calkowity, liczba plikow. NIE tytuly gier.",
    "co_nie_daje": "listy gier, okladek, osobnych wpisow na tytul gry",
    "szukaj": "https://archive.org/search?query={q}",
    "opisy": "https://archive.org/details/{ident}",
    "api_szukaj": "https://archive.org/advancedsearch.php",
    "api_meta": "https://archive.org/metadata/{ident}",
}

# ---------------------------------------------------------------- giveaway
# Publiczne strony z promocjami. Nie wymagaja konta, nie wymagaja klucza API.
# To sa linki do promocji - nic wiecej. Czy cos jest naprawde darmowe,
# da sie sprawdzic tylko prosac o strone sklepu (to robi pobierz.py --
# i dlatego kolumna "stan" w bazie nie jest zgadywana).
GIVEAWAY = [
    {
        "nazwa": "GamerPower",
        "adres": "https://www.gamerpower.com/api/giveaways",
        "strona": "https://www.gamerpower.com",
    },
    {
        "nazwa": "IndieGala",
        "adres": "https://freebies.indiegala.com/",
        "strona": "https://freebies.indiegala.com",
    },
    {
        "nazwa": "Epic Games Store",
        "adres": "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions",
        "strona": "https://store.epicgames.com",
    },
]

# ---------------------------------------------------------------- filtry tytulow
# Odrzucamy tytuly ktore udaja darmowa gre, a sa kosmetyka/moneta/klucz.
# Kazde slowo ma byc konkretne. NIE usuwamy slowa "pack" ani "bundle"
# bez kontekstu - "Witcher 3" to nie dodatek, a "Dying Light Weapon Pack" tak.
ODRZUC_SLOWA = (
    "skin", "armor", "armour", "outfit", "weapon skin", "costume",
    "avatar", "wallpaper", "soundtrack", "ost ", "artbook", "art book",
    "credit", "credits", "prime", "in-game item", "season pass",
    "dungeons and dragons", "patron", "tip jar", "supporter",
    "early access", "demo", "soundtrack edition", "virtual currency",
    "gems", "primogems", "coins", "koen", "credits key",
)

# Slowa ktore NA PEWNO sa gra, mimo zawieraja slowo odrzucane
# (np. "Soundfall", "Skin Deep"). Sprawdzane przed odrzuceniem.
ZAWSZE_GRA = (
    "soundfall", "skin deep", "bundle of", "package of",
)

# Klucz do kosmetyki/monety - NIE jest gra, nawet jesli slowo "armor" czy
# "skin" wystepuje wylacznie jako dopisek po myślniku albo w "Outfit".
# Te wzorce trzeba lapac w calosci tytulu, nie jako slowo w srodku zdania:
#   "007 First Light: Ops Radiant Outfit Key Giveaway"  -> klucz, nie gra
#   "The Witcher 3: Wild Hunt Remastered - Scarlet Crest Armor Giveaway" -> klucz
# Sprawdzone na 4 realnych tytulach z bazy, wszystkie 4 to klucze do monet.
KOSMETYKA_W_TYTULE = (
    "key giveaway", "armor giveaway", "outfit giveaway", "skin giveaway",
    "pack giveaway", "bundle giveaway", "bundle key", "pack key",
    "outfit key", "armor key", "skin key", "code giveaway",
    "credits key", "primogems", "gems code", "bonus pack key",
    "weapon skin", "costume key", "battle pass key", "dlc key",
    "premature key", "starter pack key", "welcome pack",
)


def czy_oferta_jest_gra(tytul):
    """Czy tytul wyglada na gre, a nie na klucz do skina.

    Kolejnosc jest istotna:
      1. ZAWSZE_GRA - wyjatki, np. "Soundfall" zawiera "sound"
      2. KOSMETYKA_W_TYTULE - konkretne wzorce kluczy, lapieja caly ogon
         tytulu ("... - Scarlet Crest Armor Giveaway"), gdzie samo slowo
         "armor" w srodku zdania nie wystarczy
      3. ODRZUC_SLOWA - pojedyncze slowa

    Zwraca 1 dla gry, 0 dla klucza do kosmetyki.
    """
    t = (tytul or "").lower()
    if not t:
        return False
    for wyjatek in ZAWSZE_GRA:
        if wyjatek in t:
            return True
    for wzorzec in KOSMETYKA_W_TYTULE:
        if wzorzec in t:
            return False
    for slowo in ODRZUC_SLOWA:
        if slowo in t:
            return False
    return True


# ---------------------------------------------------------------- smieci
# Rzeczy, ktore archiwum ma, ale ktore NIE sa paczka gier. Bez tego filtru
# 481 pozycji zawiera trenerki, skanery ROM-ow, konsole homebrew i puste
# placeholdery. Puste zbiory (0 bajtow) to 40+ rekordow smieci.
# Sprawdzone na realnych tytulach z pobrania, nie zgadywane.
# Rzeczy, ktore archiwum ma, ale ktore NIE sa paczka gier.
#
# UWAGA - tu juz bylo 18 wzorcow i wiekszosc byla ZLYM FILTREM.
# Odrzucalem "1g1r", "complete list", "collection no intro" i "redump
# 2024 individual" - a to sa prawdziwe paczki:
#   "Sony PlayStation 2 1G1R Part 2"            1136 GB, prawdziwe gry PS2
#   "Complete List of OG Xbox GAMES"             1100 GB, prawdziwy dump
#   "snes-collection-no-intro"                    4121 plikow, prawdziwe ROM-y
# Filtr skrocil baza z 481 do 373 rekordow, z czego czesc byla dobrymi
# paczkami. Teraz tylko to, co naprawde NIE jest gra:
NIE_GRA_TYTUL = (
    # narzedzia, nie gry
    "scanner", "trainer", "trainers", "cheat", "cheats",
    "rgh", "homebrew", "devkit", "firmware", "bios pack",
    # same listy i bazy, bez gier
    "link list", "links for", "gamelist", "game list", "title list",
    "database", ".dat", "savestate", "save states", "save game",
)

# Rozmiar ponizej ktorego to na pewno nie gra. Najmniejsza pelna gra ROM-ow
# waży kilka MB, wiec 1 MB to juz granica sensu.
MIN_BAJTY = 2 * 1024 * 1024


def czy_zbior_jest_paczka_gier(tytul, bajty, platforma=None):
    """True gdy zbior wyglada na paczke gier.

    Odrzuca: smieci (trenerki, skanery), puste placeholdery, pelne listy
    tytulow bez gier. Nie odrzuca 'PS2 Redump' ani 'Redump ISO', bo to
    sa prawdziwe paczki - tylko ich rozmiar jest kosmiczny.
    """
    t = (tytul or "").lower()

    # 0 bajtow = placeholder albo zbior usuniety
    if bajty is None or bajty < MIN_BAJTY:
        return False

    for smiec in NIE_GRA_TYTUL:
        if smiec in t:
            return False

    return True


def url_szukaj_archiwum(q):
    return ARCHIWUM["szukaj"].format(q=urllib.parse.quote_plus(q))


def url_opis(ident):
    return ARCHIWUM["opisy"].format(ident=ident)
