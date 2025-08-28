# -*- coding: utf-8 -*-
import time
import cv2
import threading

def _try_open_index(idx, fourcc_pref=None):
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap or not cap.isOpened():
        if cap: cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 20)
    if fourcc_pref:
        cap.set(cv2.CAP_PROP_FOURCC, fourcc_pref)
    ok, frame = None, None
    try:
        ok, frame = cap.read()
    except cv2.error:
        ok, frame = False, None
    if ok and frame is not None:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[cam] aperta index {idx} ({w}x{h})")
        return cap
    cap.release()
    return None

def _open_camera_any():
    for idx in range(4):
        cap = _try_open_index(idx, cv2.VideoWriter_fourcc(*'MJPG'))
        if cap: return cap
    for idx in range(4):
        cap = _try_open_index(idx, cv2.VideoWriter_fourcc(*'YUY2'))
        if cap: return cap
    print("[cam] nessuna camera disponibile")
    return None

class _VideoHub:
    def __init__(self):
        self.cap = None
        self.lock = threading.Lock()
        self.last_jpeg = None
        self.running = False
        self.thread = None

    @property
    def has_frame(self):
        with self.lock:
            return self.last_jpeg is not None

    def start(self):
        if self.running: return
        self.running = True
        self.cap = _open_camera_any()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            if self.cap is None or not self.cap.isOpened():
                time.sleep(1.0)
                self.cap = _open_camera_any()
                continue
            try:
                ok, frame = self.cap.read()
            except cv2.error:
                ok, frame = False, None
            if not ok or frame is None:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None
                continue
            try:
                ret, buf = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret:
                    with self.lock:
                        self.last_jpeg = buf.tobytes()
            except cv2.error:
                pass
            time.sleep(0.001)

    def get_jpeg(self):
        with self.lock:
            return self.last_jpeg

    def mjpeg_generator(self):
        boundary = b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
        while True:
            jpg = self.get_jpeg()
            if jpg is None:
                time.sleep(0.05)
                continue
            try:
                yield boundary + jpg + b'\r\n'
            except GeneratorExit:
                break
            except Exception:
                break

video_hub = _VideoHub()
