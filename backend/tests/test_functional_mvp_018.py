from pathlib import Path

from oryven.config import Settings
from oryven.core import OryvenCore


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


def approve_and_verify(core, mission):
    while mission["status"] not in {"completed", "failed", "cancelled"}:
        if mission["status"] == "awaiting_approval":
            result = core.decide(pending_id(mission), "approve")
            assert result["outcome"] not in {"failed", "denied"}, result
            mission = core.missions.get(mission["id"])
        if mission["status"] == "awaiting_verification":
            mission = core.verify_mission_step(mission["id"], True)
        if mission["status"] == "planned":
            mission = core.resume_mission(mission["id"])
    return mission


def active_core(tmp_path, workspace):
    core = make_core(tmp_path, workspace)
    project = core.create_project("MVP Project", str(workspace), "Functional MVP acceptance")
    core.set_active_project(project["id"])
    return core


def test_five_official_flows_plan_with_real_context(tmp_path):
    workspace = tmp_path / "project"; workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (workspace / "test_demo.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    (workspace / "notes.txt").write_text("research material", encoding="utf-8")

    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(["item", "value"]); ws.append(["A", 10]); wb.save(workspace / "sales.xlsx")

    core = active_core(tmp_path, workspace)
    cases = {
        "development.validate": {},
        "office.report": {"spreadsheet_path": "sales.xlsx", "report_path": "report.docx"},
        "research.organize": {},
        "computer.workspace": {"read_path": "notes.txt"},
        "professional.multi_app": {"spreadsheet_path": "sales.xlsx", "report_path": "multi-report.docx"},
    }
    for flow_id, context in cases.items():
        plan = core.plan_functional_mvp_flow(flow_id, context)
        assert plan["status"] == "ready", (flow_id, plan)
        assert plan["steps"], flow_id
        assert plan["permissions_granted"] is False


def test_development_flow_executes_end_to_end(tmp_path):
    workspace = tmp_path / "dev"; workspace.mkdir()
    (workspace / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (workspace / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    core = active_core(tmp_path, workspace)
    mission = core.start_functional_mvp_flow("development.validate", "validar projeto", {})
    final = approve_and_verify(core, mission)
    assert final["status"] == "completed"
    assert len(final["steps"]) >= 2


def test_office_flow_generates_real_docx(tmp_path):
    workspace = tmp_path / "office"; workspace.mkdir()
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active; ws.append(["month", "sales"]); ws.append(["Jan", 100]); wb.save(workspace / "sales.xlsx")
    core = active_core(tmp_path, workspace)
    mission = core.start_functional_mvp_flow("office.report", "gerar relatório", {
        "spreadsheet_path": "sales.xlsx", "report_path": "report.docx"
    })
    final = approve_and_verify(core, mission)
    assert final["status"] == "completed"
    assert (workspace / "report.docx").is_file()
    assert (workspace / "report.docx").stat().st_size > 0


def test_research_and_computer_flows_execute_end_to_end(tmp_path):
    workspace = tmp_path / "knowledge"; workspace.mkdir()
    (workspace / "README.md").write_text("# Project\nUseful knowledge", encoding="utf-8")
    core = active_core(tmp_path, workspace)
    for flow_id, ctx in [
        ("research.organize", {}),
        ("computer.workspace", {"read_path": "README.md"}),
    ]:
        mission = core.start_functional_mvp_flow(flow_id, flow_id, ctx)
        final = approve_and_verify(core, mission)
        assert final["status"] == "completed", (flow_id, final)


def test_functional_mvp_refuses_to_guess_missing_context(tmp_path):
    workspace = tmp_path / "empty"; workspace.mkdir()
    core = active_core(tmp_path, workspace)
    plan = core.plan_functional_mvp_flow("office.report", {})
    assert plan["status"] == "needs_context"
    assert set(plan["missing"]) == {"report_path", "spreadsheet_path"}
    assert plan["permissions_granted"] is False


def test_functional_mvp_api_surface(tmp_path):
    from fastapi.testclient import TestClient
    from oryven.api import create_app
    workspace = tmp_path / "api"; workspace.mkdir()
    (workspace / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    (workspace / "test_demo.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    core = active_core(tmp_path, workspace)
    with TestClient(create_app(core)) as client:
        headers = {"X-Oryven-Session": client.get("/api/session").json()["session_token"]}
        catalog = client.get("/api/mvp/flows", headers=headers)
        assert catalog.status_code == 200
        assert len(catalog.json()["flows"]) == 5
        plan = client.post("/api/mvp/flows/development.validate/plan", headers=headers, json={"objective": "", "context": {}})
        assert plan.status_code == 200
        assert plan.json()["status"] == "ready"
        started = client.post("/api/mvp/flows/development.validate/start", headers=headers, json={"objective": "validar", "context": {}})
        assert started.status_code == 200
        assert started.json()["status"] == "awaiting_approval"
