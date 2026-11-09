import json
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.context_engine import WORKSPACE_TOKEN


class Speaker:
    enabled=False; provider='test'; speaking=False
    def say(self, text): pass
    def stop(self): pass
class Listener:
    running=False
    def stop(self): pass
class Bridge:
    def __init__(self, response): self.response=response; self.prompts=[]
    def plan_json(self, prompt): self.prompts.append(prompt); return self.response
    def check(self): return {'reachable': True}


def core_for(tmp_path, workspace, response='{}'):
    settings=Settings(data_dir=tmp_path/'data', model_dir=tmp_path/'model', work_roots=(workspace,), developer_roots=(workspace,), buno_bearer_token='x')
    return OryvenCore(settings, speaker=Speaker(), listener=Listener(), buno_bridge=Bridge(response))


def test_context_engine_active_project_selects_relevant_memory_and_hides_workspace(tmp_path):
    workspace=tmp_path/'private'/'flow-commerce'; workspace.mkdir(parents=True)
    core=core_for(tmp_path, workspace)
    p=core.create_project('Flow Commerce', str(workspace), 'Gestão de pedidos e auditoria')
    core.remember_professional('O backend do Flow Commerce usa Java e Spring Boot.', 'decision', p['id'])
    core.remember_professional('A campanha institucional usa linguagem simples.', 'preference', p['id'])
    core.remember_professional('Preferir respostas objetivas.', 'preference', None)
    core.set_active_project(p['id'])
    preview=core.context_preview('corrija o backend Java do Flow Commerce')
    assert preview['public_context']['workspace'] == WORKSPACE_TOKEN
    assert str(workspace) not in json.dumps(preview['public_context'])
    notes=preview['public_context']['memory_notes']
    assert any('Java' in x for x in notes)
    assert preview['local_context']['workspace'] == '[workspace local protegido]'
    assert preview['permissions_granted'] is False


def test_buno_planner_gets_token_not_absolute_path_and_binding_returns_real_workspace(tmp_path):
    workspace=tmp_path/'secret-user-folder'/'project'; workspace.mkdir(parents=True)
    response=json.dumps({'agent_id':'software.engineering','rationale':'inspect','steps':[{'skill_id':'workspace.inspect','arguments':{'workspace':WORKSPACE_TOKEN}}]})
    core=core_for(tmp_path, workspace, response)
    p=core.create_project('Private Project', str(workspace), 'Backend Python')
    core.set_active_project(p['id'])
    plan=core.plan_buno_ai_mission('inspecione este projeto Python')
    assert plan['steps'][0]['arguments']['workspace'] == str(workspace.resolve())
    prompt=core.buno_bridge.prompts[0]
    assert str(workspace) not in prompt
    assert WORKSPACE_TOKEN in prompt


def test_active_project_feeds_local_autonomous_planner_without_explicit_workspace(tmp_path):
    workspace=tmp_path/'python-app'; workspace.mkdir(); (workspace/'pyproject.toml').write_text('[project]\nname="x"\n')
    core=core_for(tmp_path, workspace)
    p=core.create_project('Python App', str(workspace))
    core.set_active_project(p['id'])
    plan=core.plan_autonomous_mission('corrija e teste este backend Python')
    assert plan['status'] == 'ready'
    assert any(step['arguments'].get('workspace') == str(workspace.resolve()) for step in plan['steps'])


def test_context_api_activate_preview_and_project_delete_clears_active(tmp_path):
    workspace=tmp_path/'project'; workspace.mkdir()
    core=core_for(tmp_path, workspace)
    app=create_app(core)
    with TestClient(app) as client:
        h={'X-Oryven-Session': client.get('/api/session').json()['session_token']}
        p=client.post('/api/projects', headers=h, json={'name':'Project X','workspace':str(workspace),'description':'dados'}).json()
        assert client.patch('/api/context/active-project', headers=h, json={'project_id':p['id']}).status_code == 200
        status=client.get('/api/context', headers=h).json()
        assert status['active_project']['id'] == p['id']
        preview=client.post('/api/context/preview', headers=h, json={'objective':'analise este projeto','context':{}})
        assert preview.status_code == 200
        assert preview.json()['public_context']['workspace'] == WORKSPACE_TOKEN
        assert client.delete(f"/api/projects/{p['id']}", headers=h).status_code == 200
        assert client.get('/api/context', headers=h).json()['active_project'] is None
