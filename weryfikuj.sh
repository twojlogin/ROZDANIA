#!/usr/bin/env bash
# Uruchomienie wlasnym python3. Program korzysta wylacznie ze standardowej
# biblioteki, wiec nie potrzebuje venv ani instalacji czegokolwiek.
set -e
cd "$(dirname "$0")"
exec python3 weryfikuj.py "$@"
