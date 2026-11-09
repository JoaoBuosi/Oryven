from pathlib import Path
import subprocess

import pytest

from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.developer_runtime import DeveloperRuntime, DeveloperRuntimeError
from oryven.models import DeveloperActionIntent
from oryven.ml.intent_router import LocalIntentRouter


class QuietSpeaker:
    enabled = False
    provider = "test"
    speaking = False
    def say(self, message): pass
    def stop(self): pass


class QuietListener:
    running = False
    def start(self): self.running = True
    def stop(self): self.running = False


def test_intent_router_model_is_loaded():
    model = Path(__file__).resolve().parents[1] / "oryven" / "ml" / "intent_model.json"
    router = LocalIntentRouter(model)
    assert router.ready
    result = router.predict("rode os testes python neste projeto")
    assert result is not None
    assert result.label == "test.python"
    assert result.confidence > 0


def test_developer_runtime_blocks_workspace_outside_roots(tmp_path):
    allowed = tmp_path / "allowed"
    other = tmp_path / "other"
    allowed.mkdir(); other.mkdir()
    runtime = DeveloperRuntime((allowed,))
    with pytest.raises(DeveloperRuntimeError):
        runtime.execute(DeveloperActionIntent(action="workspace.inspect", workspace=str(other)))


def test_developer_workspace_inspection_requires_existing_absolute_path(tmp_path):
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    runtime = DeveloperRuntime((tmp_path,))
    result = runtime.execute(DeveloperActionIntent(action="workspace.inspect", workspace=str(tmp_path)))
    assert result["returncode"] == 0
    assert "README.md" in result["stdout"]


def test_developer_git_status_is_named_operation(tmp_path):
    if not subprocess.run(["git", "--version"], capture_output=True).returncode == 0:
        pytest.skip("git unavailable")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    runtime = DeveloperRuntime((tmp_path,))
    result = runtime.execute(DeveloperActionIntent(action="git.status", workspace=str(tmp_path)))
    assert result["action"] == "git.status"
    assert result["returncode"] == 0


def test_core_requires_one_shot_approval_for_developer_action(tmp_path):
    workspace = tmp_path / "project"
    workspace.mkdir()
    settings = Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "model", developer_roots=(workspace,))
    core = OryvenCore(settings, speaker=QuietSpeaker(), listener=QuietListener())
    pending = core.propose_developer_action("workspace.inspect", str(workspace))
    assert pending["kind"] == "developer.action"
    assert core.audit.list()
    result = core.decide(pending["id"], "approve")
    assert result["outcome"] == "completed"
    with pytest.raises(Exception):
        core.decide(pending["id"], "approve")


def test_chat_memory_persists_across_core_recreation(tmp_path):
    settings = Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "model")
    first = OryvenCore(settings, speaker=QuietSpeaker(), listener=QuietListener())
    first.chat_memory.append_exchange("ola", "oi")
    second = OryvenCore(settings, speaker=QuietSpeaker(), listener=QuietListener())
    messages = second.chat_memory.list_messages()
    assert [m["text"] for m in messages] == ["ola", "oi"]
    second.chat_memory.clear()
    assert second.chat_memory.list_messages() == []
