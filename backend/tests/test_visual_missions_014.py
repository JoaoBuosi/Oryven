from types import SimpleNamespace
from pathlib import Path

from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.visual_perception import VisualPerception
from oryven.window_actions import WindowActions
from oryven.computer_control import WindowInspector


class Speaker:
    enabled = False
    provider = "test"
    def say(self, text): pass
    def stop(self): pass

class Listener:
    running = False
    def stop(self): pass

class FakeWindow:
    handle = 444
    active = False
    element_info = SimpleNamespace(process_id=77, class_name="VisualWindow", name="Visual App",
                                   control_type="Window", is_password=False)
    def is_visible(self): return True
    def is_enabled(self): return True
    def window_text(self): return "Visual App"
    def children(self): return []
    def rectangle(self): return SimpleNamespace(left=10, top=20, right=210, bottom=120)
    def set_focus(self): self.active = True
    def is_active(self): return self.active

class FakeDesktop:
    def __init__(self, window): self.window = window
    def windows(self): return [self.window]


def make_core(tmp_path):
    window = FakeWindow()
    inspector = WindowInspector(platform="win32", desktop_factory=lambda backend: FakeDesktop(window))
    actions = WindowActions(inspector, sleeper=lambda _: None)
    png = b"\x89PNG\r\n\x1a\nvisual-test"
    perception = VisualPerception(capture_backend=lambda bbox: (png, bbox[2]-bbox[0], bbox[3]-bbox[1]))
    core = OryvenCore(Settings(data_dir=tmp_path/"data", model_dir=tmp_path/"model"),
                      speaker=Speaker(), listener=Listener(), window_inspector=inspector,
                      window_actions=actions, visual_perception=perception)
    return core, window


def test_visual_snapshot_requires_one_shot_approval_and_is_ephemeral(tmp_path):
    core, window = make_core(tmp_path)
    pending = core.propose_window_visual_snapshot(window.handle)
    assert pending["kind"] == "computer.window.capture"
    assert "Visual App" in pending["description"]
    result = core.decide(pending["id"], "approve")
    assert result["outcome"] == "captured"
    assert result["data"]["width"] == 200
    assert result["data"]["height"] == 100
    assert result["data"]["persisted"] is False
    assert result["data"]["image_base64"]


def test_visual_snapshot_revalidates_window_identity(tmp_path):
    core, window = make_core(tmp_path)
    pending = core.propose_window_visual_snapshot(window.handle)
    window.element_info.process_id = 88
    result = core.decide(pending["id"], "approve")
    assert result["outcome"] == "failed"
    assert "mudou" in result["message"].lower()


def test_skill_mission_executes_step_by_step_with_manual_verification(tmp_path):
    workspace = tmp_path / "workspace"; workspace.mkdir()
    core, _ = make_core(tmp_path)
    Step = SimpleNamespace
    mission = core.start_skill_mission("criar pasta e arquivo", [
        Step(skill_id="filesystem.mkdir", arguments={"workspace": str(workspace), "path": "saida"}),
        Step(skill_id="filesystem.write_text", arguments={"workspace": str(workspace), "path": "saida/relatorio.txt", "content": "Oryven 0.14"}),
    ])
    assert mission["status"] == "awaiting_approval"
    first = next(s for s in mission["steps"] if s["status"] == "awaiting_approval")
    done = core.decide(first["action_id"], "approve")
    assert done["outcome"] == "completed"
    state = core.missions.get(mission["id"])
    assert state["status"] == "awaiting_verification"
    state = core.verify_mission_step(mission["id"], True)
    assert state["status"] == "awaiting_approval"
    second = next(s for s in state["steps"] if s["status"] == "awaiting_approval")
    done2 = core.decide(second["action_id"], "approve")
    assert done2["outcome"] == "completed"
    assert (workspace/"saida/relatorio.txt").read_text() == "Oryven 0.14"


def test_visual_and_skill_mission_api_surface(tmp_path):
    core, window = make_core(tmp_path)
    workspace = tmp_path / "api-work"; workspace.mkdir()
    with TestClient(create_app(core)) as client:
        h={"X-Oryven-Session": client.get("/api/session").json()["session_token"]}
        p=client.post("/api/perception/window/propose", headers=h, json={"handle":window.handle})
        assert p.status_code == 200
        action=p.json()["pending"]["id"]
        assert client.post(f"/api/actions/{action}/decision",headers=h,json={"decision":"approve"}).json()["outcome"]=="captured"
        m=client.post("/api/missions/skills",headers=h,json={"objective":"listar workspace","steps":[
            {"skill_id":"filesystem.list","arguments":{"workspace":str(workspace),"path":"."}}
        ]})
        assert m.status_code == 200
        assert m.json()["status"] == "awaiting_approval"
