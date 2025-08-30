#!/usr/bin/env bash
# Installazione dipendenze per Rover (Ubuntu / RPi OS compatibile)
# - Non si ferma se alcuni pacchetti non esistono (es. libcamera-apps su Ubuntu)

set -u

log() { printf "\n[%s] %s\n" "$(date +%H:%M:%S)" "$*"; }
OK_LIST=()
SKIP_LIST=()
FAIL_LIST=()

apt_install() {
  # usage: apt_install pkg1 [pkg2 ...]
  for PKG in "$@"; do
    if apt-cache policy "$PKG" 2>/dev/null | grep -q 'Candidate:'; then
      log "Installo $PKG ..."
      if sudo apt-get install -y "$PKG"; then
        OK_LIST+=("$PKG")
      else
        FAIL_LIST+=("$PKG")
      fi
    else
      log "Pacchetto non trovato in repo: $PKG (lo salto)"
      SKIP_LIST+=("$PKG")
    fi
  done
}

pip_install() {
  # usage: pip_install pkg1 [pkg2 ...]  (non blocca)
  for P in "$@"; do
    log "pip install $P ..."
    if pip3 install --no-cache-dir "$P"; then
      OK_LIST+=("pip:$P")
    else
      FAIL_LIST+=("pip:$P")
    fi
  done
}

log "[1/6] Aggiornamento sistema..."
sudo apt-get update -y || true
sudo apt-get -y upgrade || true

log "[2/6] Strumenti base..."
apt_install git curl tmux build-essential pkg-config cmake unzip \
            python3 python3-pip python3-venv python3-dev python3-setuptools python3-wheel

log "[3/6] Video / multimedia / OpenCV lato sistema..."
apt_install python3-opencv v4l-utils ffmpeg \
            libjpeg-dev libpng-dev libtiff-dev libavcodec-dev libavformat-dev libswscale-dev \
            libxvidcore-dev libx264-dev libgtk-3-dev libatlas-base-dev gfortran

log "[4/6] Stack camera (CSI / libcamera) — prova ciò che esiste sulla tua distro..."
# Su Ubuntu troverai tipicamente: libcamera0.2, libcamera-tools, gstreamer1.0-libcamera
# Su Raspberry Pi OS: libcamera0, libcamera-apps
apt_install libcamera0 libcamera0.2 libcamera-tools gstreamer1.0-libcamera libcamera-apps

log "[5/6] Python: aggiorno pip e installo librerie del progetto..."
pip3 install --upgrade pip || true
# Dipendenze applicative
pip_install flask pyserial

# Picamera2: su Ubuntu potrebbe NON avere wheel pronta; tentiamo e non blocchiamo
# (su RPi OS funziona; su Ubuntu spesso servono binding libcamera python precompilati)
pip_install picamera2

log "[6/6] Pulizia..."
sudo apt-get -y autoremove || true

log "========== REPORT =========="
printf "OK:   %s\n" "${OK_LIST[*]:-—}"
printf "SKIP: %s\n" "${SKIP_LIST[*]:-—}"
printf "FAIL: %s\n" "${FAIL_LIST[*]:-—}"

cat <<'EOF'

Note importanti:
- Se stai usando una WEBCAM USB, lo stream funziona già con OpenCV (python3-opencv).
- Se stai usando la **Camera Module 3 (CSI)** su Ubuntu:
  * prova ad installare: libcamera0.2, libcamera-tools, gstreamer1.0-libcamera (già tentato sopra).
  * la libreria **Picamera2** via pip può fallire su Ubuntu; il nostro codice comunque
    funziona anche solo USB. Se vuoi usare CSI su Ubuntu e Picamera2 non si installa,
    ti consiglio Raspberry Pi OS Bookworm (supporto migliore alla CSI).
- Per avviare il progetto:
    cd ~/Desktop/rangter/V4/linux_server
    python3 app.py
EOF
