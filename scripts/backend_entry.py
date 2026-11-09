"""Production entry point for the packaged Oryven backend sidecar.

Writes local rotating diagnostics without logging secrets or HTTP bodies.
"""
from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

import uvicorn
from oryven.api import app
from oryven.release_info import VERSION


def _data_dir() -> Path:
    return Path(os.environ.get("ORYVEN_DATA_DIR", str(Path.home() / ".oryven-mvp"))).expanduser()


def configure_logging() -> Path:
    log_dir = _data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "oryven.log"
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Avoid duplicate handlers in development reload/import scenarios.
    if not any(isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", "") == str(path.resolve()) for h in root.handlers):
        handler = RotatingFileHandler(path, maxBytes=2_000_000, backupCount=4, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        root.addHandler(handler)
    logging.getLogger("oryven.release").info("backend_start version=%s", VERSION)
    return path


def install_crash_hook() -> None:
    previous = sys.excepthook

    def hook(exc_type, exc_value, exc_traceback):
        logging.getLogger("oryven.crash").critical("unhandled_exception type=%s message=%s", getattr(exc_type, "__name__", "Exception"), str(exc_value), exc_info=(exc_type, exc_value, exc_traceback))
        try:
            marker = _data_dir() / "logs" / "last_crash.json"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({
                "version": VERSION,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "exception_type": getattr(exc_type, "__name__", "Exception"),
                "message": str(exc_value)[:500],
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        previous(exc_type, exc_value, exc_traceback)

    sys.excepthook = hook


if __name__ == '__main__':
    configure_logging()
    install_crash_hook()
    uvicorn.run(app, host='127.0.0.1', port=8765, reload=False, log_config=None)
