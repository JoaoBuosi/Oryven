import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.models import WorkActionIntent
from oryven.skills import SkillCatalog, SkillError
from oryven.work_runtime import WorkRuntime, WorkRuntimeError


class QuietSpeaker:
    enabled = False
    provider = "test"
    def say(self, text): pass
    def stop(self): pass


class QuietListener:
    running = False
    def stop(self): pass


def make_core(tmp_path: Path):
    root = tmp_path / "work"
    root.mkdir()
    settings = Settings(
        data_dir=tmp_path / "data",
        model_dir=tmp_path / "model",
        developer_roots=(root,),
        work_roots=(root,),
        terminal_executables=("python", "python3"),
    )
    return OryvenCore(settings, speaker=QuietSpeaker(), listener=QuietListener()), root


def test_work_runtime_blocks_path_escape(tmp_path):
    root = tmp_path / "work"; root.mkdir()
    outside = tmp_path / "secret.txt"; outside.write_text("secret", encoding="utf-8")
    runtime = WorkRuntime((root,))
    with pytest.raises(WorkRuntimeError):
        runtime.execute(WorkActionIntent(action="filesystem.read", workspace=str(root), path="../secret.txt"))


def test_work_runtime_write_read_and_list(tmp_path):
    root = tmp_path / "work"; root.mkdir()
    runtime = WorkRuntime((root,))
    write = runtime.execute(WorkActionIntent(
        action="filesystem.write_text", workspace=str(root), path="reports/result.txt", content="oryven"
    ))
    assert write["bytes_written"] == 6
    read = runtime.execute(WorkActionIntent(action="filesystem.read", workspace=str(root), path="reports/result.txt"))
    assert read["content"] == "oryven"
    listing = runtime.execute(WorkActionIntent(action="filesystem.list", workspace=str(root), path="reports"))
    assert listing["entries"][0]["name"] == "result.txt"


def test_work_runtime_rejects_binary_and_large_files(tmp_path):
    root = tmp_path / "work"; root.mkdir()
    runtime = WorkRuntime((root,))
    (root / "binary.bin").write_bytes(b"abc\x00def")
    with pytest.raises(WorkRuntimeError):
        runtime.execute(WorkActionIntent(action="filesystem.read", workspace=str(root), path="binary.bin"))
    (root / "large.txt").write_bytes(b"a" * 1_000_001)
    with pytest.raises(WorkRuntimeError):
        runtime.execute(WorkActionIntent(action="filesystem.read", workspace=str(root), path="large.txt"))


def test_terminal_run_is_exact_argv_and_allowlisted(tmp_path):
    root = tmp_path / "work"; root.mkdir()
    runtime = WorkRuntime((root,), terminal_executables=(Path(sys.executable).name, "python", "python3"))
    executable = Path(sys.executable).name
    result = runtime.execute(WorkActionIntent(
        action="terminal.run", workspace=str(root), executable=executable,
        args=["-c", "print('ORYVEN_TERMINAL_OK')"],
    ))
    assert result["returncode"] == 0
    assert "ORYVEN_TERMINAL_OK" in result["stdout"]
    assert result["argv"][0] == executable


def test_terminal_rejects_unapproved_executable(tmp_path):
    root = tmp_path / "work"; root.mkdir()
    runtime = WorkRuntime((root,), terminal_executables=("git",))
    with pytest.raises(WorkRuntimeError):
        runtime.execute(WorkActionIntent(action="terminal.run", workspace=str(root), executable="powershell", args=["-c", "echo hi"]))


def test_skill_catalog_builds_intent_but_does_not_execute(tmp_path):
    catalog = SkillCatalog(Path(__file__).resolve().parents[2] / "skills" / "builtin")
    root = tmp_path / "work"; root.mkdir()
    intent = catalog.build_intent("filesystem.read", {"workspace": str(root), "path": "x.txt"})
    assert intent.kind == "work.action"
    assert intent.action == "filesystem.read"
    maya = catalog.build_intent("maya.assist", {
        "workspace": str(root), "output": "scene_tools.py", "language": "python", "script": "print('ok')"
    })
    assert maya.kind == "professional.action"
    assert maya.action == "maya.assist"


def test_professional_plan_recommends_real_and_planned_skills(tmp_path):
    core, _ = make_core(tmp_path)
    dev = core.professional_plan("corrija o backend Python e rode os testes")
    ids = {skill["id"] for skill in dev["recommended_skills"]}
    assert "filesystem.read" in ids
    assert "terminal.run" in ids
    assert "git.status" in ids
    assert dev["orchestration"]["permissions_granted"] is False

    maya = core.professional_plan("organize a cena no Maya e prepare o render")
    assert any(skill["id"] == "maya.assist" and skill["executable"] for skill in maya["recommended_skills"])


def test_skill_proposal_requires_one_shot_approval(tmp_path):
    core, root = make_core(tmp_path)
    (root / "note.txt").write_text("hello", encoding="utf-8")
    pending = core.propose_skill("filesystem.read", {"workspace": str(root), "path": "note.txt"})
    assert pending["kind"] == "work.action"
    assert "filesystem.read" in pending["description"]
    result = core.decide(pending["id"], "approve")
    assert result["data"]["content"] == "hello"
    with pytest.raises(Exception):
        core.decide(pending["id"], "approve")


def test_write_approval_description_hides_content_but_fingerprint_binds_it(tmp_path):
    core, root = make_core(tmp_path)
    secretish = "conteudo privado que nao deve aparecer na descricao"
    pending = core.propose_skill("filesystem.write_text", {
        "workspace": str(root), "path": "draft.txt", "content": secretish,
    })
    assert secretish not in pending["description"]
    assert "caracteres" in pending["description"]
    core.decide(pending["id"], "approve")
    assert (root / "draft.txt").read_text(encoding="utf-8") == secretish


def test_skill_api_plan_and_proposal(tmp_path):
    core, root = make_core(tmp_path)
    (root / "a.txt").write_text("A", encoding="utf-8")
    with TestClient(create_app(core)) as client:
        token = client.get("/api/session").json()["session_token"]
        headers = {"X-Oryven-Session": token}
        plan = client.post("/api/agents/plan", headers=headers, json={"objective": "analise meus arquivos e escreva um relatorio"})
        assert plan.status_code == 200
        assert plan.json()["orchestration"]["state"] == "draft"
        proposal = client.post("/api/skills/filesystem.read/propose", headers=headers,
                               json={"arguments": {"workspace": str(root), "path": "a.txt"}})
        assert proposal.status_code == 200
        pending = proposal.json()["pending"]
        approved = client.post(f"/api/actions/{pending['id']}/decision", headers=headers, json={"decision": "approve"})
        assert approved.status_code == 200
        assert approved.json()["data"]["content"] == "A"


def test_unknown_or_planned_skill_cannot_execute_via_api(tmp_path):
    core, _ = make_core(tmp_path)
    with TestClient(create_app(core)) as client:
        headers={"X-Oryven-Session": client.get('/api/session').json()['session_token']}
        assert client.post('/api/skills/does.not.exist/propose',headers=headers,json={'arguments':{}}).status_code == 422
        assert client.post('/api/skills/maya.assist/propose',headers=headers,json={'arguments':{'objective':'render'}}).status_code == 422
