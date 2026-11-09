from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.apps import AppCatalog, AppDiscoveryError
from oryven.computer_control import WindowInspector
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.governance import ApprovalStore
from oryven.window_actions import WindowActions, WindowActionError


class Speaker:
    enabled = False
    provider = "test"
    def say(self, text): pass
    def stop(self): pass


class Listener:
    running = False
    def stop(self): pass


class FakeControl:
    def __init__(self, typ, name, automation_id, *, password=False):
        self.element_info = SimpleNamespace(control_type=typ, name=name, automation_id=automation_id,
                                            is_password=password)
        self.invocations = 0
        self.value = name if typ == "Edit" else ""
        self._children = []
    def is_visible(self): return True
    def is_enabled(self): return True
    def children(self): return self._children
    def invoke(self): self.invocations += 1
    def set_edit_text(self, text): self.value = text
    def get_value(self): return self.value


class FakeWindow:
    def __init__(self, children):
        self.handle = 90210
        self._title = "Universal App"
        self._children = children
        self.active = False
        self.element_info = SimpleNamespace(process_id=321, class_name="UniversalWindow", name=self._title,
                                            control_type="Window", is_password=False)
    def is_visible(self): return True
    def is_enabled(self): return True
    def window_text(self): return self._title
    def children(self): return self._children
    def set_focus(self): self.active = True
    def is_active(self): return self.active


class FakeDesktop:
    def __init__(self, window): self.window = window
    def windows(self): return [self.window]


def make_window_stack():
    safe = FakeControl("Button", "Open", "OpenButton")
    dangerous = FakeControl("Button", "Delete", "DeleteButton")
    edit = FakeControl("Edit", "conteudo-privado-atual", "SearchBox")
    password = FakeControl("Edit", "senha-super-secreta", "PasswordBox", password=True)
    window = FakeWindow([safe, dangerous, edit, password])
    inspector = WindowInspector(platform="win32", desktop_factory=lambda backend: FakeDesktop(window))
    actions = WindowActions(inspector, sleeper=lambda _: None)
    return window, safe, dangerous, edit, password, inspector, actions


def make_core(tmp_path, *, actions=None, app_catalog=None):
    return OryvenCore(Settings(data_dir=tmp_path / "data", model_dir=tmp_path / "model"),
                      speaker=Speaker(), listener=Listener(), window_actions=actions,
                      app_catalog=app_catalog)


def test_inspector_exposes_safe_generic_controls_and_redacts_edit_values():
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    tree = inspector.inspect_window(window.handle)
    nodes = {tuple(x["path"]): x for x in tree["elements"]}
    assert nodes[(0,)]["eligible_action"] == "computer.control.invoke"
    assert nodes[(1,)]["eligible_action"] is None
    assert nodes[(2,)]["eligible_action"] == "computer.control.set_text"
    assert nodes[(2,)]["name"] == "[omitido: conteúdo editável]"
    assert nodes[(2,)]["automation_id"] == "SearchBox"
    assert nodes[(3,)]["eligible_action"] is None
    serialized = str(tree)
    assert "conteudo-privado-atual" not in serialized
    assert "senha-super-secreta" not in serialized


def test_generic_invoke_requires_preview_identity_and_never_claims_verified():
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    intent = actions.preview_invoke(window.handle, (0,))
    assert safe.invocations == 0
    result = actions.execute_invoke(intent)
    assert safe.invocations == 1
    assert result["outcome"] == "unverified"
    assert result["verified"] is False
    safe.element_info.name = "Changed"
    with pytest.raises(WindowActionError):
        actions.execute_invoke(intent)


def test_dangerous_generic_button_cannot_be_preapproved():
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    with pytest.raises(WindowActionError):
        actions.preview_invoke(window.handle, (1,))
    assert dangerous.invocations == 0


def test_text_input_hides_old_and_new_text_from_human_description_and_verifies():
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    new_text = "nova consulta confidencial"
    intent = actions.preview_set_text(window.handle, (2,), new_text)
    assert intent.control_name == ""
    store = ApprovalStore()
    pending = store.propose(intent)
    assert new_text not in pending.description
    assert "conteudo-privado-atual" not in pending.description
    assert "SearchBox" in pending.description
    result = actions.execute_set_text(store.decide(pending.id, True))
    assert result["verified"] is True
    assert edit.value == new_text


