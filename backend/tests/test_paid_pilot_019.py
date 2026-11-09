import hashlib
from pathlib import Path
from fastapi.testclient import TestClient

from oryven.commercial import CommercialStore, CommercialError, DataPortability, COMMERCIAL_TERMS_VERSION, PRIVACY_VERSION
from oryven.api import create_app
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.accounts import AccountStore
from oryven.device_vault import DeviceSessionVault

class DummyMailer:
    def __init__(self): self.sent=[]
    def send_code(self,email,code,purpose): self.sent.append((email,code,purpose))


def settings(tmp_path: Path, license_hash: str=''):
    return Settings(data_dir=tmp_path/'data', model_dir=tmp_path/'model', license_key_sha256=license_hash,
                    work_roots=(tmp_path,), developer_roots=(tmp_path,))


def test_commercial_license_consent_telemetry_and_export(tmp_path):
    key='PILOT-ORYVEN-TEST-1234'
    store=CommercialStore(tmp_path/'commercial.sqlite3')
    assert store.entitlement().plan == 'free'
    ent=store.activate_license(key, hashlib.sha256(key.encode()).hexdigest())
    assert ent.plan == 'pilot' and ent.status == 'active'
    assert ent.as_dict()['grants_execution_permissions'] is False
    cons=store.accept('terms', COMMERCIAL_TERMS_VERSION)
    store.accept('privacy', PRIVACY_VERSION)
    assert cons['terms']['accepted'] is True
    assert store.record_event('mission.completed', {'flow':'development'}) is False
    store.set_telemetry(True)
    assert store.record_event('mission.completed', {'flow':'development','secret':'NO'}) is True
    out=DataPortability.export_user_data(tmp_path, tmp_path/'export.zip')
    assert Path(out['path']).exists() and out['contains_credentials'] is False


def test_invalid_license_is_rejected(tmp_path):
    store=CommercialStore(tmp_path/'commercial.sqlite3')
    try:
        store.activate_license('wrong', '0'*64)
        assert False
    except CommercialError:
        pass


def test_commercial_api_status_and_feedback_legacy_mode(tmp_path):
    core=OryvenCore(settings(tmp_path))
    app=create_app(core=core)
    c=TestClient(app)
    session=c.get('/api/session').json()['session_token']
    headers={'X-Oryven-Session':session}
    status=c.get('/api/commercial/status',headers=headers)
    assert status.status_code==200
    body=status.json()
    assert body['entitlement']['plan']=='free'
    assert body['permissions_granted'] is False
    fb=c.post('/api/commercial/feedback',headers=headers,json={'category':'experience','message':'Fluxo claro e rápido.'})
    assert fb.status_code==200 and fb.json()['stored_locally'] is True


def test_paid_pilot_gate_in_authenticated_mode(tmp_path, monkeypatch):
    key='PILOT-TEST-KEY'
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path/'authdata'))
    monkeypatch.setenv('ORYVEN_LICENSE_KEY_SHA256', hashlib.sha256(key.encode()).hexdigest())
    mailer=DummyMailer()
    store=AccountStore(tmp_path/'authdata'/'accounts.sqlite3')
    vault=DeviceSessionVault(tmp_path/'authdata'/'device_session.bin')
    app=create_app(account_store=store, mailer=mailer, vault=vault)
    c=TestClient(app)
    local=c.get('/api/session').json()['session_token']
    h={'X-Oryven-Session':local}
    r=c.post('/api/auth/register',headers=h,json={'name':'Pilot User','email':'pilot@example.com','password':'VeryStrong123'})
    assert r.status_code==200
    code=mailer.sent[-1][1]
    v=c.post('/api/auth/verify-email',headers=h,json={'email':'pilot@example.com','code':code})
    assert v.status_code==200
    access=v.json()['access_token']; ah={**h,'Authorization':f'Bearer {access}'}
    # commercial flow blocked before consent/license
    blocked=c.post('/api/mvp/flows/research/start',headers=ah,json={'objective':'organize','context':{}})
    assert blocked.status_code in (402,451)
    assert c.post('/api/commercial/consent',headers=ah,json={'kind':'terms','version':COMMERCIAL_TERMS_VERSION,'accepted':True}).status_code==200
    assert c.post('/api/commercial/consent',headers=ah,json={'kind':'privacy','version':PRIVACY_VERSION,'accepted':True}).status_code==200
    assert c.post('/api/commercial/license/activate',headers=ah,json={'license_key':key}).status_code==200
    status=c.get('/api/commercial/status',headers=ah).json()
    assert status['entitlement']['plan']=='pilot'
    assert status['consents']['terms']['accepted'] and status['consents']['privacy']['accepted']

def test_account_delete_requires_password_and_removes_user_data(tmp_path, monkeypatch):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path/'delete-data'))
    mailer=DummyMailer(); store=AccountStore(tmp_path/'delete-data'/'accounts.sqlite3'); vault=DeviceSessionVault(tmp_path/'delete-data'/'device_session.bin')
    app=create_app(account_store=store, mailer=mailer, vault=vault); c=TestClient(app)
    local=c.get('/api/session').json()['session_token']; h={'X-Oryven-Session':local}
    assert c.post('/api/auth/register',headers=h,json={'name':'Delete Me','email':'delete@example.com','password':'VeryStrong123'}).status_code==200
    code=mailer.sent[-1][1]
    verified=c.post('/api/auth/verify-email',headers=h,json={'email':'delete@example.com','code':code}).json()
    user_id=verified['user']['id']; ah={**h,'Authorization':f"Bearer {verified['access_token']}"}
    assert (tmp_path/'delete-data'/'users'/user_id).exists()
    bad=c.request('DELETE','/api/account',headers=ah,json={'password':'WrongPass123'})
    assert bad.status_code==401
    ok=c.request('DELETE','/api/account',headers=ah,json={'password':'VeryStrong123'})
    assert ok.status_code==200 and ok.json()['local_user_data_deleted'] is True
    assert store.get_user_by_email('delete@example.com') is None
    assert not (tmp_path/'delete-data'/'users'/user_id).exists()
