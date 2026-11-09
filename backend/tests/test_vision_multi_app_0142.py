from types import SimpleNamespace
from pathlib import Path

from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.visual_perception import VisualPerception
from oryven.window_actions import WindowActions
from oryven.computer_control import WindowInspector
from oryven.vision_provider import ScreenUnderstanding, StructuredScreenProvider


class Speaker:
    enabled = False
    provider = "test"
    speaking = False
    def say(self, text): pass
    def stop(self): pass

class Listener:
    running = False
    def stop(self): pass

class FakeEdit:
    handle = 0
    element_info = SimpleNamespace(process_id=77, class_name="", name="private value", control_type="Edit", is_password=False, automation_id="Query")
    def children(self): return []
    def is_visible(self): return True
    def is_enabled(self): return True

class FakeButton:
    handle = 0
    element_info = SimpleNamespace(process_id=77, class_name="", name="Analyze", control_type="Button", is_password=False, automation_id="AnalyzeButton")
    def children(self): return []
    def is_visible(self): return True
    def is_enabled(self): return True

class FakeWindow:
    handle = 555
    element_info = SimpleNamespace(process_id=77, class_name="VisualWindow", name="Workbook", control_type="Window", is_password=False, automation_id="")
    def is_visible(self): return True
    def is_enabled(self): return True
    def window_text(self): return "Workbook"
    def children(self): return [FakeEdit(), FakeButton()]
    def rectangle(self): return SimpleNamespace(left=0, top=0, right=300, bottom=200)

class FakeDesktop:
    def __init__(self, window): self.window=window
    def windows(self): return [self.window]

class FakeAppCatalog:
    def resolve(self, name):
        return SimpleNamespace(name=name, launch_target=f"C:/Apps/{name}.exe", target_type="executable")


def make_core(tmp_path, work_roots=()):
    window=FakeWindow()
    inspector=WindowInspector(platform="win32", desktop_factory=lambda backend: FakeDesktop(window))
    actions=WindowActions(inspector, sleeper=lambda _: None)
    perception=VisualPerception(capture_backend=lambda bbox: (b"\x89PNG\r\n\x1a\nscene", 300, 200))
    core=OryvenCore(Settings(data_dir=tmp_path/"data", model_dir=tmp_path/"model", work_roots=tuple(work_roots)),
                    speaker=Speaker(), listener=Listener(), window_inspector=inspector,
                    window_actions=actions, visual_perception=perception,
                    screen_understanding=ScreenUnderstanding(StructuredScreenProvider()),
                    app_catalog=FakeAppCatalog())
    return core, window


def test_screen_understanding_is_governed_and_redacts_edit_content(tmp_path):
    core, window=make_core(tmp_path)
    pending=core.propose_window_understanding(window.handle, "qual o estado da tela?")
    assert pending["kind"] == "computer.window.understand"
    result=core.decide(pending["id"], "approve")
    assert result["outcome"] == "understood"
    scene=result["data"]["scene"]
    assert scene["execution_authorized"] is False
    assert scene["mode"] == "structured"
    assert all("private value" not in str(item) for item in scene["observations"])
    assert "image_base64" not in result["data"]["evidence"]


def test_multi_app_planner_requires_context_instead_of_guessing(tmp_path):
    core,_=make_core(tmp_path)
    plan=core.submit("abra o Excel, analise essa planilha, crie um relatório no Word e me mostre o resultado")
    assert plan["status"] == "needs_context"
    assert "workspace" in plan["missing"] and "spreadsheet_path" in plan["missing"]
    assert plan["permissions_granted"] is False


def test_voice_ready_multi_app_plan_creates_governed_mission(tmp_path):
    workspace=tmp_path/"work"; workspace.mkdir()
    xlsx=workspace/"dados.xlsx"
    # The context setter only validates path/extension; the professional runtime opens it later after approval.
    xlsx.write_bytes(b"placeholder")
    core,_=make_core(tmp_path, (workspace,))
    core.set_mission_context(str(workspace), "dados.xlsx", "relatorio.docx")
    mission=core.submit("abra o Excel, analise essa planilha, crie um relatório no Word e me mostre o resultado")
    assert mission["status"] == "awaiting_approval"
    assert len(mission["steps"]) == 3
    assert mission["steps"][0]["kind"] == "professional.action"
    assert mission["steps"][1]["kind"] == "professional.action"
    assert mission["steps"][2]["kind"] == "professional.action"
    assert sum(1 for s in mission["steps"] if s["status"] == "awaiting_approval") == 1


def test_vision_and_multi_app_api_surface(tmp_path):
    workspace=tmp_path/"work"; workspace.mkdir(); (workspace/"dados.xlsx").write_bytes(b"placeholder")
    core,window=make_core(tmp_path,(workspace,))
    with TestClient(create_app(core)) as client:
        h={"X-Oryven-Session": client.get("/api/session").json()["session_token"]}
        p=client.post("/api/perception/window/understand/propose",headers=h,json={"handle":window.handle,"prompt":"estado"})
        assert p.status_code==200
        aid=p.json()["pending"]["id"]
        assert client.post(f"/api/actions/{aid}/decision",headers=h,json={"decision":"approve"}).json()["outcome"]=="understood"
        c=client.post("/api/missions/context",headers=h,json={"workspace":str(workspace),"spreadsheet_path":"dados.xlsx","report_path":"relatorio.docx"})
        assert c.status_code==200 and c.json()["configured"] is True
        q=client.post("/api/missions/multi-app/plan",headers=h,json={"objective":"abra o Excel, analise essa planilha e crie relatório no Word","workspace":str(workspace),"spreadsheet_path":"dados.xlsx","report_path":"relatorio.docx"})
        assert q.status_code==200 and q.json()["status"]=="ready"
