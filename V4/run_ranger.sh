#!/usr/bin/env bash
set -euo pipefail

# ======= Percorsi progetto (adatta solo se cambiano) =======
ARDUINO_DIR="$HOME/Desktop/rangter/V4/Arduino_motion"
PY_DIR="$HOME/Desktop/rangter/V4/linux_server"
VENV_DIR="$PY_DIR/venv"
PY_APP="app.py"

# ======= Opzioni =======
SESSION_NAME="rover"                 # nome sessione tmux
ARDUINO_PORT="${ARDUINO_PORT:-}"     # opzionale: export ARDUINO_PORT=/dev/ttyUSB0
FQBN_NEW="arduino:avr:nano"
FQBN_OLD="arduino:avr:nano:cpu=atmega328old"

echo "[1/7] Aggiorno pacchetti di sistema e dipendenze base..."
sudo apt-get update -y
sudo apt-get install -y git curl python3 python3-venv python3-pip python3-opencv tmux

# ======= arduino-cli install =======
if ! command -v arduino-cli >/dev/null 2>&1; then
  echo "[2/7] Installo arduino-cli..."
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh
  sudo mv bin/arduino-cli /usr/local/bin/
  rm -rf bin
fi

echo "[3/7] Configuro arduino-cli e core AVR..."
arduino-cli config init || true
arduino-cli core update-index
arduino-cli core install arduino:avr

# ======= Git update =======
echo "[4/7] Aggiorno repository..."
if [ -d "$ARDUINO_DIR/.git" ]; then
  (cd "$ARDUINO_DIR" && git pull --rebase || true)
fi
if [ -d "$PY_DIR/.git" ]; then
  (cd "$PY_DIR" && git pull --rebase || true)
fi

# ======= Trova la porta dell'Arduino =======
if [ -z "$ARDUINO_PORT" ]; then
  echo "[5/7] Rilevo la porta seriale Arduino..."
  ARDUINO_PORT="$(arduino-cli board list | awk '/tty(ACM|USB)/ {print $1; exit}')"
fi
if [ -z "$ARDUINO_PORT" ]; then
  echo "ERRORE: impossibile trovare una porta Arduino. Imposta ARDUINO_PORT=... e riprova."
  exit 1
fi
echo "Arduino su: $ARDUINO_PORT"

# ======= Compila & carica sketch =======
echo "[6/7] Compilo e carico lo sketch su Arduino..."
arduino-cli compile -b "$FQBN_NEW" "$ARDUINO_DIR"
if ! arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_NEW" "$ARDUINO_DIR"; then
  echo "Upload fallito con bootloader nuovo, provo con quello OLD..."
  arduino-cli compile -b "$FQBN_OLD" "$ARDUINO_DIR"
  arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_OLD" "$ARDUINO_DIR"
fi

# ======= Ambiente Python =======
echo "[7/7] Preparo ambiente Python e avvio server..."
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

# chiudo eventuale sessione precedente e riavvio in tmux
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
  tmux kill-session -t "$SESSION_NAME"
fi
tmux new-session -d -s "$SESSION_NAME" "cd \"$PY_DIR\" && source \"$VENV_DIR/bin/activate\" && python \"$PY_APP\""
echo "Server avviato in tmux:  tmux attach -t $SESSION_NAME"
echo "Apri la console su: http://<IP-del-Pi>:8080/"
