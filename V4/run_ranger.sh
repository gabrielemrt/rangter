#!/usr/bin/env bash
set -euo pipefail

# ========= Percorsi progetto =========
ARDUINO_DIR="$HOME/Desktop/rangter/V4/Arduino_motion"
PY_DIR="$HOME/Desktop/rangter/V4/linux_server"
VENV_DIR="$PY_DIR/venv"
PY_APP="app.py"

SESSION_NAME="rover"
ARDUINO_PORT="${ARDUINO_PORT:-}"   # es: export ARDUINO_PORT=/dev/ttyACM0
FQBN_NEW="arduino:avr:nano"
FQBN_OLD="arduino:avr:nano:cpu=atmega328old"

INSTALL_DIR="$HOME/Desktop/rangter/V4/bin"   # dove abbiamo installato arduino-cli
export PATH="$INSTALL_DIR:$PATH"

retry() { local n=$1; shift; local i=1; until "$@"; do
  if (( i >= n )); then return 1; fi
  echo "Retry $i/$n fallito. Riprovo tra 3s..."; sleep 3; ((i++))
done; }

echo "[1/10] Pacchetti base..."
sudo apt-get update -y
sudo apt-get install -y git curl python3 python3-venv python3-pip python3-opencv tmux

echo "[2/10] arduino-cli..."
if ! command -v arduino-cli >/dev/null 2>&1; then
  mkdir -p "$INSTALL_DIR"
  echo "Installo arduino-cli in $INSTALL_DIR"
  curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | sh -s -- -b "$INSTALL_DIR"
fi

echo "[3/10] Config arduino-cli..."
arduino-cli config init || true

ONLINE_OK=false
echo "[4/10] TENTO install core arduino:avr (online, con retry)..."
if retry 5 arduino-cli core update-index && retry 5 arduino-cli core install arduino:avr; then
  ONLINE_OK=true
  echo "✓ Core AVR installato online."
else
  echo "⚠️  Download core AVR fallito ripetutamente. Passo alla modalità OFFLINE."
fi

if [ "$ONLINE_OK" != true ]; then
  echo "[5/10] OFFLINE MODE: installo core + toolchain via APT e li preparo per arduino-cli…"
  # Installa IDE classico + toolchain (contiene core e avr-gcc/avrdude)
  sudo apt-get install -y arduino gcc-avr avr-libc avrdude

  # Prepara sketchbook/hardware utente con core e tools presi dal sistema
  SKETCHBOOK="$HOME/Arduino"
  mkdir -p "$SKETCHBOOK/hardware/arduino" "$SKETCHBOOK/hardware/tools"
  # Copia core
  if [ -d "/usr/share/arduino/hardware/arduino/avr" ]; then
    rsync -a --delete "/usr/share/arduino/hardware/arduino/avr/" "$SKETCHBOOK/hardware/arduino/avr/"
  else
    echo "ERRORE: core /usr/share/arduino/hardware/arduino/avr non trovato."; exit 1
  endfi

  # Copia toolchain (avr-gcc, avrdude, etc.) nella struttura attesa
  if [ -d "/usr/share/arduino/hardware/tools/avr" ]; then
    rsync -a --delete "/usr/share/arduino/hardware/tools/avr/" "$SKETCHBOOK/hardware/tools/avr/"
  else
    # fallback: su alcune distro i binari stanno in /usr/bin; creiamo una struttura minima
    mkdir -p "$SKETCHBOOK/hardware/tools/avr/bin"
    for b in avr-gcc avr-g++ avr-ar avr-objcopy avr-objdump avr-size avr-strip avrdude; do
      if command -v "$b" >/dev/null 2>&1; then
        ln -sf "$(command -v $b)" "$SKETCHBOOK/hardware/tools/avr/bin/$b"
      fi
    done
  fi

  # Punta lo sketchbook dell'arduino-cli al nostro
  mkdir -p "$HOME/.arduino15"
  CLI_YAML="$HOME/.arduino15/arduino-cli.yaml"
  if ! grep -q "directories:" "$CLI_YAML" 2>/dev/null; then
    cat >> "$CLI_YAML" <<EOF
directories:
  user: $SKETCHBOOK
EOF
  else
    # aggiorna/garantisce la chiave user
    awk -v sk="$SKETCHBOOK" '
      BEGIN{done=0}
      /^directories:/ {print; print "  user: " sk; done=1; next}
      {print}
      END{if(!done){print "directories:\n  user: " sk}}
    ' "$CLI_YAML" > "$CLI_YAML.tmp" && mv "$CLI_YAML.tmp" "$CLI_YAML"
  fi

  echo "✓ Core e toolchain locali pronti in $SKETCHBOOK/hardware."
  echo "Verifica piattaforme viste dall'arduino-cli:"
  arduino-cli core list || true
fi

echo "[6/10] Libreria Adafruit NeoPixel (se online disponibile)…"
# Non essenziale per la compilazione se già presente nello sketchbook.
arduino-cli lib install "Adafruit NeoPixel" || echo "Non sono riuscito a installare la libreria online: proseguo (se serve, copiala manualmente in $HOME/Arduino/libraries)."

echo "[7/10] Aggiorno repository progetto..."
if [ -d "$ARDUINO_DIR/.git" ]; then (cd "$ARDUINO_DIR" && git pull --rebase || true); fi
if [ -d "$PY_DIR/.git" ]; then (cd "$PY_DIR" && git pull --rebase || true); fi

echo "[8/10] Rilevo porta Arduino..."
if [ -z "${ARDUINO_PORT}" ]; then
  ARDUINO_PORT="$(arduino-cli board list | awk '/tty(ACM|USB)/ {print $1; exit}')"
fi
if [ -z "${ARDUINO_PORT}" ]; then
  echo "ERRORE: impossibile trovare una porta Arduino. Esempio: export ARDUINO_PORT=/dev/ttyACM0"; exit 1
fi
echo "Arduino su: ${ARDUINO_PORT}"

echo "[9/10] Compilo e carico lo sketch..."
set +e
arduino-cli compile -b "$FQBN_NEW" "$ARDUINO_DIR"
RC=$?
set -e
if [ $RC -ne 0 ]; then
  echo "Compilazione con profilo NEW fallita, riprovo con OLD…"
  arduino-cli compile -b "$FQBN_OLD" "$ARDUINO_DIR"
  arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_OLD" "$ARDUINO_DIR"
else
  if ! arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_NEW" "$ARDUINO_DIR"; then
    echo "Upload NEW fallito, riprovo con OLD…"
    arduino-cli compile -b "$FQBN_OLD" "$ARDUINO_DIR"
    arduino-cli upload -p "$ARDUINO_PORT" -b "$FQBN_OLD" "$ARDUINO_DIR"
  fi
fi

echo "[10/10] Ambiente Python e avvio server (tmux)…"
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

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then tmux kill-session -t "$SESSION_NAME"; fi
tmux new-session -d -s "$SESSION_NAME" "cd \"$PY_DIR\" && source \"$VENV_DIR/bin/activate\" && python \"$PY_APP\""
echo "✓ Server avviato in tmux. Logs:  tmux attach -t $SESSION_NAME"
echo "Apri la console: http://<IP-del-Pi>:8080/"
