"""0.5 contract tests: UIA is faked. E2E on Windows is a separate release gate."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from oryven.api import create_app
from oryven.computer_control import WindowInspector, ComputerControlError
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.governance import ApprovalError, ApprovalStore
from oryven.models import WindowButtonIntent
from oryven.window_actions import WindowActions, WindowActionError


class FakeWindow:
    def __init__(self, title="Untitled - Notepad", pid=111, buttons=None):
        self.handle = 7331
        self._title = title
        self.active = False
        self.state = 0
        self._children = buttons or []
        self.element_info = SimpleNamespace(process_id=pid, class_name="Notepad", name=title,
                                            control_type="Window", is_password=False)
    def is_visible(self): return True
    def is_enabled(self): return True
    def window_text(self): return self._title
    def children(self): return self._children
    def set_focus(self): self.active = True
    def is_active(self): return self.active
    def get_show_state(self): return self.state


class FakeButton:
    def __init__(self, window, name="Maximize", automation_id="MaxButton", enabled=True):
        self.window = window
        self.name = name
        self.enabled = enabled
        self.invocations = 0
        self.effect = True
        self.element_info = SimpleNamespace(name=name, automation_id=automation_id,
                                            control_type="Button", is_password=False)
    def is_visible(self): return True
    def is_enabled(self): return self.enabled
    def children(self): return []
    def invoke(self):
        self.invocations += 1
        if self.effect:
            self.window.state = {"maximize":1,"maximizar":1,"minimize":2,"minimizar":2,
                                 "restore":0,"restaurar":0}[self.name.casefold()]


class FakeDesktop:
    def __init__(self, holder): self.holder = holder
    def windows(self): return self.holder[:]


class Speaker:
    enabled = False
    provider = "fake"
    def say(self, text): pass
    def stop(self): pass

class Listener:
    running = False
    def stop(self): pass


def setup():
    w = FakeWindow()
    button = FakeButton(w)
    w._children = [button]
    holder = [w]
    inspector = WindowInspector(platform="win32", desktop_factory=lambda backend: FakeDesktop(holder))
    actions = WindowActions(inspector, sleeper=lambda s:None)
    return w, button, holder, inspector, actions


def core_for(tmp_path, actions):
    return OryvenCore(Settings(data_dir=tmp_path, model_dir=tmp_path/'absent'),
                      speaker=Speaker(), listener=Listener(), window_actions=actions)


def test_inspection_exposes_only_safe_action_paths():
    w, button, holder, inspector, actions = setup()
    w._children.append(FakeButton(w, name="Delete", automation_id="Destroy"))
    tree = inspector.inspect_window(w.handle)
    assert tree['elements'][1]['path'] == [0]
    assert tree['elements'][1]['eligible_action'] == 'computer.button.invoke'
    assert tree['elements'][2]['eligible_action'] is None


def test_window_focus_is_bound_and_verified():
    w, button, holder, inspector, actions = setup()
    intent = actions.preview_focus(w.handle)
    assert w.active is False
    result = actions.execute_focus(intent)
    assert result['outcome']=='verified' and result['verified']
    assert w.active is True


def test_button_requires_grant_and_verifies_state(tmp_path):
    w, button, holder, inspector, actions = setup()
    core = core_for(tmp_path, actions)
    proposal = core.propose_window_button(w.handle, (0,))
    assert button.invocations == 0 and core.status()['pending_approvals'] == 1
    result = core.decide(proposal['id'], 'approve')
    assert result['outcome']=='verified' and result['data']['observed_state'] == 1
    assert button.invocations == 1 and w.state == 1
    with pytest.raises(ApprovalError): core.decide(proposal['id'], 'approve')
    assert core.audit.list() and 'MaxButton' not in str(core.audit.list())


def test_denied_and_emergency_stopped_never_invoke(tmp_path):
    w, button, holder, inspector, actions = setup()
    core=core_for(tmp_path, actions)
    p=core.propose_window_button(w.handle,(0,))
    assert core.decide(p['id'], 'deny')['outcome']=='denied'
    p=core.propose_window_button(w.handle,(0,))
    core.emergency_stop()
    with pytest.raises(ApprovalError): core.decide(p['id'], 'approve')
    assert button.invocations == 0


def test_stale_window_pid_title_and_handle_are_refused(tmp_path):
    w, button, holder, inspector, actions = setup()
    p=actions.preview_button(w.handle,(0,))
    w.element_info.process_id = 222
    with pytest.raises(WindowActionError, match='identidade'): actions.execute_button(p)
    w.element_info.process_id = 111
    w._title = 'Other'
    with pytest.raises(WindowActionError, match='identidade'): actions.execute_button(p)
    w._title = 'Untitled - Notepad'
    holder.clear()
    with pytest.raises(WindowActionError, match='Janela'): actions.execute_button(p)
    assert button.invocations == 0


def test_stale_button_path_name_and_automation_id_are_refused():
    w, button, holder, inspector, actions = setup()
    p=actions.preview_button(w.handle,(0,))
    button.element_info.automation_id = 'other'
    with pytest.raises(WindowActionError, match='botão mudou'): actions.execute_button(p)
    assert button.invocations == 0
    button.element_info.automation_id = 'MaxButton'
    w._children=[FakeButton(w,'Delete')]
    with pytest.raises(WindowActionError): actions.execute_button(p)


def test_delete_confirm_send_edit_password_and_overdeep_paths_never_invoke():
    w, button, holder, inspector, actions = setup()
    for forbidden in ('Delete','Confirm','Enviar','OK','Help','Sobre'):
        w._children = [FakeButton(w, name=forbidden)]
        with pytest.raises(WindowActionError): actions.preview_button(w.handle,(0,))
    w._children = [button]
    with pytest.raises(WindowActionError): actions.preview_button(w.handle, (0,0,0))
    with pytest.raises(WindowActionError): actions.preview_button(w.handle, (25,))
    button.element_info.is_password = True
    with pytest.raises(WindowActionError): actions.preview_button(w.handle,(0,))
    assert button.invocations == 0


def test_unverified_effect_does_not_claim_success():
    w, button, holder, inspector, actions = setup()
    p=actions.preview_button(w.handle,(0,))
    button.effect=False
    result=actions.execute_button(p)
    assert result['outcome']=='unverified' and result['verified'] is False
    assert button.invocations == 1 and w.state == 0
    # No automatic retry on uncertain effects.


@pytest.mark.parametrize('name,start,target',[
    ('Maximize',0,1), ('Maximizar',0,1), ('Restore',1,0),
    ('Restaurar',1,0), ('Minimize',0,2), ('Minimizar',0,2)
])
def test_safe_button_variants_and_state_confirmation(name,start,target):
    w, button, holder, inspector, actions = setup()
    button.name=name
    button.element_info.name=name
    w.state=start
    intent=actions.preview_button(w.handle,(0,))
    result=actions.execute_button(intent)
    assert result['verified'] and result['before_state']==start
    assert result['observed_state']==target and button.invocations==1


def test_disabled_button_is_rejected():
    w, button, holder, inspector, actions = setup()
    button.enabled = False
    with pytest.raises(WindowActionError,match='habilitado'):
        actions.preview_button(w.handle,(0,))
    assert button.invocations == 0


def test_no_invoke_if_already_in_target_state():
    w, button, holder, inspector, actions = setup()
    p=actions.preview_button(w.handle,(0,))
    w.state=1
    with pytest.raises(WindowActionError,match='já está'): actions.execute_button(p)
    assert button.invocations == 0


def test_invalid_control_cannot_be_preapproved_even_through_api(tmp_path):
    w, button, holder, inspector, actions = setup()
    core=core_for(tmp_path, actions)
    with TestClient(create_app(core)) as client:
        assert client.post('/api/control/window/focus/propose',json={'handle':w.handle}).status_code==401
        token=client.get('/api/session').json()['session_token']
        h={'X-Oryven-Session':token}
        bad=client.post('/api/control/window/button/propose',headers=h,
                        json={'handle':w.handle,'path':[77]})
        assert bad.status_code==409
        proposal=client.post('/api/control/window/button/propose',headers=h,
                             json={'handle':w.handle,'path':[0]})
        assert proposal.status_code==200
        assert button.invocations==0
        pid=proposal.json()['pending']['id']
        result=client.post(f'/api/actions/{pid}/decision',headers=h,json={'decision':'approve'})
        assert result.status_code==200 and result.json()['outcome']=='verified'
        assert button.invocations==1
        assert client.post(f'/api/actions/{pid}/decision',headers=h,json={'decision':'approve'}).status_code==409


def test_approval_fingerprint_includes_window_snapshot_and_path():
    w, button, holder, inspector, actions = setup()
    first=actions.preview_button(w.handle,(0,))
    store=ApprovalStore()
    fp=store.fingerprint_for(first)
    mutated=first.model_copy(update={'window_title':'Other'})
    assert store.fingerprint_for(mutated) != fp
    mutated=first.model_copy(update={'button_automation_id':'Different'})
    assert store.fingerprint_for(mutated) != fp
    mutated=first.model_copy(update={'path':(1,)})
    assert store.fingerprint_for(mutated) != fp


def test_window_button_not_available_on_nonwindows():
    inspector=WindowInspector(platform='linux')
    with pytest.raises(ComputerControlError):
        WindowActions(inspector).preview_focus(123)


def test_api_nonwindows_returns_controlled_error(tmp_path):
    inspector=WindowInspector(platform='linux')
    core=core_for(tmp_path,WindowActions(inspector))
    with TestClient(create_app(core)) as client:
        h={'X-Oryven-Session':client.get('/api/session').json()['session_token']}
        response=client.post('/api/control/window/focus/propose',headers=h,json={'handle':7331})
        assert response.status_code==409
        assert 'Windows' in response.json()['detail']
