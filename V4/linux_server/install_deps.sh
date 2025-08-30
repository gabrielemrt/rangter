#!/usr/bin/env bash
# Installazione dipendenze per Rover su Raspberry Pi OS (Bookworm)
# - Tollerante agli errori: continua anche se qualche pacchetto non esiste
# - Installa libcamera + picamera2 (per Camera Module 3 / CSI)
# - Installa OpenCV, Flask, PySerial
# - Prepara un venv in ~/Desktop/rangter/V4/linux_server/venv (se la cartella esiste)

set -u

log(){ printf "\n[%s] %s\n" "$(date +%H:%M:%S)" "$*"; }
OK_LIST=(); SKIP_LIST=(); FAIL_LIST=()

apt_install() {
  for PKG in "$@"; do
    if apt-cache policy "$PKG" 2>/dev/null | grep -q 'Candidate:'; then
      log "Installo $PKG ..."
      if sudo apt-get install -y "$PKG"; then
        OK_LIST+=("$PKG")
      else
        FAIL_LIST+=("$PKG")
      fi
    else
      log "Pacchetto non trovato nei repo: $PKG (skip)"
      SKIP_LIST+=("$PKG")
    fi
  done
}

pip_install() {
  local BIN="pip3"
  command -v "$BIN" >/dev/null 2>&1 || BIN="python3 -m pip"
  for P in "$@"; do
    log "pip install $P ..."
    if $BIN install --no-cache-dir "$P"; then
      OK_LIST+=("pip:$P")
    else
      FAIL_LIST+=("pip:$P")
    fi
  done
}

# ---------------- Inizio ----------------
log "[0/7] Verifico repo Raspberry Pi"
if ! grep -Rq "archive.raspberrypi.com" /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
  log "Aggiungo repository Raspberry Pi"
  . /etc/os-release
  echo "deb http://archive.raspberrypi.com/debian ${VERSION_CODENAME} main" | sudo tee /etc/apt/sources.list.d/raspi.list
fi

log "[1/7] Aggiorno sistema"
sudo apt-get update -y || true
sudo apt-get -y upgrade || true

log "[2/7] Strumenti base"
apt_install git curl tmux build-essential pkg-config cmake unzip \
            python3 python3-pip python3-venv python3-dev python3-setuptools python3-wheel

log "[3/7] Multimedia / OpenCV lato sistema"
apt_install python3-opencv v4l-utils ffmpeg \
            libjpeg-dev libpng-dev libtiff-dev libavcodec-dev libavformat-dev libswscale-dev \
            libxvidcore-dev libx264-dev libgtk-3-dev libatlas-base-dev gfortran

log "[4/7] Stack camera (CSI / libcamera per Pi)"
# Su Raspberry Pi OS i pacchetti corretti sono questi
apt_install libcamera0 libcamera-apps python3-picamera2

# Abilita auto-detect camera se non presente
if ! grep -q "^camera_auto_detect=1" /boot/firmware/config.txt 2>/dev/null; then
  log "Abilito camera_auto_detect=1 in /boot/firmware/config.txt"
  echo "camera_auto_detect=1" | sudo tee -a /boot/firmware/config.txt >/dev/null
fi

# Assicura appartenenza al gruppo 'video'
if ! id -nG "$USER" | grep -qw video; then
  log "Aggiungo $USER al gruppo 'video' (richiede logout/login)"
  sudo usermod -aG video "$USER" || true
fi

log "[5/7] Python: aggiorno pip e dipendenze app"
pip3 install --upgrade pip || true

# Prepara (se esiste) la cartella del progetto per venv
APP_DIR="$HOME/Desktop/rangter/V4/linux_server"
if [ -d "$APP_DIR" ]; then
  log "Creo venv in $APP_DIR/venv"
  python3 -m venv "$APP_DIR/venv" || true
  # shellcheck disable=SC1091
  source "$APP_DIR/venv/bin/activate" 2>/dev/null || true
  if [ -f "$APP_DIR/requirements.txt" ]; then
    log "requirements.txt trovato: installo dipendenze"
    pip_install -r "$APP_DIR/requirements.txt"
  else
    log "requirements.txt non trovato: installo dipendenze base per app Flask"
    pip_install flask pyserial
  fi
else
  log "Cartella progetto non trovata ($APP_DIR). Installo dipendenze globali base"
  pip_install flask pyserial
fi

log "[6/7] (Opzionale) Arduino CLI (se ti serve programmare il Nano da Pi)"
# scommenta se vuoi installare automaticamente arduino-cli
# INSTALL_ARDUINO=1
if [ "${INSTALL_ARDUINO:-0}" = "1" ]; then
  if ! command -v arduino-cli >/dev/null 2>&1; then
    BIN_DIR="$HOME/bin"
    mkdir -p "$BIN_DIR"
    log "Installo arduino-cli in $BIN_DIR"
    curl -fsSL https://raw.githubusercontent.com/arduino/arduino-cli/master/install.sh | BINDIR="$BIN_DIR" sh || true
    echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
    source "$HOME/.bashrc" || true
  else
    log "arduino-cli già presente"
  fi
fi

log "[7/7] Pulizia"
sudo apt-get -y autoremove || true

log "========== REPORT =========="
printf "OK:   %s\n" "${OK_LIST[*]:-—}"
printf "SKIP: %s\n" "${SKIP_LIST[*]:-—}"
printf "FAIL: %s\n" "${FAIL_LIST[*]:-—}"

cat <<'EOF'

Note:
- Per la Camera Module 3 (CSI) usa i tool:
    libcamera-hello --list-cameras
    libcamera-hello
  Se non vedi nulla, riavvia il Pi:
    sudo reboot

- Per avviare il server (se la cartella esiste):
    cd ~/Desktop/rangter/V4/linux_server
    source venv/bin/activate
    python app.py

- Se hai aggiunto l'utente al gruppo 'video', fai logout/login o riapri la sessione SSH.
EOF
