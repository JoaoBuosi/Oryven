import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from oryven.accounts import AccountStore, AccountError
from oryven.api import create_app
from oryven.device_vault import DeviceSessionVault


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


def test_password_and_code_are_not_stored_plaintext(tmp_path):
    store = AccountStore(tmp_path / 'accounts.sqlite3')
    user = store.register('User One', 'one@example.com', 'StrongPass123')
    code = store.create_code(user.id, 'verify_email')
    with sqlite3.connect(store.path) as db:
        pwd = db.execute('select password_hash from users').fetchone()[0]
        stored_code = db.execute('select code_hash from one_time_codes').fetchone()[0]
    assert 'StrongPass123' not in pwd
    assert code not in stored_code
    verified = store.consume_code('one@example.com', code, 'verify_email')
    assert verified.email_verified is True
    assert store.authenticate('one@example.com', 'StrongPass123').id == user.id


def test_full_account_flow_persistent_restore_and_user_isolation(tmp_path, monkeypatch):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path / 'data'))
    mailer = DummyMailer()
    store = AccountStore(tmp_path / 'data' / 'accounts.sqlite3')
    vault = DeviceSessionVault(tmp_path / 'data' / 'device_session.bin')
    app = create_app(account_store=store, mailer=mailer, vault=vault)
    client = TestClient(app)

    local, first = register_verified(client, mailer, 'Alice', 'alice@example.com')
    access1 = first['access_token']
    h1 = {**local, 'Authorization': f'Bearer {access1}'}
    assert client.patch('/api/voice/profile', headers=h1, json={'assistant_name': 'Atlas'}).status_code == 200
    assert client.get('/api/voice/profile', headers=h1).json()['assistant_name'] == 'Atlas'

    # Simulate process restart: same account DB + device vault, new API process/session.
    app2 = create_app(account_store=AccountStore(store.path), mailer=mailer, vault=DeviceSessionVault(vault.path))
    client2 = TestClient(app2)
    local2, _ = local_headers(client2)
    restored = client2.post('/api/auth/restore', headers=local2)
    assert restored.status_code == 200, restored.text
    assert restored.json()['user']['email'] == 'alice@example.com'
    h1b = {**local2, 'Authorization': f"Bearer {restored.json()['access_token']}"}
    assert client2.get('/api/voice/profile', headers=h1b).json()['assistant_name'] == 'Atlas'

    # Logout Alice, create Bob, and confirm Bob cannot see Alice's per-user voice profile.
    assert client2.post('/api/auth/logout', headers=h1b).status_code == 200
    local2, _ = local_headers(client2)
    _, second = register_verified(client2, mailer, 'Bob', 'bob@example.com')
    h2 = {**local2, 'Authorization': f"Bearer {second['access_token']}"}
    assert client2.get('/api/voice/profile', headers=h2).json()['assistant_name'] == 'Oryven'


def test_password_recovery_revokes_persistent_session(tmp_path, monkeypatch):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path / 'data'))
    mailer = DummyMailer()
    store = AccountStore(tmp_path / 'data' / 'accounts.sqlite3')
    vault = DeviceSessionVault(tmp_path / 'data' / 'device_session.bin')
    client = TestClient(create_app(account_store=store, mailer=mailer, vault=vault))
    local, login = register_verified(client, mailer, 'Alice', 'alice@example.com')
    old_access = login['access_token']

    generic = client.post('/api/auth/forgot-password', headers=local, json={'email': 'alice@example.com'})
    assert generic.status_code == 200
    code = next(code for target, code, purpose in reversed(mailer.sent) if target == 'alice@example.com' and purpose == 'reset_password')
    reset = client.post('/api/auth/reset-password', headers=local, json={'email': 'alice@example.com', 'code': code, 'new_password': 'NewStrongPass456'})
    assert reset.status_code == 200

    old = client.get('/api/auth/me', headers={**local, 'Authorization': f'Bearer {old_access}'})
    assert old.status_code == 401
    restored = client.post('/api/auth/restore', headers=local)
    assert restored.status_code == 401
    relogin = client.post('/api/auth/login', headers=local, json={'email': 'alice@example.com', 'password': 'NewStrongPass456', 'remember_device': True})
    assert relogin.status_code == 200


def test_forgot_password_does_not_enumerate_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path / 'data'))
    client = TestClient(create_app(account_store=AccountStore(tmp_path/'data'/'accounts.sqlite3'), mailer=DummyMailer(), vault=DeviceSessionVault(tmp_path/'data'/'vault.bin')))
    h, _ = local_headers(client)
    response = client.post('/api/auth/forgot-password', headers=h, json={'email': 'missing@example.com'})
    assert response.status_code == 200
    assert 'Se houver uma conta' in response.json()['message']
