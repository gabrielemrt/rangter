#!/usr/bin/env bash
set -e

echo "[1/6] Aggiorno i pacchetti di sistema..."
sudo apt update
sudo apt -y upgrade

echo "[2/6] Strumenti base..."
sudo apt install -y git curl tmux build-essential pkg-config cmake unzip \
    python3 python3-pip python3-venv python3-dev python3-setuptools python3-wheel

echo "[3/6] Librerie per video/camera..."
# OpenCV da pacchetto
sudo apt install -y python3-opencv v4l-utils ffmpeg

# librerie utili per compilazioni future (jpeg, png, ecc.)
sudo apt install -y libjpeg-dev libpng-dev libtiff-dev libavcodec-dev libavformat-dev libswscale-dev \
    libxvidcore-dev libx264-dev libgtk-3-dev libatlas-base-dev gfortran

echo "[4/6] Libcamera & Picamera2 (per Camera Module CSI)..."
# su Ubuntu ufficiale non sempre c'è picamera2. Se usi Ubuntu Server for Raspberry,
# puoi installare via pip la parte Python.
sudo apt install -y libcamera0 libcamera-apps
pip3 install --upgrade pip
pip3 install picamera2 --extra-index-url https://www.piwheels.org/simple

echo "[5/6] Librerie Python del progetto..."
pip3 install flask pyserial

echo "[6/6] Pulizia..."
sudo apt -y autoremove
echo "---------------------------------------------------------"
echo "Dipendenze installate. Ora puoi avviare il progetto:"
echo "  cd ~/Desktop/rangter/V4/linux_server"
echo "  python3 app.py"
echo "---------------------------------------------------------"
