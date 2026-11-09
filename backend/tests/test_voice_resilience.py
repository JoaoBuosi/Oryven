"""0.6 voice regression tests: no real audio device, network or credentials."""
import httpx
from oryven.elevenlabs_tts import ElevenLabsSpeaker


class Fallback:
    enabled = True
    speaking = False
    def __init__(self):
        self.messages = []
    def say(self, text):
        self.messages.append(text)
    def stop(self):
        pass


class Player:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = []
    def play(self, audio):
        if self.fail:
            raise RuntimeError("unexpected audio driver failure")
        self.messages.append(audio)
    def stop(self):
        pass


def make_voice(handler, player=None, fallback=None):
    return ElevenLabsSpeaker(
        "fake-key", "voice12345", client=httpx.Client(transport=httpx.MockTransport(handler)),
        player=player or Player(), fallback=fallback or Fallback(),
    )


def test_provider_failure_falls_back_without_leaking_details():
    fallback = Fallback()
    voice = make_voice(lambda request: httpx.Response(503), fallback=fallback)
    assert voice.speak_once("teste") is False
    assert fallback.messages == ["teste"]
    assert voice.last_provider == "local-fallback"
    assert voice.last_error == "HTTPStatusError"


def test_unexpected_audio_failure_does_not_kill_fallback():
    fallback = Fallback()
    voice = make_voice(lambda request: httpx.Response(200, content=b"mp3"),
                       player=Player(fail=True), fallback=fallback)
    assert voice.speak_once("ola") is False
    assert fallback.messages == ["ola"]
    assert voice.last_error == "RuntimeError"


def test_provider_recovers_on_next_request():
    count = [0]
    def handler(request):
        count[0] += 1
        return httpx.Response(503) if count[0] == 1 else httpx.Response(200, content=b"mp3")
    fallback, player = Fallback(), Player()
    voice = make_voice(handler, player=player, fallback=fallback)
    assert voice.speak_once("primeira") is False
    assert voice.speak_once("segunda") is True
    assert fallback.messages == ["primeira"]
    assert player.messages == [b"mp3"]
    assert voice.last_error is None
    assert voice.last_provider == "elevenlabs"


def test_fallback_failure_is_reported_without_raising():
    class BrokenFallback(Fallback):
        def say(self, text):
            raise RuntimeError("device failed")
    voice = make_voice(lambda request: httpx.Response(401), fallback=BrokenFallback())
    assert voice.speak_once("teste") is False
    assert voice.last_provider == "unavailable"
    assert voice.last_error == "HTTPStatusError; fallback:RuntimeError"
