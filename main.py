from __future__ import annotations

import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from qasync import QEventLoop

from core.event_bus import EventBus
from core.logger import configure_logging
from core.orchestrator import RobotOrchestrator
from core.settings_controller import SettingsController
from face.face_controller import FaceController

ROOT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, dict):
        raise ValueError("config.yaml must contain a mapping")
    return config


def display_context(config: dict[str, Any]) -> dict[str, Any]:
    display = config["display"]
    return {
        "fullscreen": bool(display.get("fullscreen", False)),
        "development": display.get("mode", "development") == "development",
        "width": int(display.get("width", 1280)),
        "height": int(display.get("height", 720)),
        "idleSleepSeconds": int(display.get("idle_sleep_seconds", 45)),
    }


def main() -> int:
    load_dotenv(ROOT / ".env")
    config = load_config(ROOT / "config.yaml")
    configure_logging(bool(config["app"].get("debug")), ROOT / "logs")

    app = QGuiApplication(sys.argv)
    app.setApplicationName(config["app"]["name"])
    if config["display"].get("hide_cursor", False):
        app.setOverrideCursor(QCursor(Qt.CursorShape.BlankCursor))

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    bus = EventBus()
    face = FaceController(bus)
    orchestrator = RobotOrchestrator(config, bus, face)
    settings = SettingsController(ROOT, config)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("faceController", face)
    engine.rootContext().setContextProperty("appConfig", display_context(config))
    engine.rootContext().setContextProperty("settingsController", settings)
    engine.load(QUrl.fromLocalFile(str(ROOT / "face/qml/Main.qml")))
    if not engine.rootObjects():
        return 1

    shutdown_task: asyncio.Task[None] | None = None

    def begin_shutdown() -> None:
        nonlocal shutdown_task
        if shutdown_task is not None:
            return
        shutdown_task = loop.create_task(orchestrator.stop())
        shutdown_task.add_done_callback(lambda _: (app.quit(), loop.stop()))

    def request_shutdown() -> None:
        begin_shutdown()

    app.aboutToQuit.connect(orchestrator.stop_camera_sync)
    app.aboutToQuit.connect(begin_shutdown)
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: request_shutdown())
    if os.getenv("RN_AI_BOT_SMOKE_TEST") == "1":
        QTimer.singleShot(1500, request_shutdown)

    with loop:
        loop.create_task(orchestrator.start())
        loop.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
