#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import threading
from flask import Flask, render_template, Response, request, jsonify

from settings_store import settings, load_settings, save_settings, DEFAULTS
from video_hub import video_hub
from serial_bridge import SerialBridge

app = Flask(__name__)

# --- Bootstrap: settings + serial + video ---
load_settings()                # carica settings.json in memoria
bridge = SerialBridge()        # gestione seriale/READY/applicazione settaggi
bridge.open()                  # apre seriale e attende READY (con timeout) + schedule apply
video_hub.start()              # avvia thread lettura camera (single producer)

# ---------- ROUTES ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vr')
def vr():
    return render_template('vr.html')

@app.route('/video_feed')
def video_feed():
    return Response(video_hub.mjpeg_generator(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/health')
def health():
    video_ok  = video_hub.has_frame
    serial_ok = bridge.is_open
    return jsonify(video=video_ok, serial=serial_ok, ok=(video_ok and serial_ok))

# ---- Comandi seriali inoltrati al Nano ----
@app.route('/cmd', methods=['POST'])
def cmd():
    data = request.get_json(silent=True) or {}
    c = (data.get('c') or '').strip()
    if not c:
        return jsonify(ok=False, err="missing command"), 400
    if not bridge.is_open:
        return jsonify(ok=False, err="serial not available"), 503

    # Aggiorna stato luci in settings se ON/OFF
    cu = c.upper()
    if cu == "LED ON":
        settings["led_on"] = True
        save_settings()
    elif cu == "LED OFF":
        settings["led_on"] = False
        save_settings()

    # Se è la prima volta e arriva LED ON, applica settaggi prima di inoltrare
    if cu == "LED ON" and not bridge.applied_once:
        bridge.apply_settings_now(settings)
        time.sleep(0.02)

    ok, err = bridge.write_line(c)
    if not ok:
        return jsonify(ok=False, err=err or "write failed"), 500
    return jsonify(ok=True)

# ---- Settings persistenti ----
@app.route('/settings', methods=['GET'])
def get_settings():
    return jsonify(settings)

@app.route('/settings', methods=['POST'])
def set_settings():
    data = request.get_json(silent=True) or {}
    changed = False
    for k in ("led_color", "led_brightness", "led_on",
              "motor_default_speed", "servo_angles"):
        if k in data:
            settings[k] = data[k]
            changed = True
    if changed:
        save_settings()
    if data.get("apply"):
        bridge.apply_settings_now(settings)
    return jsonify(ok=True, settings=settings)

# Facoltativo: applica subito (usato per debug/UI)
@app.route('/apply_settings_now', methods=['POST'])
def apply_settings_now():
    bridge.apply_settings_now(settings)
    return jsonify(ok=True)

if __name__ == '__main__':
    # ascolta sulla LAN
    app.run(host='0.0.0.0', port=8080, threaded=True)
