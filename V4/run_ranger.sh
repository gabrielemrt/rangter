#!/usr/bin/env bash
set -euo pipefail

# ========= Percorsi =========
ARDUINO_DIR="$HOME/Desktop/rangter/V4/Arduino_motion"
PY_DIR="$HOME/Desktop/rangter/V4/linux_server"
VENV_DIR="$PY_DIR/venv"
PY_APP="app.py"

SESSION_NAME="rover"
ARDUINO_PORT="${ARDUINO_PORT:-}"   # es: export ARDUINO_PORT=/dev/ttyACM0
FQBN_NEW="arduino:avr:nano"
FQBN_OLD="arduino:avr:nano:cpu=atmega328old"

# ========= Helpers =========
retry() { # retry <tentativi> <comando...>
  local n=$1; shift
  local i=1
  until "$@"; do
    if (( i >= n )); then return 1; fi
    echo "Retry $i/$n fallito. Riprovo tra 3s..."
    sleep 3
    ((i++))
  done
}

echo "[1/9] Pacchetti base..."
sudo apt-get update -y
sudo apt-get install -y git curl python3 python3-venv python3-pip python3-opencv tmux

# ========= arduino-cli =========
echo "[2/9] arduino-cli..."
if ! command -v arduino-cli >/dev/null 2>&1; then
  INSTALL_DIR="$HOME/Desktop/rangter/V4/bin"
  mkdir -p "$INSTALL_DIR"
  echo "Installo arduino-cli in $INSTALL_DIR"
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh -s -- -b "$INSTALL_DIR"
  export PATH="$INSTALL_DIR:$PATH"
else
  # Potrebbe essere appena installato in ~/Desktop/rangter/V4/bin dal run precedente
  export PATH="$HOME/Desktop/rangter/V4/bin:$PATH"
fi

# ========= Config + Core AVR con retry =========
echo "[3/9] Configuro arduino-cli..."
arduino-cli config init || true
retry 5 arduino-cli core update-index

echo "[4/9] Installo core arduino:avr (con retry)..."
retry 5 arduino-cli core install arduino:avr

echo "[5/9] Librerie Arduino (NeoPixel)..."
# Installation idempotente: se già presente non fallisce
retry 3 arduino-cli lib install "Adafruit NeoPixel"

# ========= Aggiorna repo =========
echo "[6/9] Aggiorno repository..."
if [ -d "$ARDUINO_DIR/.git" ]; then
  (cd "$ARDUINO_DIR" && git pull --rebase || true)
fi
if [ -d "$PY_DIR/.git" ]; then
  (cd "$PY_DIR" && git pull --rebase || true)
fi

# ========= Porta Arduino =========
echo "[7/9] Rilevo la porta seriale Arduino..."
if [ -z "${ARDUINO_PORT}" ]; then
  ARDUINO_PORT="$(arduino-cli board list | awk '/tty(ACM|USB)/ {print $1; exit}')"
fi
if [ -z "${ARDUINO_PORT}" ]; then
  echo "ERRORE: impossibile trovare una porta Arduino. Imposta ARDUINO_PORT=/dev/ttyACM0 (o USB0) e riprova."
  exit 1
fi
echo "Arduino su: ${ARDUINO_PORT}"

# ========= Compila & carica =========
echo "[8/9] Compilo e carico lo sketch..."
arduino-cli compile -b "$FQBN_NEW" "$ARDUINO_DIR"
if ! arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_NEW" "$ARDUINO_DIR"; then
  echo "Upload fallito con bootloader nuovo, provo OLD..."
  arduino-cli compile -b "$FQBN_OLD" "$ARDUINO_DIR"
  arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_OLD" "$ARDUINO_DIR"
fi

# ========= Python env + avvio =========
echo "[9/9] Ambiente Python e avvio server..."
python3 -m venv "$VENV_DIR"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [ -f "$PY_DIR/requirements.txt" ]; then
  pip install --upgrade pip
  pip install -r "$PY_DIR/requirements.txt"
else
  pip install --upgrade pip
  pip install flask pyserial opencv-python
fi

# avvio in tmux (così resta attivo)
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
fi
tmux new-session -d -s "$SESSION_NAME" "cd \"$PY_DIR\" && source \"$VENV_DIR/bin/activate\" && python \"$PY_APP\""
echo "Server avviato in tmux. Logs: tmux attach -t $SESSION_NAME"
echo "Apri la console su: http://<IP-del-Pi>:8080/"
