from fastapi.testclient import TestClient
from oryven.release_info import VERSION

from oryven.accounts import AccountStore
from oryven.api import create_app
from oryven.device_vault import DeviceSessionVault


class DummyMailer:
    def __init__(self):
        self.sent = []
    def send_code(self, email, code, purpose):
        self.sent.append((email, code, purpose))


def _session_headers(client):
    token = client.get('/api/session').json()['session_token']
    return {'X-Oryven-Session': token}


def _verified_account(client, mailer, email='demo@example.com'):
    local = _session_headers(client)
    r = client.post('/api/auth/register', headers=local, json={
        'name': 'Demo User', 'email': email, 'password': 'StrongPass123'
    })
    assert r.status_code == 200, r.text
    code = next(code for target, code, purpose in reversed(mailer.sent)
                if target == email and purpose == 'verify_email')
    r = client.post('/api/auth/verify-email', headers=local, json={'email': email, 'code': code})
    assert r.status_code == 200, r.text
    return {**local, 'Authorization': f"Bearer {r.json()['access_token']}"}


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path / 'data'))
    mailer = DummyMailer()
    store = AccountStore(tmp_path / 'data' / 'accounts.sqlite3')
    vault = DeviceSessionVault(tmp_path / 'data' / 'device_session.bin')
    client = TestClient(create_app(account_store=store, mailer=mailer, vault=vault))
    return client, mailer


def test_demo_readiness_guides_user_until_project_and_onboarding_are_ready(tmp_path, monkeypatch):
    client, mailer = _client(tmp_path, monkeypatch)
    headers = _verified_account(client, mailer)

    first = client.get('/api/demo/readiness', headers=headers)
    assert first.status_code == 200
    body = first.json()
    assert body['ready'] is False
    assert body['next_action']['key'] == 'assistant_named'
    assert body['permissions_granted'] is False

    project = client.post('/api/projects', headers=headers, json={
        'name': 'Demo Project', 'workspace': str(tmp_path / 'workspace'), 'description': 'Fluxo comercial'
    })
    assert project.status_code == 200
    pid = project.json()['id']
    assert client.patch('/api/context/active-project', headers=headers, json={'project_id': pid}).status_code == 200
    assert client.patch('/api/onboarding', headers=headers, json={
        'assistant_named': True, 'voice_configured': True, 'permissions_reviewed': True
    }).status_code == 200

    ready = client.get('/api/demo/readiness', headers=headers).json()
    assert ready['ready'] is True
    assert ready['active_project']['name'] == 'Demo Project'
    assert ready['next_action']['key'] == 'create_mission'
    assert ready['permissions_granted'] is False


def test_health_reports_demo_readiness_release(tmp_path, monkeypatch):
    client, _mailer = _client(tmp_path, monkeypatch)
    health = client.get('/api/health')
    assert health.status_code == 200
    assert health.json()['version'] == VERSION
