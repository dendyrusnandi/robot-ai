from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:  # Camera remains optional; face/audio must still start.
    cv2 = None


class CameraManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self._frame: np.ndarray | None = None
        self._frame_time = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._capture: Any | None = None
        self._available = False
        self.logger = logging.getLogger("VISION")

    @property
    def available(self) -> bool:
        return self._available

    def start(self, timeout: float = 3.0) -> bool:
        if self._thread is not None:
            return self._available
        self._stop.clear()
        self._ready.clear()
        self._available = False
        self._thread = threading.Thread(target=self._capture_loop, name="camera", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        if not self._available:
            self.logger.warning("vision disabled: camera did not become ready")
            self.stop()
        return self._available

    def _capture_loop(self) -> None:
        if cv2 is None:
            self.logger.error("camera unavailable: install opencv-python-headless")
            self._ready.set()
            return
        device = self.config.get("device", 0)
        capture = cv2.VideoCapture(device)
        self._capture = capture
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, int(self.config.get("width", 1280)))
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, int(self.config.get("height", 720)))
        capture.set(cv2.CAP_PROP_FPS, int(self.config.get("capture_fps", 30)))
        if not capture.isOpened():
            self.logger.error("camera unavailable device=%s", device)
            capture.release()
            self._capture = None
            self._ready.set()
            return
        while not self._stop.is_set():
            ok, frame = capture.read()
            if not ok:
                self.logger.warning("camera frame read failed")
                time.sleep(0.1)
                continue
            if not self._available:
                self._available = True
                self._ready.set()
                self.logger.info("camera started device=%s", device)
            with self._lock:
                self._frame = frame
                self._frame_time = time.time()
        capture.release()
        self._capture = None
        self._available = False
        self._ready.set()
        self.logger.info("camera stopped")

    def latest_frame(self) -> tuple[np.ndarray | None, float]:
        with self._lock:
            return (None if self._frame is None else self._frame.copy(), self._frame_time)

    def snapshot_jpeg(self) -> tuple[bytes | None, float]:
        frame, timestamp = self.latest_frame()
        if frame is None:
            return None, 0.0
        quality = int(self.config.get("jpeg_quality", 80))
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            return None, timestamp
        self.logger.info("snapshot %sx%s", frame.shape[1], frame.shape[0])
        return encoded.tobytes(), timestamp

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            # VideoCapture must be released by the capture thread itself;
            # releasing it cross-thread can abort inside OpenCV/V4L2.
            self._thread.join(timeout=3)
            self._thread = None
        self._available = False
