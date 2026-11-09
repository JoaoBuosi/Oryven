"""Opt-in ElevenLabs TTS for the Windows MVP.

The API key remains on the Python side; only reply text is sent to ElevenLabs.
MCI is used for MP3 playback on Windows without extra native audio libraries.
"""
from __future__ import annotations

from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
from tempfile import NamedTemporaryFile
import re
import secrets
import sys

import httpx

from .voice import Speaker


class TTSUnavailable(Exception):
    pass


class WindowsMp3Player:
    def __init__(self):
        self._alias = None
        self._lock = Lock()

    @staticmethod
    def _command(command: str):
        import ctypes
        result = ctypes.windll.winmm.mciSendStringW(command, None, 0, None)
        if result != 0:
            raise TTSUnavailable(f"A reprodução de áudio falhou (código MCI {result}).")

    def play(self, audio: bytes):
        if sys.platform != "win32":
            raise TTSUnavailable("Reprodução MP3 nativa disponível apenas no Windows.")
        if not audio or len(audio) > 5_000_000:
            raise TTSUnavailable("Resposta de áudio vazia ou excessivamente grande.")
        path: Path | None = None
        alias = "oryven_" + secrets.token_hex(7)
        try:
            with NamedTemporaryFile(prefix="oryven-", suffix=".mp3", delete=False) as f:
                path = Path(f.name)
                f.write(audio)
            # Alias unique per call. Do not play untrusted user-selected paths.
            self._command(f'open "{path}" type mpegvideo alias {alias}')
            with self._lock:
                self._alias = alias
            self._command(f"play {alias} wait")
        finally:
            try:
                self._command(f"close {alias}")
            except TTSUnavailable:
                pass
            with self._lock:
                if self._alias == alias:
                    self._alias = None
            if path is not None:
                path.unlink(missing_ok=True)

    def stop(self):
        with self._lock:
            alias = self._alias
        if alias:
            try:
                self._command(f"stop {alias}")
            except TTSUnavailable:
                pass


class ElevenLabsSpeaker:
    """Queue serialized replies, with a local Windows SAPI fallback."""

    def __init__(self, api_key: str, voice_id: str, model_id: str = "eleven_flash_v2_5",
                 *, client=None, player=None, fallback: Speaker | None = None):
        if not api_key.strip() or not voice_id.strip():
            raise ValueError("A voz ElevenLabs exige API key e Voice ID.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", voice_id):
            raise ValueError("Voice ID inválido: apenas letras, números, _ e -.")
        self.api_key = api_key
        self.voice_id = voice_id
        self.model_id = model_id
        self._client = client or httpx.Client(timeout=httpx.Timeout(25.0, connect=6.0))
        self._player = player or WindowsMp3Player()
        self.fallback = fallback or Speaker()
        self.enabled = True
        self.provider = "elevenlabs"
        self._speaking = Event()
        self._queue: Queue[str] = Queue(maxsize=8)
        self._thread: Thread | None = None
        self._lock = Lock()
        self._stop = Event()
        self.last_error: str | None = None
        self.last_provider: str | None = None

    @property
    def speaking(self):
        return self._speaking.is_set() or self.fallback.speaking

    def say(self, message: str):
        text = message.strip()[:350]
        if not text:
            return
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._stop.clear()
                self._thread = Thread(target=self._run, daemon=True, name="oryven-elevenlabs")
                self._thread.start()
        try:
            self._queue.put_nowait(text)
        except Full:
            pass

    def speak_once(self, message: str) -> bool:
        """Return True on ElevenLabs playback, False if local voice is used."""
        try:
            # Only a fixed HTTPS API host; no user-supplied URL or query parameter.
            response = self._client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                params={"output_format": "mp3_44100_128"},
                json={"text": message, "model_id": self.model_id},
            )
            response.raise_for_status()
            if self._stop.is_set():
                return False
            self._player.play(response.content)
            self.last_error = None
            self.last_provider = "elevenlabs"
            return True
        except Exception as exc:
            # Never expose exception messages: HTTP failures can include sensitive data.
            self.last_error = type(exc).__name__
            self.last_provider = "local-fallback"
            if not self._stop.is_set():
                try:
                    self.fallback.say(message)
                except Exception as fallback_exc:
                    self.last_error = f"{type(exc).__name__}; fallback:{type(fallback_exc).__name__}"
                    self.last_provider = "unavailable"
            return False

    def _run(self):
        while not self._stop.is_set():
            try:
                message = self._queue.get(timeout=0.25)
            except Empty:
                break
            self._speaking.set()
            try:
                self.speak_once(message)
            except Exception as exc:
                # Keep worker alive for subsequent requests even if a provider misbehaves.
                self.last_error = type(exc).__name__
                self.last_provider = "unavailable"
            finally:
                self._speaking.clear()

    def stop(self):
        self._stop.set()
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                break
        self._player.stop()
        if hasattr(self.fallback, "stop"):
            self.fallback.stop()
