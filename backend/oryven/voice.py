"""Optional offline Portuguese STT (Vosk) and Windows TTS (SAPI via pyttsx3).

Microphone is OFF until user explicitly clicks 'Ativar microfone'.
No audio is written to disk or sent to a server by this module.
"""
import importlib.util
import json
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Lock, Thread
import sys


class VoiceUnavailable(Exception):
    pass


class Speaker:
    def __init__(self, enabled: bool | None = None):
        self.enabled = (sys.platform == "win32") if enabled is None else enabled
        self._speaking = Event()
        self._queue: Queue[str | None] = Queue(maxsize=15)
        self._thread: Thread | None = None
        self._lock = Lock()
        self._engine = None

    @property
    def speaking(self) -> bool:
        return self._speaking.is_set()

    def say(self, message: str):
        if not self.enabled:
            return
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = Thread(target=self._run, daemon=True, name="oryven-speaker")
                self._thread.start()
        try:
            self._queue.put_nowait(message[:350])
        except Full:
            pass

    def stop(self):
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                break
        if self._engine is not None:
            try:
                self._engine.stop()
            except Exception:
                pass

    def _run(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            self._engine = engine
            engine.setProperty("rate", 165)
            # Prefer a Portuguese voice if installed; otherwise use OS default.
            for voice in engine.getProperty("voices"):
                lang = str(getattr(voice, "languages", "")).lower()
                name = str(getattr(voice, "name", "")).lower()
                if "pt" in lang or "portugu" in name or "brazil" in name:
                    engine.setProperty("voice", voice.id)
                    break
        except Exception:
            self.enabled = False
            return
        while True:
            message = self._queue.get()
            if message is None:
                break
            self._speaking.set()
            try:
                engine.say(message)
                engine.runAndWait()
            except Exception:
                self.enabled = False
                break
            finally:
                self._speaking.clear()


class VoiceListener:
    def __init__(self, model_dir: Path, on_text, on_error, speaker: Speaker):
        self.model_dir = model_dir
        self.on_text = on_text
        self.on_error = on_error
        self.speaker = speaker
        self._stop = Event()
        self._thread: Thread | None = None
        self._lock = Lock()
        self._running = Event()

    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self):
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            if not self.model_dir.is_dir():
                raise VoiceUnavailable(f"Modelo Vosk não encontrado em {self.model_dir}")
            if not importlib.util.find_spec("vosk") or not importlib.util.find_spec("sounddevice"):
                raise VoiceUnavailable("Instale as dependências de voz: pip install -r requirements-voice.txt")
            self._stop.clear()
            self._thread = Thread(target=self._run, daemon=True, name="oryven-microphone")
            self._thread.start()

    def stop(self):
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not __import__("threading").current_thread():
            thread.join(timeout=3)

    def _run(self):
        try:
            from vosk import Model, KaldiRecognizer, SetLogLevel
            import sounddevice as sd
            SetLogLevel(-1)
            model = Model(str(self.model_dir))
            recognizer = KaldiRecognizer(model, 16000)
            audio: Queue[bytes] = Queue(maxsize=30)

            def callback(indata, frames, time_info, status):
                if self._stop.is_set() or self.speaker.speaking:
                    return
                try:
                    audio.put_nowait(bytes(indata))
                except Full:
                    pass  # Drop instead of blocking real-time audio callback.

            with sd.RawInputStream(samplerate=16000, blocksize=4000, dtype="int16", channels=1, callback=callback):
                self._running.set()
                while not self._stop.is_set():
                    try:
                        chunk = audio.get(timeout=0.2)
                    except Empty:
                        continue
                    if self.speaker.speaking:
                        recognizer = KaldiRecognizer(model, 16000)
                        continue
                    if recognizer.AcceptWaveform(chunk):
                        text = json.loads(recognizer.Result()).get("text", "").strip()
                        if text:
                            self.on_text(text)
        except Exception as exc:
            # Never dump audio, credentials or a full traceback to the UI.
            self.on_error(f"Microfone ou reconhecimento indisponível: {type(exc).__name__}")
        finally:
            self._running.clear()
