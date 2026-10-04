from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(debug: bool = False, log_dir: Path | None = None) -> None:
    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_dir / "rn-ai-bot.log", maxBytes=5_000_000, backupCount=3
            )
            handlers.append(file_handler)
        except OSError as exc:
            # A stale root-owned log must never prevent the robot from booting.
            print(f"Warning: file logging disabled: {exc}")
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=handlers, force=True)
    # Third-party websocket debug logs can include authorization headers and
    # raw audio payloads. Never allow them even when application debug is on.
    for noisy_logger in ("websockets", "httpx", "httpcore", "google_genai"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
