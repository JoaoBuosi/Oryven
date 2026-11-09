from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.executor import BrowserExecutor
from oryven.missions import MissionError, MissionStore, plan_text


class FakeSpeaker:
    enabled = True
    provider = 'fake'
    def say(self, text): pass
    def stop(self): pass

class FakeListener:
    running = False
    def stop(self): pass


def make_core(tmp_path):
    dispatched = []
    class FakeApps:
        def execute(self, intent):
            dispatched.append('app:' + intent.app_id)
            return 'Solicitei abertura; execução não verificada.'
    core = OryvenCore(Settings(data_dir=tmp_path, model_dir=tmp_path/'missing'),
                      executor=BrowserExecutor(opener=lambda url, new: dispatched.append(url) or True),
                      app_executor=FakeApps(), speaker=FakeSpeaker(), listener=FakeListener())
    return core, dispatched


def test_planner_rejects_partial_or_unsafe_plans():
    p = plan_text('Abra a calculadora e depois abra o bloco de notas')
    assert [x.kind for x in p] == ['app.launch', 'app.launch']
    assert [x.app_id for x in p] == ['calculator','notepad']
    for text in ['Abra a calculadora e depois apague os arquivos',
                 'execute o PowerShell', 'abra a calculadora e depois abra o cmd',
                 'abra o navegador e pesquise ai e depois abra o bloco de notas e depois abra a calculadora e depois abra o explorador']:
        with pytest.raises(MissionError): plan_text(text)


def test_two_step_mission_needs_two_approvals_and_manual_checks(tmp_path):
    core, dispatched = make_core(tmp_path)
    mission = core.start_mission('Abra a calculadora e depois abra o bloco de notas')
    assert mission['status'] == 'awaiting_approval' and len(mission['steps']) == 2
    assert dispatched == []
    first_id = mission['steps'][0]['action_id']
    assert core.decide(first_id, 'approve')['outcome'] == 'dispatched'
    assert dispatched == ['app:calculator']
    assert core.missions.get(mission['id'])['status'] == 'awaiting_verification'
    assert len(core.approvals.list_pending()) == 0
    nxt = core.verify_mission_step(mission['id'], True)
    assert nxt['status'] == 'awaiting_approval'
    second_id = nxt['steps'][1]['action_id']
    assert core.decide(second_id, 'approve')['outcome']=='dispatched'
    final = core.verify_mission_step(mission['id'], True)
    assert final['status']=='completed'
    assert [s['status'] for s in final['steps']] == ['verified_by_user','verified_by_user']
    assert dispatched == ['app:calculator','app:notepad']


def test_denial_cancels_mission(tmp_path):
    core, dispatched = make_core(tmp_path)
    m = core.start_mission('pesquise inteligencia artificial')
    assert core.decide(m['steps'][0]['action_id'], 'deny')['outcome'] == 'denied'
    assert core.missions.get(m['id'])['status'] == 'cancelled'
    assert dispatched == []


def test_restart_does_not_reuse_authorizations(tmp_path):
    core, _ = make_core(tmp_path)
    mission = core.start_mission('Abra a calculadora')
    old_id = mission['steps'][0]['action_id']
    restarted, dispatched = make_core(tmp_path)
    assert restarted.missions.get(mission['id'])['status']=='paused'
    with pytest.raises(Exception): restarted.decide(old_id,'approve')
    resumed = restarted.resume_mission(mission['id'])
    assert resumed['steps'][0]['action_id'] != old_id
    assert not dispatched


def test_emergency_stop_pauses_and_invalidates(tmp_path):
    core, dispatched = make_core(tmp_path)
    m=core.start_mission('Abra a calculadora e depois abra o bloco de notas')
    old=m['steps'][0]['action_id']
    core.emergency_stop()
    assert core.missions.get(m['id'])['status'] == 'paused'
    with pytest.raises(Exception): core.decide(old,'approve')
    assert dispatched == []


def test_api_mission_lifecycle_and_rejected_unknown(tmp_path):
    core, dispatched = make_core(tmp_path)
    with TestClient(create_app(core)) as client:
        headers={'X-Oryven-Session':client.get('/api/session').json()['session_token']}
        assert client.post('/api/missions',json={'text':'abra o powershell'},headers=headers).status_code == 422
        resp = client.post('/api/missions',json={'text':'pesquise inteligência artificial'},headers=headers)
        assert resp.status_code == 200
        mission=resp.json()
        assert client.get('/api/missions',headers=headers).json()[0]['id'] == mission['id']
        action=mission['steps'][0]['action_id']
        assert client.post(f'/api/actions/{action}/decision',json={'decision':'approve'},headers=headers).status_code==200
        assert client.get(f"/api/missions/{mission['id']}",headers=headers).json()['status'] == 'awaiting_verification'
        assert client.post(f"/api/missions/{mission['id']}/verify",json={'confirmed':True},headers=headers).json()['status']=='completed'
        assert len(dispatched)==1
        assert client.post(f"/api/missions/{mission['id']}/verify",json={'confirmed':True},headers=headers).status_code==409
        assert client.get('/api/missions',headers={'Origin':'https://attacker.example',**headers}).status_code==403


def test_crash_during_execution_does_not_retry(tmp_path):
    store = MissionStore(tmp_path/'missions.sqlite3')
    mission = store.create('Abra a calculadora',plan_text('Abra a calculadora'))
    store.proposed(mission['id'],0,'approved-1')
    store.executing(mission['id'],'approved-1')
    restarted = MissionStore(tmp_path/'missions.sqlite3')
    assert restarted.get(mission['id'])['status']=='needs_review'
    with pytest.raises(MissionError): restarted.next_intent(mission['id'])


def test_browser_and_search_is_single_safe_step_and_multi_is_not_skipped(tmp_path):
    one = plan_text('Abra o navegador e pesquise inteligência artificial')
    assert len(one) == 1 and one[0].kind == 'browser.search'
    core, dispatched = make_core(tmp_path)
    # Previously parse_search could silently skip a preceding launch action.
    pending = core.submit('Abra a calculadora e depois pesquise inteligência artificial')
    assert pending['status'] == 'awaiting_approval'
    assert len(pending['steps']) == 2
    assert not dispatched
    refused = core.submit('Abra a calculadora e depois apague meus arquivos')
    assert refused is None
    assert len(core.missions.list()) == 1


def test_cancel_revokes_approval_and_delete_history(tmp_path):
    core, dispatched = make_core(tmp_path)
    mission = core.start_mission('abra a calculadora')
    action = mission['steps'][0]['action_id']
    core.cancel_mission(mission['id'])
    with pytest.raises(Exception): core.decide(action, 'approve')
    assert dispatched == []
    assert core.delete_mission(mission['id'])['status'] == 'deleted'
    assert core.missions.list() == []


def test_expired_approval_can_resume_with_new_token(tmp_path):
    core, dispatched = make_core(tmp_path)
    mission = core.start_mission('abra a calculadora')
    action = mission['steps'][0]['action_id']
    core.approvals.cancel_one(action)  # emulate TTL pruning
    resumed = core.resume_mission(mission['id'])
    assert resumed['steps'][0]['action_id'] != action
    assert not dispatched


def test_cancel_after_dispatch_preserves_unverified_fact(tmp_path):
    core, _ = make_core(tmp_path)
    mission=core.start_mission('pesquise IA')
    core.decide(mission['steps'][0]['action_id'], 'approve')
    cancelled=core.cancel_mission(mission['id'])
    assert cancelled['status']=='cancelled'
    assert cancelled['steps'][0]['status']=='unverified'
