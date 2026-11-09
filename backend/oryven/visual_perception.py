"""Governed visual snapshots for Oryven 0.14.

Captures only the exact top-level window that was fingerprinted before approval.
Image bytes are returned to the caller and are not persisted by this module.
"""
from __future__ import annotations

import base64
from hashlib import sha256
from io import BytesIO
from typing import Callable

from .models import WindowVisualSnapshotIntent
from .window_actions import WindowActions, WindowActionError


class VisualPerceptionError(ValueError):
    pass


class VisualPerception:
    def __init__(self, capture_backend: Callable[[tuple[int, int, int, int]], tuple[bytes, int, int]] | None = None):
        self.capture_backend = capture_backend or self._capture_windows

    @staticmethod
    def _capture_windows(rect: tuple[int, int, int, int]) -> tuple[bytes, int, int]:
        try:
            from PIL import ImageGrab
        except ImportError as exc:
            raise VisualPerceptionError("Instale Pillow para habilitar captura visual no Windows.") from exc
        left, top, right, bottom = rect
        width, height = right-left, bottom-top
        if width <= 0 or height <= 0 or width * height > 8_000_000:
            raise VisualPerceptionError("Janela fora do limite visual permitido.")
        try:
            image = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True)
            output = BytesIO(); image.save(output, format="PNG")
            return output.getvalue(), image.width, image.height
        except Exception as exc:
            raise VisualPerceptionError("Não foi possível capturar a janela autorizada.") from exc

    def capture(self, intent: WindowVisualSnapshotIntent, actions: WindowActions) -> dict:
        window = actions._window(intent.handle)
        actions._check_identity(window, intent)
        try:
            rect = window.rectangle()
            bbox = (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
        except Exception as exc:
            raise VisualPerceptionError("A janela não expôs uma região capturável.") from exc
        raw, width, height = self.capture_backend(bbox)
        if not raw or len(raw) > 12_000_000:
            raise VisualPerceptionError("Snapshot visual vazio ou acima do limite permitido.")
        return {
            "handle": intent.handle,
            "process_id": intent.process_id,
            "width": width,
            "height": height,
            "mime_type": "image/png",
            "sha256": sha256(raw).hexdigest(),
            "image_base64": base64.b64encode(raw).decode("ascii"),
            "persisted": False,
            "message": "Snapshot capturado em memória; não salvo automaticamente no histórico.",
        }
