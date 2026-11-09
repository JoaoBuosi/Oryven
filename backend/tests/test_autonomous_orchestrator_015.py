from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.models import SkillMissionStep


class Speaker:
    enabled = False
    provider = "test"
    speaking = False
    def say(self, text): pass
    def stop(self): pass


class Listener:
    running = False
    def stop(self): pass


def make_core(tmp_path, workspace):
    return OryvenCore(
        Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "model", work_roots=(workspace,), developer_roots=(workspace,)),
        speaker=Speaker(), listener=Listener(),
    )


def pending_id(mission):
    return next(step["action_id"] for step in mission["steps"] if step["status"] == "awaiting_approval")


def test_adaptive_planner_detects_python_project(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir(); (workspace / "pyproject.toml").write_text("[project]\nname='x'\n")
    core = make_core(tmp_path, workspace)
    plan = core.plan_autonomous_mission("corrija e teste este backend Python", {"workspace": str(workspace)})
    assert plan["status"] == "ready"
    assert plan["agent"]["agent_id"] == "software.engineering"
    assert [s["skill_id"] for s in plan["steps"]] == ["workspace.inspect", "git.status", "test.python"]
    assert plan["permissions_granted"] is False


def test_planner_refuses_to_guess_workspace(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir()
    core = make_core(tmp_path, workspace)
    plan = core.plan_autonomous_mission("analise os dados e gere métricas", {})
    assert plan["status"] == "needs_context"
    assert "workspace" in plan["missing"]
    assert plan["permissions_granted"] is False


def test_autonomous_loop_auto_verifies_and_advances_one_approval_at_a_time(tmp_path):
    workspace = tmp_path / "work"; workspace.mkdir()
    core = make_core(tmp_path, workspace)
    steps = [
        SkillMissionStep(skill_id="filesystem.mkdir", arguments={"workspace": str(workspace), "path": "reports"}),
        SkillMissionStep(skill_id="filesystem.write_text", arguments={"workspace": str(workspace), "path": "reports/status.txt", "content": "ok"}),
    ]
    mission = core.start_autonomous_mission("prepare uma pasta e um relatório", {}, steps, recovery_budget=1)
    assert mission["status"] == "awaiting_approval"
    assert sum(s["status"] == "awaiting_approval" for s in mission["steps"]) == 1

    result = core.decide(pending_id(mission), "approve")
    assert result["outcome"] == "completed"
    advanced = core.autonomous_advance(mission["id"])
    assert advanced["status"] == "awaiting_approval"
    assert (workspace / "reports").is_dir()

    result2 = core.decide(pending_id(advanced), "approve")
    assert result2["outcome"] == "completed"
    final = core.autonomous_advance(mission["id"])
    assert final["state"] == "completed"
    assert (workspace / "reports" / "status.txt").read_text() == "ok"


def test_failed_step_injects_diagnostic_recovery_without_auto_approval(tmp_path):
    workspace = tmp_path / "work"; workspace.mkdir()
    core = make_core(tmp_path, workspace)
    steps = [SkillMissionStep(skill_id="terminal.run", arguments={
        "workspace": str(workspace), "executable": "python", "args": ["-c", "import sys; sys.exit(3)"]
    })]
    mission = core.start_autonomous_mission("execute uma checagem supervisionada", {}, steps, recovery_budget=1)
    failed = core.decide(pending_id(mission), "approve")
    assert failed["outcome"] == "failed"
    recovery = core.autonomous_advance(mission["id"])
    assert recovery["status"] == "awaiting_approval"
    assert recovery["steps"][0]["status"] == "failed_recovered"
    assert recovery["steps"][1]["status"] == "awaiting_approval"
    assert recovery["steps"][1]["kind"] == "work.action"
    meta = core.autonomous_mission_status(mission["id"])["autonomy"]
    assert meta["recovery_used"] == 1
    assert meta["recovery_budget"] == 1


def test_autonomous_api_surface(tmp_path):
    workspace = tmp_path / "work"; workspace.mkdir()
    core = make_core(tmp_path, workspace)
    app = create_app(core)
    with TestClient(app) as client:
        headers = {"X-Oryven-Session": client.get("/api/session").json()["session_token"]}
        body = {
            "objective": "crie uma pasta para resultados",
            "steps": [{"skill_id": "filesystem.mkdir", "arguments": {"workspace": str(workspace), "path": "out"}}],
            "max_steps": 4,
            "recovery_budget": 1,
        }
        plan = client.post("/api/missions/autonomous/plan", headers=headers, json=body)
        assert plan.status_code == 200 and plan.json()["status"] == "ready"
        started = client.post("/api/missions/autonomous/start", headers=headers, json=body)
        assert started.status_code == 200
        mission = started.json(); mid = mission["id"]
        status = client.get(f"/api/missions/{mid}/autonomous", headers=headers)
        assert status.status_code == 200 and status.json()["autonomy"]["recovery_budget"] == 1
