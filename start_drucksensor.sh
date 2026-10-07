#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

VENV_PYTHON="$DIR/.venv/bin/python3"
if [ -x "$VENV_PYTHON" ]; then
    PYTHON_BIN="$VENV_PYTHON"
else
    PYTHON_BIN="python3"
fi

"$PYTHON_BIN" drucksensor.py
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo ""
    echo "drucksensor.py wurde mit Fehler beendet (Code $STATUS)."
    echo "Fenster schliessen mit Enter ..."
    read -r
fi
