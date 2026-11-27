#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PATTERN="python3 $DIR/serwer.py|python3 serwer.py"

PIDS="$(pgrep -f "$DIR/serwer.py" || true)"
if [ -z "$PIDS" ]; then
  echo "ROZDANIA nie działa."
  exit 0
fi

echo "Zatrzymuję ROZDANIA ($PIDS)..."
kill $PIDS 2>/dev/null || true
sleep 1
STILL="$(pgrep -f "$DIR/serwer.py" || true)"
if [ -n "$STILL" ]; then
  kill -9 $STILL 2>/dev/null || true
fi
echo "Zatrzymane."
