from pathlib import Path
from oryven.voice_profile import VoiceProfile
from oryven.config import Settings
from oryven.core import OryvenCore

class DummySpeaker:
    enabled=True
    speaking=False
    provider='test'
    def __init__(self): self.messages=[]
    def say(self, msg): self.messages.append(msg)
    def stop(self): pass

class DummyListener:
    def __init__(self): self.running=False; self.starts=0; self.stops=0
    def start(self): self.running=True; self.starts+=1
    def stop(self): self.running=False; self.stops+=1

def settings(tmp_path):
    return Settings(data_dir=tmp_path, model_dir=tmp_path/'model')

def test_custom_wake_word_and_remaining_command():
    p=VoiceProfile(assistant_name='Atlas')
    ok, rest=p.match_wake('Atlas, acordar. abra o chrome')
    assert ok is True
    assert rest == 'abra o chrome'
    assert p.match_wake('Oryven acordar')[0] is False

def test_voice_profile_persists(tmp_path):
    path=tmp_path/'voice_profile.json'
    p=VoiceProfile().update(assistant_name='Nova', background_listening_enabled=True, wake_enabled=True)
    p.save(path)
    got=VoiceProfile.load(path)
    assert got.assistant_name == 'Nova'
    assert got.background_listening_enabled is True

def test_profile_update_controls_listener_and_does_not_grant_actions(tmp_path):
    speaker=DummySpeaker(); listener=DummyListener()
    core=OryvenCore(settings(tmp_path), speaker=speaker, listener=listener)
    result=core.update_voice_profile(assistant_name='Atlas', background_listening_enabled=True)
    assert result['assistant_name']=='Atlas'
    assert listener.running is True
    assert core.approvals.list_pending() == []
    core.update_voice_profile(background_listening_enabled=False)
    assert listener.running is False

def test_startup_greeting_uses_saved_name(tmp_path):
    VoiceProfile(assistant_name='Atlas', speak_on_startup=True).save(tmp_path/'voice_profile.json')
    speaker=DummySpeaker(); listener=DummyListener()
    OryvenCore(settings(tmp_path), speaker=speaker, listener=listener)
    assert any('Atlas' in x for x in speaker.messages)

def test_voice_profile_api_roundtrip(tmp_path):
    from fastapi.testclient import TestClient
    from oryven.api import create_app
    speaker=DummySpeaker(); listener=DummyListener()
    core=OryvenCore(settings(tmp_path), speaker=speaker, listener=listener)
    with TestClient(create_app(core)) as client:
        token=client.get('/api/session').json()['session_token']
        h={'X-Oryven-Session':token}
        r=client.patch('/api/voice/profile',headers=h,json={'assistant_name':'Atlas','background_listening_enabled':True})
        assert r.status_code==200
        assert r.json()['assistant_name']=='Atlas'
        assert r.json()['background_listening_enabled'] is True
        assert client.get('/api/voice/profile',headers=h).json()['assistant_name']=='Atlas'

def test_speech_stop_does_not_cancel_action_permissions(tmp_path):
    speaker=DummySpeaker(); listener=DummyListener()
    core=OryvenCore(settings(tmp_path), speaker=speaker, listener=listener)
    action=core.submit('pesquise python')
    assert action is not None
    assert core.stop_speaking()['status']=='stopped'
    assert len(core.approvals.list_pending())==1
