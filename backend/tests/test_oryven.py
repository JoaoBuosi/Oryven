from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.elevenlabs_tts import ElevenLabsSpeaker
from oryven.executor import BrowserExecutor
from oryven.governance import ApprovalError, ApprovalStore
from oryven.intent import parse_search, strip_wake
from oryven.models import SearchIntent


class FakeSpeaker:
    enabled = True
    speaking = False
    provider = "fake"
    def __init__(self): self.messages = []; self.stopped = False
    def say(self, message): self.messages.append(message)
    def stop(self): self.stopped = True


class FakeListener:
    running = False
    def start(self): self.running = True
    def stop(self): self.running = False


def make_core(tmp_path):
    opened = []
    speaker = FakeSpeaker()
    listener = FakeListener()
    core = OryvenCore(Settings(data_dir=tmp_path, model_dir=tmp_path / 'missing'),
                      executor=BrowserExecutor(opener=lambda url, new: opened.append(url) or True),
                      speaker=speaker, listener=listener)
    return core, opened, speaker, listener


def test_wake_and_search():
    detected, remaining = strip_wake('Oryven, acordar. Abra o navegador e pesquise inteligência artificial')
    assert detected
    assert parse_search(remaining).query == 'inteligencia artificial'


def test_requires_explicit_search():
    assert parse_search('abra meus documentos') is None
    assert parse_search('execute powershell Remove-Item') is None


def test_approval_one_use_and_exact_target(tmp_path):
    core, opened, _, _ = make_core(tmp_path)
    action = core.submit('Abra o navegador e pesquise inteligência artificial')
    assert not opened
    assert core.decide(action['id'], 'approve')['outcome'] == 'dispatched'
    assert len(opened) == 1 and 'inteligencia+artificial' in opened[0]
    with pytest.raises(ApprovalError): core.decide(action['id'], 'approve')


def test_rejection_and_emergency_stop(tmp_path):
    core, opened, speaker, listener = make_core(tmp_path)
    first = core.submit('pesquise inteligência artificial')
    assert core.decide(first['id'], 'deny')['outcome'] == 'denied'
    second = core.submit('pesquise outras notícias')
    listener.start()
    assert core.emergency_stop()['cancelled'] == 1
    assert not listener.running and speaker.stopped
    with pytest.raises(ApprovalError): core.decide(second['id'], 'approve')
    assert opened == []


def test_voice_wake_requires_activation_phrase(tmp_path):
    core, _, _, _ = make_core(tmp_path)
    assert core.handle_voice_text('pesquise noticias') is None
    assert core.approvals.list_pending() == []
    core.handle_voice_text('Oryven acordar')
    core.handle_voice_text('Abra o navegador e pesquise noticias')
    assert len(core.approvals.list_pending()) == 1


def test_approval_ttl():
    now = [1000.0]
    store = ApprovalStore(ttl_seconds=2, clock=lambda: now[0])
    action = store.propose(SearchIntent(query='python'))
    now[0] = 1003.0
    with pytest.raises(ApprovalError): store.decide(action.id, True)


def test_api_flow(tmp_path):
    core, opened, _, _ = make_core(tmp_path)
    with TestClient(create_app(core)) as client:
        assert client.get('/api/health').status_code == 200
        assert client.get('/api/status').status_code == 401
        token = client.get('/api/session').json()['session_token']
        headers = {'X-Oryven-Session': token}
        action = client.post('/api/commands', headers=headers, json={'text':'pesquise inteligência artificial'}).json()['pending']
        assert not opened
        assert len(client.get('/api/actions/pending', headers=headers).json()) == 1
        resp = client.post(f"/api/actions/{action['id']}/decision", headers=headers, json={'decision':'approve'})
        assert resp.status_code == 200 and resp.json()['outcome'] == 'dispatched'
        assert len(opened) == 1
        assert client.get('/api/status', headers={**headers, 'Origin':'https://attacker.example'}).status_code == 403


def test_cloud_tts_sends_only_text_to_fixed_api():
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b'fake-audio')
    client = httpx.Client(transport=httpx.MockTransport(handler))
    class FakePlayer:
        def __init__(self): self.played = []
        def play(self, data): self.played.append(data)
        def stop(self): pass
    player = FakePlayer()
    fallback = FakeSpeaker()
    voice = ElevenLabsSpeaker('test-secret','voice123',client=client,player=player,fallback=fallback)
    assert voice.speak_once('Olá, eu sou Oryven')
    assert len(seen) == 1 and player.played == [b'fake-audio']
    assert seen[0].url.host == 'api.elevenlabs.io'
    assert seen[0].headers['xi-api-key'] == 'test-secret'
    assert b'Ol\xc3\xa1' in seen[0].content


def test_cloud_tts_local_fallback_on_failure():
    def handler(request): return httpx.Response(401, json={'detail': 'Unauthorized'})
    player = type('FakePlayer', (), {'play': lambda self, a: None, 'stop': lambda self: None})()
    fallback = FakeSpeaker()
    voice = ElevenLabsSpeaker('bad','voice123',client=httpx.Client(transport=httpx.MockTransport(handler)),player=player,fallback=fallback)
    assert voice.speak_once('Olá') is False
    assert fallback.messages == ['Olá']
