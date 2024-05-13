from io import BytesIO
import time
import picamera

class Camera(object):
    def __init__(self):
        self.stream = BytesIO()
        self.camera = picamera.PiCamera()
        self.camera.resolution = (640, 480)
        self.camera.rotation = 180  # Se necessario, regola la rotazione della fotocamera

    def stream(self):
        for _ in self.camera.capture_continuous(self.stream, 'jpeg', use_video_port=True):
            self.stream.seek(0)
            yield self.stream.read()
            self.stream.seek(0)
            self.stream.truncate()

    def __del__(self):
        self.camera.close()
