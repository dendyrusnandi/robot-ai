from __future__ import annotations

from typing import Any

from vision.camera import CameraManager


class VisionManager:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config["camera"]
        self.camera = CameraManager(self.config)
        self.enabled = False

    def start(self) -> bool:
        if not bool(self.config.get("enabled", True)):
            self.enabled = False
            return False
        self.enabled = self.camera.start(float(self.config.get("startup_timeout_seconds", 3)))
        return self.enabled

    def snapshot(self) -> tuple[bytes | None, float]:
        return self.camera.snapshot_jpeg()

    def stop(self) -> None:
        self.camera.stop()
        self.enabled = False
