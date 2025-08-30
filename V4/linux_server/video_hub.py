# -*- coding: utf-8 -*-
import time
import threading
import cv2

# Prova Picamera2 (CSI/libcamera)
try:
    from picamera2 import Picamera2
    HAS_PICAM2 = True
except Exception:
    HAS_PICAM2 = False


class _VideoHub:
    """
    Single-producer / multi-consumer MJPEG.
    - Preferisce Picamera2 (CSI). Fallback a OpenCV (USB).
    - Chiude SEMPRE le risorse prima di riaprire.
    - Backoff esponenziale su errori: evita "Too many open files".
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.last_jpeg = None
        self.running = False
        self.thread = None

        # Stato Picamera2
        self.use_picam = False
        self.picam = None
        self.picam_next_retry_ts = 0.0
        self.picam_fail_streak = 0

        # Stato OpenCV USB
        self.cap = None
        self.cv_next_retry_ts = 0.0
        self.cv_fail_streak = 0

    @property
    def has_frame(self):
        with self.lock:
            return self.last_jpeg is not None

    # ---------- Picamera2 ----------
    def _start_picam(self):
        if not HAS_PICAM2:
            return False
        now = time.time()
        if now < self.picam_next_retry_ts:
            return False
        try:
            self.picam = Picamera2()
            cfg = self.picam.create_preview_configuration(
                main={"format": "RGB888", "size": (640, 480)}
            )
            self.picam.configure(cfg)
            self.picam.start()
            self.use_picam = True
            self.picam_fail_streak = 0
            print("[cam/picam2] avviata (CSI)")
            return True
        except Exception as e:
            self.use_picam = False
            self._safe_close_picam()
            self.picam_fail_streak += 1
            backoff = min(2 ** self.picam_fail_streak, 30)  # max 30s
            self.picam_next_retry_ts = time.time() + backoff
            print(f"[cam/picam2] errore avvio: {e} (retry in {backoff}s)")
            return False

    def _safe_close_picam(self):
        if self.picam:
            try:
                try:
                    self.picam.stop()
                except Exception:
                    pass
                # picamera2.close() può lanciare se preview non inizializzato → ignora
                try:
                    self.picam.close()
                except Exception:
                    pass
            finally:
                self.picam = None
        self.use_picam = False

    # ---------- OpenCV USB ----------
    def _try_open_opencv_index(self, idx, fourcc_pref=None):
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
            print(f"[cam/opencv] aperta index {idx}")
            return cap
        cap.release()
        return None

    def _open_any_opencv(self):
        # prima MJPG, poi YUY2
        for idx in range(4):
            cap = self._try_open_opencv_index(idx, cv2.VideoWriter_fourcc(*"MJPG"))
            if cap:
                return cap
        for idx in range(4):
            cap = self._try_open_opencv_index(idx, cv2.VideoWriter_fourcc(*"YUY2"))
            if cap:
                return cap
        print("[cam/opencv] nessuna USB camera disponibile")
        return None

    def _start_opencv(self):
        now = time.time()
        if now < self.cv_next_retry_ts:
            return False
        self.cap = self._open_any_opencv()
        if self.cap is None:
            self.cv_fail_streak += 1
            backoff = min(2 ** self.cv_fail_streak, 30)
            self.cv_next_retry_ts = time.time() + backoff
            return False
        self.cv_fail_streak = 0
        return True

    def _stop_opencv(self):
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
        self.cap = None

    # ---------- Avvio / ciclo ----------
    def start(self):
        if self.running:
            return
        self.running = True

        # Prova CSI prima, con backoff già attivo
        started = self._start_picam()
        if not started:
            self._start_opencv()

        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            # ---- PICAMERA2 ----
            if self.use_picam and self.picam:
                try:
                    frame = self.picam.capture_array()  # RGB888
                    ret, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    if ret:
                        with self.lock:
                            self.last_jpeg = buf.tobytes()
                except Exception as e:
                    print(f"[cam/picam2] errore runtime: {e}")
                    self._safe_close_picam()
                    # non riparto subito: backoff gestito da _start_picam
                time.sleep(0.01)
                # se abbiamo chiuso picam, prova a riaprirla quando scatta il retry;
                # altrimenti prova il fallback USB
                if not self.use_picam:
                    if not self._start_picam():
                        self._start_opencv()
                continue

            # ---- OPENCV USB ----
            if self.cap is None or not self.cap.isOpened():
                # preferisci sempre CSI: se è tempo di riprovare Picam, riprovala
                if self._start_picam():
                    continue
                # altrimenti tenta USB con backoff
                self._start_opencv()
                time.sleep(0.2)
                continue

            try:
                ok, frame = self.cap.read()
            except cv2.error:
                ok, frame = False, None

            if not ok or frame is None:
                self._stop_opencv()
                time.sleep(0.2)
                continue

            try:
                ret, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if ret:
                    with self.lock:
                        self.last_jpeg = buf.tobytes()
            except cv2.error:
                pass

            time.sleep(0.001)

    # ---------- API per Flask ----------
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
