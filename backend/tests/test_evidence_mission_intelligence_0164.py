import json
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.context_engine import WORKSPACE_TOKEN
from oryven.core import OryvenCore
from oryven.mission_intelligence import MissionIntelligenceStore


class Speaker:
    enabled=False; provider='test'; speaking=False
    def say(self, text): pass
    def stop(self): pass
class Listener:
    running=False
    def stop(self): pass
class Bridge:
    def __init__(self, response): self.response=response
    def plan_json(self, prompt): return self.response
    def check(self): return {'reachable': True}


def core_for(tmp_path, workspace, response='{}'):
    settings=Settings(data_dir=tmp_path/'data', model_dir=tmp_path/'model', work_roots=(workspace,), developer_roots=(workspace,), buno_bearer_token='x')
    return OryvenCore(settings, speaker=Speaker(), listener=Listener(), buno_bridge=Bridge(response))


def test_evidence_store_redacts_paths_and_secret_keys(tmp_path):
    store=MissionIntelligenceStore(tmp_path/'intel.sqlite3')
    store.register('m1', planner='test', reason_summary='short reason', context={
        'workspace': r'C:\\Users\\Joao\\private-project', 'token': 'super-secret', 'project_name': 'Demo'
    })
    store.add('m1', phase='execution', outcome='failed', summary=r'Falhou em C:\\Users\\Joao\\private-project', evidence={'api_key':'abc'})
    view=store.get('m1')
    raw=json.dumps(view, ensure_ascii=False)
    assert 'private-project' not in raw
    assert 'super-secret' not in raw
    assert 'abc' not in raw
    assert view['chain_of_thought_exposed'] is False


def test_buno_mission_intelligence_records_minimized_context_and_reason(tmp_path):
    workspace=tmp_path/'private-user'/'project'; workspace.mkdir(parents=True)
    response=json.dumps({'agent_id':'software.engineering','rationale':'Inspecionar o workspace e validar o estado do projeto.','steps':[{'skill_id':'workspace.inspect','arguments':{'workspace':WORKSPACE_TOKEN}}]})
    core=core_for(tmp_path, workspace, response)
    project=core.create_project('Projeto Privado', str(workspace), 'Backend')
    core.remember_professional('Usar Python para este backend.', 'decision', project['id'])
    core.set_active_project(project['id'])
    mission=core.start_buno_ai_mission('inspecione este backend Python')
    intel=core.mission_intelligence_view(mission['id'])
    assert intel['planner']=='buno-ai'
    assert intel['agent_id']=='software.engineering'
    assert 'Inspecionar' in intel['reason_summary']
    raw=json.dumps(intel, ensure_ascii=False)
    assert str(workspace) not in raw
    assert intel['selected_memory_ids']
    assert any(e['phase']=='proposal' for e in intel['events'])


def test_manual_verification_adds_evidence_event(tmp_path):
    workspace=tmp_path/'project'; workspace.mkdir()
    core=core_for(tmp_path, workspace)
    mission=core.start_skill_mission('criar pasta', [type('S', (), {'skill_id':'filesystem.mkdir','arguments':{'workspace':str(workspace),'path':'reports'}})])
    action=mission['steps'][0]['action_id']
    result=core.decide(action, 'approve')
    assert result['outcome']=='completed'
    core.verify_mission_step(mission['id'], True)
    intel=core.mission_intelligence_view(mission['id'])
    assert any(e['phase']=='execution' for e in intel['events'])
    assert any(e['phase']=='verification' and e['outcome']=='verified_by_user' for e in intel['events'])


def test_intelligence_api_returns_explainability_without_internal_reasoning(tmp_path):
    workspace=tmp_path/'project'; workspace.mkdir()
    core=core_for(tmp_path, workspace)
    app=create_app(core)
    with TestClient(app) as client:
        h={'X-Oryven-Session': client.get('/api/session').json()['session_token']}
        mission=client.post('/api/missions', headers=h, json={'text':'pesquise OpenAI'}).json()
        res=client.get(f"/api/missions/{mission['id']}/intelligence", headers=h)
        assert res.status_code==200
        payload=res.json()
        assert payload['planner']=='deterministic-text'
        assert payload['chain_of_thought_exposed'] is False
        assert payload['events'][0]['phase']=='proposal'
