import httpx
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.api import create_app
from oryven.executor import WindowsAppExecutor, ExecutionError, BrowserExecutor
from oryven.intent import parse_app_launch, parse_intent
from oryven.models import AppLaunchIntent
from oryven.skills import list_skills

class FakeVoice:
    enabled=True
    provider="test"
    speaking=False
    def say(self,message): pass
    def stop(self): pass
class FakeListener:
    running=False
    def stop(self): pass


def test_app_intents_exact_allowlist():
    assert parse_app_launch("Abra o bloco de notas").app_id == "notepad"
    assert parse_app_launch("abra a calculadora").app_id == "calculator"
    assert parse_app_launch("Abra o explorador de arquivos").app_id == "explorer"
    assert parse_app_launch("abra o powershell") is None
    assert parse_app_launch("abra o bloco de notas; delete tudo") is None
    assert parse_intent("abra o navegador e pesquise Java").kind == "browser.search"


def test_windows_app_executor_uses_exact_exe_no_shell(tmp_path):
    system = tmp_path / "System32"
    system.mkdir()
    (system / "notepad.exe").write_bytes(b"test")
    launched=[]
    executor=WindowsAppExecutor(windows_dir=tmp_path, platform="win32", launcher=lambda argv, **kw: launched.append((argv,kw)))
    result=executor.execute(AppLaunchIntent(app_id="notepad"))
    assert "notepad" in result
    assert launched[0][0] == [str((system / 'notepad.exe').resolve())]
    assert launched[0][1]["shell"] is False
    with pytest.raises(ExecutionError):
        executor.execute(AppLaunchIntent(app_id="explorer"))


def test_app_action_must_be_approved(tmp_path):
    calls=[]
    class FakeApps:
        def execute(self,intent):
            calls.append(intent.app_id)
            return 'Solicitado'
    core=OryvenCore(Settings(data_dir=tmp_path,model_dir=tmp_path/'none'),
        executor=BrowserExecutor(opener=lambda url,new: True),
        speaker=FakeVoice(), listener=FakeListener(),app_executor=FakeApps())
    pending=core.submit('abra a calculadora')
    assert not calls
    assert pending['target']=='windows-known-app:calculator'
    assert core.decide(pending['id'],'approve')['outcome']=='dispatched'
    assert calls==['calculator']
    assert core.approvals.list_pending()==[]


def test_skills_endpoint_and_no_arbitrary_tool_execution(tmp_path):
    core=OryvenCore(Settings(data_dir=tmp_path,model_dir=tmp_path/'none'), speaker=FakeVoice(), listener=FakeListener())
    with TestClient(create_app(core)) as client:
        token=client.get('/api/session').json()['session_token']
        headers={'X-Oryven-Session':token}
        response=client.get('/api/skills',headers=headers)
        assert response.status_code==200
        assert response.json()['dynamic_execution'] is False
        ids={s['id'] for s in response.json()['skills']}
        assert {'browser.search','app.launch','computer.windows.list','browser.inspect','buno.chat'}.issubset(ids)
        assert {'filesystem.read','filesystem.write_text','terminal.run','git.status','maya.assist'}.issubset(ids)
        assert response.json()['execution'] == 'named adapters + one-shot approval'
        response=client.post('/api/commands',headers=headers,json={'text':'execute PowerShell shutdown'})
        assert response.status_code==200
        assert response.json()['pending'] is None
