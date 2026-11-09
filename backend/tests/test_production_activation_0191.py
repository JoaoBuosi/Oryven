from pathlib import Path
import httpx
import pytest
from oryven.remote_services import PilotServiceClient, RemoteServicesConfig, RemoteServiceError
from oryven.config import Settings


def test_remote_service_requires_configuration():
    c = PilotServiceClient(RemoteServicesConfig())
    with pytest.raises(RemoteServiceError):
        c.create_checkout(user_id='u1', email='user@example.com')


def test_production_env_settings(monkeypatch, tmp_path: Path):
    monkeypatch.setenv('ORYVEN_DATA_DIR', str(tmp_path/'data'))
    monkeypatch.setenv('ORYVEN_PILOT_SERVICE_URL', 'https://pilot.example')
    monkeypatch.setenv('ORYVEN_PILOT_SERVICE_TOKEN', 'token-value')
    s = Settings.from_env()
    assert s.pilot_service_url == 'https://pilot.example'
    assert s.pilot_service_token == 'token-value'
    assert 'token-value' not in repr(s)


def test_pilot_service_client_sends_checkout_without_stripe_secret(monkeypatch):
    seen = {}
    class Resp:
        status_code=200
        def json(self): return {'checkout_url':'https://checkout.stripe.com/test','session_id':'cs_test'}
    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(url=url, headers=headers, json=json)
        return Resp()
    monkeypatch.setattr(httpx, 'post', fake_post)
    c=PilotServiceClient(RemoteServicesConfig('https://pilot.example','desktop-token'))
    out=c.create_checkout(user_id='u1',email='user@example.com')
    assert out['session_id']=='cs_test'
    assert seen['url'].endswith('/v1/billing/checkout')
    assert seen['headers']['Authorization']=='Bearer desktop-token'
    assert 'stripe' not in str(seen).lower()


def test_pilot_service_entitlement(monkeypatch):
    seen = {}
    class Resp:
        status_code=200
        def json(self): return {'plan':'pilot','status':'active'}
    def fake_get(url, headers=None, params=None, timeout=None):
        seen.update(url=url, headers=headers, params=params)
        return Resp()
    monkeypatch.setattr(httpx, 'get', fake_get)
    c=PilotServiceClient(RemoteServicesConfig('https://pilot.example','desktop-token'))
    out=c.entitlement(user_id='u1')
    assert out == {'plan':'pilot','status':'active'}
    assert seen['params'] == {'user_id':'u1'}
    assert seen['headers']['Authorization'] == 'Bearer desktop-token'
