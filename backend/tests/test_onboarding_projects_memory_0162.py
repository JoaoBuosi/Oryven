import sqlite3
from fastapi.testclient import TestClient

from oryven.accounts import AccountStore
from oryven.api import create_app
from oryven.device_vault import DeviceSessionVault
from oryven.professional_memory import ProfessionalMemory, ProfessionalMemoryError
from oryven.projects import ProjectStore


class DummyMailer:
    def __init__(self):
        self.sent = []
    def send_code(self, email, code, purpose):
        self.sent.append((email, code, purpose))

def local_headers(client):
    token = client.get('/api/session').json()['session_token']
    return {'X-Oryven-Session': token}, token

def register_verified(client, mailer, name, email, password='StrongPass123'):
    h, _ = local_headers(client)
    r = client.post('/api/auth/register', headers=h, json={'name': name, 'email': email, 'password': password})
    assert r.status_code == 200, r.text
    code = next(code for target, code, purpose in reversed(mailer.sent) if target == email.lower() and purpose == 'verify_email')
    r = client.post('/api/auth/verify-email', headers=h, json={'email': email, 'code': code})
    assert r.status_code == 200, r.text
    return h, r.json()



def authed_client(tmp_path, monkeypatch, email='alice@example.com'):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path / 'data'))
    mailer = DummyMailer()
    store = AccountStore(tmp_path / 'data' / 'accounts.sqlite3')
    vault = DeviceSessionVault(tmp_path / 'data' / 'device_session.bin')
    client = TestClient(create_app(account_store=store, mailer=mailer, vault=vault))
    local, login = register_verified(client, mailer, 'Alice', email)
    headers = {**local, 'Authorization': f"Bearer {login['access_token']}"}
    return client, headers, login['user']['id']


def test_project_store_and_memory_are_persistent_and_project_scoped(tmp_path):
    projects = ProjectStore(tmp_path / 'projects.sqlite3')
    memory = ProfessionalMemory(tmp_path / 'memory.sqlite3')
    p1 = projects.create('Flow Commerce', str(tmp_path / 'flow'))
    p2 = projects.create('Oryven', str(tmp_path / 'oryven'))
    memory.remember('Usar Java no backend.', 'decision', p1['id'])
    memory.remember('Preferir respostas curtas.', 'preference', p2['id'])
    assert len(ProfessionalMemory(tmp_path / 'memory.sqlite3').list(p1['id'])) == 1
    assert ProfessionalMemory(tmp_path / 'memory.sqlite3').list(p1['id'])[0]['content'] == 'Usar Java no backend.'


def test_professional_memory_rejects_secrets_and_can_be_disabled(tmp_path):
    memory = ProfessionalMemory(tmp_path / 'memory.sqlite3')
    try:
        memory.remember('API_KEY=abcdef', 'fact')
        assert False, 'secret should be rejected'
    except ProfessionalMemoryError:
        pass
    memory.set_enabled(False)
    try:
        memory.remember('Preferir relatórios em português.', 'preference')
        assert False, 'disabled memory should reject writes'
    except ProfessionalMemoryError:
        pass


def test_authenticated_api_onboarding_projects_memory_and_delete_cascade(tmp_path, monkeypatch):
    client, headers, _user_id = authed_client(tmp_path, monkeypatch)
    onboarding = client.get('/api/onboarding', headers=headers)
    assert onboarding.status_code == 200
    assert onboarding.json()['completed'] is False

    project = client.post('/api/projects', headers=headers, json={
        'name': 'Flow Commerce', 'workspace': str(tmp_path / 'flow'), 'description': 'SaaS de pedidos'
    })
    assert project.status_code == 200, project.text
    pid = project.json()['id']

    updated = client.patch('/api/onboarding', headers=headers, json={
        'assistant_named': True, 'voice_configured': True, 'permissions_reviewed': True
    })
    assert updated.status_code == 200
    assert updated.json()['completed'] is True  # workspace flag set automatically on project creation

    remembered = client.post('/api/memory/professional', headers=headers, json={
        'content': 'O backend principal usa Java.', 'kind': 'fact', 'project_id': pid
    })
    assert remembered.status_code == 200, remembered.text
    listed = client.get(f'/api/memory/professional?project_id={pid}', headers=headers)
    assert len(listed.json()['memories']) == 1

    deleted = client.delete(f'/api/projects/{pid}', headers=headers)
    assert deleted.status_code == 200
    assert client.get('/api/memory/professional', headers=headers).json()['memories'] == []


def test_user_isolation_for_projects_and_professional_memory(tmp_path, monkeypatch):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path / 'data'))
    mailer = DummyMailer()
    store = AccountStore(tmp_path / 'data' / 'accounts.sqlite3')
    vault = DeviceSessionVault(tmp_path / 'data' / 'vault.bin')
    client = TestClient(create_app(account_store=store, mailer=mailer, vault=vault))
    local, alice = register_verified(client, mailer, 'Alice', 'alice@example.com')
    a = {**local, 'Authorization': f"Bearer {alice['access_token']}"}
    p = client.post('/api/projects', headers=a, json={'name':'Alice Project','workspace':str(tmp_path/'alice')}).json()
    assert client.post('/api/memory/professional', headers=a, json={'content':'Preferir Java.','kind':'preference','project_id':p['id']}).status_code == 200
    assert client.post('/api/auth/logout', headers=a).status_code == 200

    local2, bob = register_verified(client, mailer, 'Bob', 'bob@example.com')
    b = {**local2, 'Authorization': f"Bearer {bob['access_token']}"}
    assert client.get('/api/projects', headers=b).json()['projects'] == []
    assert client.get('/api/memory/professional', headers=b).json()['memories'] == []
