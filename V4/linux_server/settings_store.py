# -*- coding: utf-8 -*-
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "settings.json"

DEFAULTS = {
    "led_color": [255, 180, 100],     # R,G,B
    "led_brightness": 60,             # 0-255
    "led_on": False,                  # stato ON/OFF persistente
    "motor_default_speed": 150,
    "servo_angles": [90, 90, 90, 90], # Base, Spalla, Gomito, Pinza
}

settings = {}

def load_settings():
    global settings
    if SETTINGS_PATH.exists():
        try:
            disk = json.loads(SETTINGS_PATH.read_text())
        except Exception:
            disk = {}
        # merge con defaults
        s = DEFAULTS.copy()
        s.update(disk)
        settings = s
    else:
        settings = DEFAULTS.copy()

def save_settings():
    try:
        SETTINGS_PATH.write_text(json.dumps(settings, indent=2))
    except Exception as e:
        print("[settings] write error:", e)
