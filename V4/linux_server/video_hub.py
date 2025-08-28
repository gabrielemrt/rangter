# -*- coding: utf-8 -*-
import time
import threading
import cv2

# Prova ad importare Picamera2 (CSI/libcamera)
try:
    from picamera2 import Picamera2
    HAS_PICAM2 = True
except Exception:
    HAS_PICAM2 = False


def _try_open_opencv_index(idx, fourcc_pref=None):
    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
    if not cap or not cap.isOpened():
        if cap:
            cap.release()
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
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
        h = int(cv2.CAP_PROP_FRAME_HEIGHT)
        print(f"[cam/opencv] aperta index {idx} ({w}x{h})")
        return cap
    cap.release()
    return None


def _open_any_opencv():
    # prima MJPG, poi YUY2
    for idx in range(4):
        cap = _try_open_opencv_index(idx, cv2.VideoWriter_fourcc(*"MJPG"))
        if cap:
            return cap
    for idx in range(4):
        cap = _try_open_opencv_index(idx, cv2.VideoWriter_fourcc(*"YUY2"))
        if cap:
            return cap
    print("[cam/opencv] nessuna USB camera disponibile")
    return None


class _VideoHub:
    """
    Single-producer / multi-consumer.
    - Se disponibile, usa Picamera2 (CSI/libcamera).
    - Altrimenti, fallback a OpenCV (USB/V4L2).
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.last_jpeg = None
        self.running = False
        self.thread = None

        # Picamera2
        self.use_picam = False
        self.picam = None

        # OpenCV
        self.cap = None

    @property
    def has_frame(self):
        with self.lock:
            return self.last_jpeg is not None

    def _start_picam(self):
        if not HAS_PICAM2:
            return False
        try:
            self.picam = Picamera2()
            # RGB888 per facile encoding JPEG con OpenCV
            config = self.picam.create_preview_configuration(
                main={"format": "RGB888", "size": (640, 480)}
            )
            self.picam.configure(config)
            self.picam.start()
            self.use_picam = True
            print("[cam/picam2] avviata (CSI/libcamera)")
            return True
        except Exception as e:
            print("[cam/picam2] errore avvio:", e)
            self.picam = None
            self.use_picam = False
            return False

    def _stop_picam(self):
        if self.picam:
            try:
                self.picam.stop()
            except Exception:
                pass
        self.picam = None
        self.use_picam = False

    def _start_opencv(self):
        self.cap = _open_any_opencv()
        return self.cap is not None

    def _stop_opencv(self):
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None

    def start(self):
        if self.running:
            return
        self.running = True

        # preferisci CSI se disponibile (Picamera2)
        ok = self._start_picam()
        if not ok:
            # fallback USB/OpenCV
            self._start_opencv()

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            # ---- Picamera2 path ----
            if self.use_picam and self.picam:
                try:
                    frame = self.picam.capture_array()  # RGB888 (H,W,3)
                    ret, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ret:
                        with self.lock:
                            self.last_jpeg = buf.tobytes()
                except Exception as e:
                    print("[cam/picam2] errore:", e)
                    # prova a riavviare picam dopo una breve pausa
                    self._stop_picam()
                    time.sleep(0.5)
                    if not self._start_picam():
                        # fallback a opencv se CSI continua a fallire
                        self._start_opencv()
                time.sleep(0.01)
                continue

            # ---- OpenCV path (USB) ----
            if self.cap is None or not self.cap.isOpened():
                time.sleep(1.0)
                if not self._start_opencv():
                    # nessuna camera USB -> se possibile prova (di nuovo) picam
                    if not self.use_picam:
                        self._start_picam()
                continue

            try:
                ok, frame = self.cap.read()
            except cv2.error:
                ok, frame = False, None

            if not ok or frame is None:
                self._stop_opencv()
                continue

            try:
                ret, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
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
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while True:
            jpg = self.get_jpeg()
            if jpg is None:
                time.sleep(0.05)
                continue
            try:
                yield boundary + jpg + b"\r\n"
            except GeneratorExit:
                break
            except Exception:
                break


video_hub = _VideoHub()
