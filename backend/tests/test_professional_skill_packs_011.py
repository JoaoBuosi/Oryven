import csv
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.models import ProfessionalActionIntent
from oryven.professional_runtime import ProfessionalRuntime, ProfessionalRuntimeError
from oryven.work_runtime import WorkRuntime


class QuietSpeaker:
    enabled = False
    provider = "test"
    def say(self, text): pass
    def stop(self): pass


class QuietListener:
    running = False
    def stop(self): pass


def make_core(tmp_path: Path):
    root = tmp_path / "work"; root.mkdir()
    settings = Settings(data_dir=tmp_path/"data", model_dir=tmp_path/"model",
                        developer_roots=(root,), work_roots=(root,))
    return OryvenCore(settings, speaker=QuietSpeaker(), listener=QuietListener()), root


def write_csv(path: Path):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh); w.writerow(["name", "value", "group"])
        w.writerow([" A ", "10", "x"]); w.writerow(["B", "20", "x"]); w.writerow(["B", "20", "x"])


def test_spreadsheet_and_analytics_profile_csv(tmp_path):
    root=tmp_path/"work"; root.mkdir(); write_csv(root/"data.csv")
    runtime=ProfessionalRuntime(WorkRuntime((root,)))
    sheet=runtime.execute(ProfessionalActionIntent(action="spreadsheet.analyze", workspace=str(root), arguments={"path":"data.csv"}))
    assert sheet["data"]["rows"] == 3
    value=next(c for c in sheet["data"]["columns"] if c["name"]=="value")
    assert value["mean"] == pytest.approx(50/3)
    analytics=runtime.execute(ProfessionalActionIntent(action="analytics.analyze", workspace=str(root), arguments={"path":"data.csv"}))
    group=next(c for c in analytics["data"]["columns"] if c["name"]=="group")
    assert group["top_values"][0][0] == "x"


def test_dataset_prepare_preserves_source_and_removes_duplicate(tmp_path):
    root=tmp_path/"work"; root.mkdir(); write_csv(root/"raw.csv")
    before=(root/"raw.csv").read_text(encoding="utf-8")
    runtime=ProfessionalRuntime(WorkRuntime((root,)))
    out=runtime.execute(ProfessionalActionIntent(action="datasets.prepare", workspace=str(root), arguments={"path":"raw.csv","output":"clean.csv"}))
    assert out["data"]["duplicates_removed"] == 1
    assert (root/"raw.csv").read_text(encoding="utf-8") == before
    assert (root/"clean.csv").exists()


def test_documents_and_presentation_write_only_after_execute(tmp_path):
    root=tmp_path/"work"; root.mkdir(); runtime=ProfessionalRuntime(WorkRuntime((root,)))
    doc=ProfessionalActionIntent(action="documents.compose", workspace=str(root), arguments={"path":"report.md","content":"# Report"})
    runtime.validate(doc); assert not (root/"report.md").exists()
    runtime.execute(doc); assert (root/"report.md").read_text(encoding="utf-8") == "# Report"
    pres=ProfessionalActionIntent(action="presentation.compose", workspace=str(root), arguments={"path":"deck.md","title":"Pitch","sections":[{"title":"Problem","body":"Pain"},"Solution"]})
    runtime.execute(pres); text=(root/"deck.md").read_text(encoding="utf-8")
    assert "# Pitch" in text and "Problem" in text and "Solution" in text


def test_database_query_is_read_only(tmp_path):
    root=tmp_path/"work"; root.mkdir(); dbp=root/"data.sqlite3"
    with sqlite3.connect(dbp) as db:
        db.execute("create table items(id integer primary key, name text)"); db.execute("insert into items(name) values ('one')"); db.commit()
    runtime=ProfessionalRuntime(WorkRuntime((root,)))
    result=runtime.execute(ProfessionalActionIntent(action="database.query", workspace=str(root), arguments={"path":"data.sqlite3","query":"select id,name from items"}))
    assert result["data"]["rows"] == [[1,"one"]]
    with pytest.raises(ProfessionalRuntimeError):
        runtime.validate(ProfessionalActionIntent(action="database.query", workspace=str(root), arguments={"path":"data.sqlite3","query":"delete from items"}))


def test_design_and_knowledge_inventory_does_not_return_content(tmp_path):
    root=tmp_path/"work"; root.mkdir(); (root/"assets").mkdir()
    (root/"assets"/"logo.png").write_bytes(b"fakepng"); (root/"secret.txt").write_text("PRIVATE",encoding="utf-8")
    runtime=ProfessionalRuntime(WorkRuntime((root,)))
    design=runtime.execute(ProfessionalActionIntent(action="design.assist", workspace=str(root), arguments={"path":"assets"}))
    assert design["data"]["assets"][0]["path"].endswith("logo.png")
    knowledge=runtime.execute(ProfessionalActionIntent(action="knowledge.organize", workspace=str(root), arguments={"path":"."}))
    assert any(x["path"]=="secret.txt" for x in knowledge["data"]["files"])
    assert "PRIVATE" not in str(knowledge)


def test_maya_assist_prepares_script_but_does_not_execute_it(tmp_path):
    root=tmp_path/"work"; root.mkdir(); runtime=ProfessionalRuntime(WorkRuntime((root,)))
    marker=root/"executed.txt"
    script=f"from pathlib import Path\nPath(r'{marker}').write_text('bad')"
    result=runtime.execute(ProfessionalActionIntent(action="maya.assist", workspace=str(root), arguments={"output":"maya/tool.py","language":"python","script":script}))
    assert (root/"maya"/"tool.py").exists()
    assert not marker.exists()
    assert "manual review" in (root/"maya"/"tool.py").read_text(encoding="utf-8")


def test_professional_skill_requires_approval_and_api_executes(tmp_path):
    core, root=make_core(tmp_path); write_csv(root/"data.csv")
    pending=core.propose_skill("analytics.analyze", {"workspace":str(root),"path":"data.csv"})
    assert pending["kind"] == "professional.action"
    assert pending["target"].startswith("professional:analytics.analyze:")
    result=core.decide(pending["id"], "approve")
    assert result["outcome"] == "completed"
    with TestClient(create_app(core)) as client:
        headers={"X-Oryven-Session":client.get('/api/session').json()['session_token']}
        skills=client.get('/api/skills',headers=headers).json()['skills']
        assert any(s['id']=='maya.assist' and s['executable'] for s in skills)
        proposal=client.post('/api/skills/documents.compose/propose',headers=headers,json={'arguments':{'workspace':str(root),'path':'api.md','content':'hello'}})
        assert proposal.status_code == 200
        action=proposal.json()['pending']
        approved=client.post(f"/api/actions/{action['id']}/decision",headers=headers,json={'decision':'approve'})
        assert approved.status_code == 200
        assert (root/'api.md').read_text(encoding='utf-8') == 'hello'


def test_professional_skill_blocks_workspace_escape(tmp_path):
    root=tmp_path/"work"; root.mkdir(); outside=tmp_path/"outside.csv"; write_csv(outside)
    runtime=ProfessionalRuntime(WorkRuntime((root,)))
    with pytest.raises((ProfessionalRuntimeError, Exception)):
        runtime.validate(ProfessionalActionIntent(action="analytics.analyze",workspace=str(root),arguments={"path":"../outside.csv"}))
