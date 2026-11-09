import json

from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.buno_mission_planner import BunoMissionPlannerError
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


class FakeBunoPlannerBridge:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
    def plan_json(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("unexpected planner call")
        return self.responses.pop(0)
    def check(self):
        return {"reachable": True}


def make_core(tmp_path, workspace, bridge, token="test-token"):
    settings = Settings(
        data_dir=tmp_path / "data", model_dir=tmp_path / "model",
        work_roots=(workspace,), developer_roots=(workspace,), buno_bearer_token=token,
    )
    return OryvenCore(settings, speaker=Speaker(), listener=Listener(), buno_bridge=bridge)


def pending_id(mission):
    return next(step["action_id"] for step in mission["steps"] if step["status"] == "awaiting_approval")


def test_buno_plan_validated_against_live_skill_and_workspace(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir(); (workspace / "pyproject.toml").write_text("[project]\nname='x'\n")
    bridge = FakeBunoPlannerBridge([json.dumps({
        "agent_id": "software.engineering", "rationale": "inspect and test",
        "steps": [
            {"skill_id": "workspace.inspect", "arguments": {"workspace": str(workspace)}},
            {"skill_id": "test.python", "arguments": {"workspace": str(workspace)}},
        ],
    })])
    core = make_core(tmp_path, workspace, bridge)
    plan = core.plan_buno_ai_mission("corrija e teste este backend Python", {"workspace": str(workspace)}, 6)
    assert plan["status"] == "ready"
    assert plan["planner"] == "buno-ai"
    assert plan["permissions_granted"] is False
    assert [s["skill_id"] for s in plan["steps"]] == ["workspace.inspect", "test.python"]
    assert len(bridge.prompts) == 1


def test_invalid_buno_plan_gets_one_bounded_correction(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir()
    bridge = FakeBunoPlannerBridge([
        json.dumps({"agent_id": "software.engineering", "rationale": "bad", "steps": [
            {"skill_id": "evil.run", "arguments": {"workspace": str(workspace)}}
        ]}),
        json.dumps({"agent_id": "software.engineering", "rationale": "fixed", "steps": [
            {"skill_id": "workspace.inspect", "arguments": {"workspace": str(workspace)}}
        ]}),
    ])
    core = make_core(tmp_path, workspace, bridge)
    plan = core.plan_buno_ai_mission("inspecione este projeto de software", {"workspace": str(workspace)}, 4)
    assert plan["corrected"] is True
    assert len(bridge.prompts) == 2
    assert "previous_plan_error" in bridge.prompts[1]


def test_buno_cannot_smuggle_permissions_or_unknown_fields(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir()
    bad = json.dumps({
        "agent_id": "software.engineering", "rationale": "try bypass",
        "permissions_granted": True,
        "steps": [{"skill_id": "workspace.inspect", "arguments": {"workspace": str(workspace)}}],
    })
    bridge = FakeBunoPlannerBridge([bad, bad])
    core = make_core(tmp_path, workspace, bridge)
    try:
        core.plan_buno_ai_mission("inspecione este software", {"workspace": str(workspace)}, 4)
    except BunoMissionPlannerError:
        pass
    else:
        raise AssertionError("untrusted permission field should be rejected")
    assert len(bridge.prompts) == 2


def test_buno_plan_cannot_escape_allowed_workspace(tmp_path):
    workspace = tmp_path / "allowed"; workspace.mkdir()
    outside = tmp_path / "outside"; outside.mkdir()
    response = json.dumps({
        "agent_id": "software.engineering", "rationale": "escape",
        "steps": [{"skill_id": "workspace.inspect", "arguments": {"workspace": str(outside)}}],
    })
    bridge = FakeBunoPlannerBridge([response, response])
    core = make_core(tmp_path, workspace, bridge)
    try:
        core.plan_buno_ai_mission("inspecione este projeto", {"workspace": str(workspace)}, 4)
    except Exception:
        pass
    else:
        raise AssertionError("outside workspace must not become a ready plan")


def test_failed_ai_mission_uses_buno_recovery_but_requires_new_approval(tmp_path):
    workspace = tmp_path / "work"; workspace.mkdir()
    plan_response = json.dumps({
        "agent_id": "software.engineering", "rationale": "run check",
        "steps": [{"skill_id": "terminal.run", "arguments": {
            "workspace": str(workspace), "executable": "python", "args": ["-c", "import sys; sys.exit(3)"]
        }}],
    })
    recovery_response = json.dumps({
        "rationale": "inspect workspace first",
        "step": {"skill_id": "filesystem.list", "arguments": {"workspace": str(workspace), "path": "."}},
    })
    bridge = FakeBunoPlannerBridge([plan_response, recovery_response])
    core = make_core(tmp_path, workspace, bridge)
    mission = core.start_buno_ai_mission("execute uma checagem Python neste software", {"workspace": str(workspace)}, 4, 1)
    failed = core.decide(pending_id(mission), "approve")
    assert failed["outcome"] == "failed"
    recovery = core.autonomous_advance(mission["id"])
    assert recovery["status"] == "awaiting_approval"
    assert recovery["steps"][1]["status"] == "awaiting_approval"
    assert recovery["steps"][1]["kind"] == "work.action"
    assert core.autonomous_mission_status(mission["id"])["autonomy"]["recovery_used"] == 1


def test_buno_ai_api_surface(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir()
    response = json.dumps({
        "agent_id": "software.engineering", "rationale": "inspect",
        "steps": [{"skill_id": "workspace.inspect", "arguments": {"workspace": str(workspace)}}],
    })
    bridge = FakeBunoPlannerBridge([response, response])
    core = make_core(tmp_path, workspace, bridge)
    app = create_app(core)
    with TestClient(app) as client:
        headers = {"X-Oryven-Session": client.get("/api/session").json()["session_token"]}
        body = {"objective": "inspecione este projeto de software", "context": {"workspace": str(workspace)}, "max_steps": 4, "recovery_budget": 1}
        plan = client.post("/api/missions/ai/plan", headers=headers, json=body)
        assert plan.status_code == 200 and plan.json()["planner"] == "buno-ai"
        start = client.post("/api/missions/ai/start", headers=headers, json=body)
        assert start.status_code == 200 and start.json()["status"] == "awaiting_approval"