def test_password_and_append_are_rejected():
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    with pytest.raises(WindowActionError):
        actions.preview_set_text(window.handle, (3,), "x")
    with pytest.raises(WindowActionError):
        actions.preview_set_text(window.handle, (2,), "x", replace=False)


def test_dynamic_app_launch_uses_only_discovered_target_and_revalidates(tmp_path):
    exe = tmp_path / "tool.exe"; exe.write_bytes(b"MZ")
    launched = []
    catalog = AppCatalog(platform="win32", entries=[{
        "name": "Tool Pro", "version": "1", "launchable": True,
        "launch_target": str(exe), "target_type": "executable", "source": "test",
    }], launcher=lambda target, kind: launched.append((target, kind)) or True)
    core = make_core(tmp_path, app_catalog=catalog)
    pending = core.propose_app_launch("Tool Pro")
    assert launched == []
    result = core.decide(pending["id"], "approve")
    assert result["outcome"] == "verified"
    assert launched == [(str(exe.resolve()), "executable")]
    with pytest.raises(Exception): core.decide(pending["id"], "approve")


def test_app_catalog_rejects_ambiguous_and_arbitrary_names(tmp_path):
    a = tmp_path / "alpha.exe"; a.write_bytes(b"MZ")
    b = tmp_path / "alpha-beta.exe"; b.write_bytes(b"MZ")
    catalog = AppCatalog(platform="win32", entries=[
        {"name":"Alpha One","launchable":True,"launch_target":str(a),"target_type":"executable"},
        {"name":"Alpha Two","launchable":True,"launch_target":str(b),"target_type":"executable"},
    ])
    with pytest.raises(AppDiscoveryError, match="ambíguo"):
        catalog.resolve("Alpha")
    with pytest.raises(AppDiscoveryError, match="não encontrado"):
        catalog.resolve("cmd.exe /c evil")


def test_universal_operator_api_flow(tmp_path):
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    exe = tmp_path / "tool.exe"; exe.write_bytes(b"MZ")
    launched = []
    catalog = AppCatalog(platform="win32", entries=[{
        "name":"Tool Pro","launchable":True,"launch_target":str(exe),"target_type":"executable"
    }], launcher=lambda target, kind: launched.append(target) or True)
    core = make_core(tmp_path, actions=actions, app_catalog=catalog)
    with TestClient(create_app(core)) as client:
        h = {"X-Oryven-Session": client.get("/api/session").json()["session_token"]}
        assert client.get("/api/apps", headers=h).json()["apps"][0]["launchable"] is True
        p = client.post("/api/apps/launch/propose", headers=h, json={"app_name":"Tool Pro"}).json()["pending"]
        assert launched == []
        assert client.post(f"/api/actions/{p['id']}/decision", headers=h, json={"decision":"approve"}).json()["outcome"] == "verified"
        invoke = client.post("/api/control/window/invoke/propose", headers=h,
                             json={"handle":window.handle,"path":[0]})
        assert invoke.status_code == 200 and safe.invocations == 0
        pid = invoke.json()["pending"]["id"]
        assert client.post(f"/api/actions/{pid}/decision", headers=h, json={"decision":"approve"}).json()["outcome"] == "unverified"
        text = client.post("/api/control/window/text/propose", headers=h,
                           json={"handle":window.handle,"path":[2],"text":"oryven","replace":True})
        assert text.status_code == 200
        assert "oryven" not in str(text.json())
        tid = text.json()["pending"]["id"]
        done = client.post(f"/api/actions/{tid}/decision", headers=h, json={"decision":"approve"}).json()
        assert done["outcome"] == "verified" and edit.value == "oryven"


def test_professional_agents_receive_universal_operator_skills(tmp_path):
    window, safe, dangerous, edit, password, inspector, actions = make_window_stack()
    core = make_core(tmp_path, actions=actions)
    plan = core.professional_plan("prepare uma campanha de marketing")
    ids = {item["id"] for item in plan["recommended_skills"]}
    assert "app.launch.universal" in ids
    assert "computer.control.invoke" in ids
    assert "computer.control.set_text" in ids
    assert plan["orchestration"]["permissions_granted"] is False
