"""Cross-platform contract tests: real UIA/Chromium require a Windows workstation."""
from pathlib import Path
from types import SimpleNamespace
import httpx
import pytest
from fastapi.testclient import TestClient

from oryven.api import create_app
from oryven.buno_bridge import BunoConnectionError, BunoHealthBridge
from oryven.browser_control import BrowserControlError, PlaywrightInspector, approved_public_url
from oryven.computer_control import ComputerControlError, WindowInspector
from oryven.config import Settings
from oryven.core import OryvenCore
from oryven.governance import ApprovalError


class Voice:
    enabled = True
    provider = "fake"
    def say(self, text): pass
    def stop(self): pass

class Listener:
    running = False
    def stop(self): pass


class Element:
    def __init__(self, handle=42, text="Janela", typ="Window", name="Nome", sensitive=False, children=None):
        self.handle = handle
        self._text = text
        self.element_info = SimpleNamespace(control_type=typ, name=name, automation_id="input1", is_password=sensitive)
        self._children = children or []
    def is_visible(self): return True
    def window_text(self): return self._text
    def children(self): return self._children


class FakeDesktop:
    def __init__(self, windows): self._windows = windows
    def windows(self): return self._windows


def test_windows_inspection_metadata_only_and_redacted():
    secret_field = Element(typ="Edit", name="senha-secreta", children=[Element(name="Never inspect")])
    passwd = Element(typ="Text", name="Segredo inesperado", sensitive=True)
    public = Element(typ="Button", name="OK")
    tree = Element(children=[secret_field, passwd, public])
    inspector = WindowInspector(platform="win32", desktop_factory=lambda backend: FakeDesktop([tree]))
    listed = inspector.list_windows()
    assert listed['windows'][0]['handle'] == 42
    result = inspector.inspect_window(42)
    assert len(result['elements']) == 4  # Never traverse sensitive field descendants
    serialized = str(result)
    assert 'senha-secreta' not in serialized
    assert 'Segredo inesperado' not in serialized
    assert 'Never inspect' not in serialized
    assert any(e['name'] == 'OK' for e in result['elements'])


def test_windows_non_windows_and_expired_handle():
    with pytest.raises(ComputerControlError):
        WindowInspector(platform="linux").list_windows()
    inspector = WindowInspector(platform="win32", desktop_factory=lambda backend: FakeDesktop([]))
    with pytest.raises(ComputerControlError): inspector.inspect_window(42)


@pytest.mark.parametrize('bad', [
    'http://example.com', 'http://127.0.0.1:8000', 'https://localhost',
    'https://evil.example.com', 'https://example.com.evil.test/',
    'https://example.com:3000/', 'https://evil@playwright.dev/',
    'https://playwright.dev@127.0.0.1/', 'file:///etc/passwd',
    'https://example.com/ has spaces', 'https://example.com\\@evil.com',
])
def test_browser_rejects_unapproved_network_targets(bad):
    with pytest.raises(BrowserControlError): approved_public_url(bad)


def test_browser_normalizes_exact_allowlisted_target():
    assert approved_public_url('https://example.com') == 'https://example.com/'
    assert approved_public_url('https://docs.python.org/3/tutorial/') == 'https://docs.python.org/3/tutorial/'


def test_browser_playwright_fake_isolated_and_verifies():
    class Page:
        url = 'https://example.com/'
        def goto(self, url, **kwargs):
            assert url == self.url and kwargs['timeout'] == 12000
            return SimpleNamespace(status=200, ok=True)
        def title(self): return 'Example Domain'
        def locator(self, target): return SimpleNamespace(all_text_contents=lambda: ['Example Domain'])
    class Context:
        def __init__(self): self._page = Page(); self.closed=False; self.route_handler=None
        def route(self, pattern, callback): self.route_handler=callback
        def new_page(self): return self._page
        def close(self): self.closed=True
    class Browser:
        def __init__(self): self.context=Context(); self.closed=False
        def new_context(self, **kwargs):
            assert kwargs['accept_downloads'] is False and kwargs['service_workers']=='block'
            return self.context
        def close(self): self.closed=True
    class Playwright:
        def __init__(self): self.browser=Browser(); self.chromium=SimpleNamespace(launch=self.launch)
        def launch(self, **kwargs): assert kwargs['headless'] is True; return self.browser
    class Provider:
        def __enter__(self): self.p=Playwright(); return self.p
        def __exit__(self, *a): assert self.p.browser.closed and self.p.browser.context.closed
    result = PlaywrightInspector(playwright_factory=Provider).inspect('https://example.com/')
    assert result['verified'] and result['title']=='Example Domain'


def test_buno_health_only_contract_and_no_secret_headers():
    def responder(request):
        assert str(request.url)=='http://127.0.0.1:8000/api/v1/health'
        assert 'authorization' not in request.headers and 'xi-api-key' not in request.headers
        return httpx.Response(200, json={'api':'ok','provider':'fake'})
    bridge = BunoHealthBridge(transport=httpx.MockTransport(responder))
    assert bridge.check() == {'reachable':True,'url':'http://127.0.0.1:8000',
                              'bridge_mode':'health-only','model_execution_enabled':False}
    for url in ['https://buno.com:8000','http://192.168.0.2:8000','http://127.0.0.1:8000/secret',
                'http://localhost:80', 'http://user:pass@localhost:8000']:
        with pytest.raises(BunoConnectionError): BunoHealthBridge(url)


def make_core(tmp_path):
    calls=[]
    class FakeWindows:
        def list_windows(self): calls.append('list'); return {'windows':[{'handle':42, 'title':'Notepad', 'control_type':'Window'}]}
        def inspect_window(self, handle): calls.append(f'tree:{handle}'); return {'handle':handle, 'elements':[]}
    class FakeBrowser:
        def inspect(self,url): calls.append(f'browser:{url}'); return {'url':url,'title':'Example Domain','verified':True}
    core=OryvenCore(Settings(data_dir=tmp_path, model_dir=tmp_path/'missing'),
                    speaker=Voice(), listener=Listener(),
                    window_inspector=FakeWindows(), browser_inspector=FakeBrowser())
    return core,calls


def test_ui_approval_workflow_exact_targets_api(tmp_path):
    core,calls=make_core(tmp_path)
    with TestClient(create_app(core)) as client:
        assert client.post('/api/control/windows/propose').status_code==401
        token=client.get('/api/session').json()['session_token']
        headers={'X-Oryven-Session':token}
        proposed=client.post('/api/control/windows/propose',headers=headers).json()['pending']
        assert calls==[]
        assert proposed['kind']=='computer.windows.list'
        decision=client.post(f"/api/actions/{proposed['id']}/decision", headers=headers, json={'decision':'approve'})
        assert decision.json()['outcome']=='inspected'
        assert decision.json()['data']['windows'][0]['handle']==42
        assert calls==['list']
        assert client.post(f"/api/actions/{proposed['id']}/decision", headers=headers, json={'decision':'approve'}).status_code==409
        tree=client.post('/api/control/window/propose',headers=headers,json={'handle':42}).json()['pending']
        assert tree['target']=='windows-ui-automation:window:42:metadata'
        client.post(f"/api/actions/{tree['id']}/decision",headers=headers,json={'decision':'deny'})
        assert calls==['list']
        assert client.post('/api/control/browser/propose',headers=headers,json={'url':'http://127.0.0.1:8765/api/session'}).status_code==422
        browser=client.post('/api/control/browser/propose',headers=headers,json={'url':'https://example.com'}).json()['pending']
        assert calls==['list']
        assert client.post(f"/api/actions/{browser['id']}/decision",headers=headers,json={'decision':'approve'}).json()['data']['verified']
        assert calls==['list','browser:https://example.com/']
        audit=client.get('/api/audit',headers=headers).json()
        assert 'Example Domain' not in str(audit)


def test_stop_revokes_window_inspection(tmp_path):
    core,calls=make_core(tmp_path)
    pending=core.propose_window_list()
    core.emergency_stop()
    with pytest.raises(ApprovalError): core.decide(pending['id'],'approve')
    assert calls==[]


def test_buno_chat_requires_jwt_and_stream_contract():
    token = 'very-secret-test-token'
    def responder(request):
        assert request.method == 'POST'
        assert str(request.url) == 'http://127.0.0.1:8000/api/v1/chat/stream'
        assert request.headers.get('Authorization') == f'Bearer {token}'
        assert request.headers.get('accept') == 'text/event-stream'
        assert request.content == b'{"message":"Oi Buno"}'
        return httpx.Response(200, text=(
            'event: start\ndata: {"conversation_id":"not-needed"}\n\n'
            'event: chunk\ndata: {"text":"Ol\u00e1 "}\n\n'
            'event: chunk\ndata: {"text":"usu\u00e1rio"}\n\n'
            'event: done\ndata: {}\n\n'), headers={'Content-Type':'text/event-stream'})
    bridge=BunoHealthBridge(bearer_token=token, transport=httpx.MockTransport(responder))
    result=bridge.chat('Oi Buno')
    assert result['answer']=='Olá usuário'
    assert result['executed_tools'] is False
    with pytest.raises(BunoConnectionError): BunoHealthBridge().chat('Oi')


def test_buno_requires_approval_and_does_not_leak_text_to_audit(tmp_path):
    core,calls=make_core(tmp_path)
    class FakeBuno:
        def chat(self, text):
            calls.append(text)
            return {'answer':'Texto livre, sem execução', 'executed_tools':False}
        def check(self): return {'reachable':True}
    core.buno_bridge=FakeBuno()
    with TestClient(create_app(core)) as client:
        headers={'X-Oryven-Session':client.get('/api/session').json()['session_token']}
        action=client.post('/api/integrations/buno/chat/propose',json={'message':'dado particular'},headers=headers)
        assert action.status_code==200
        pending=action.json()['pending']
        assert 'dado particular' not in str(pending)
        assert calls==[]
        resp=client.post(f"/api/actions/{pending['id']}/decision",json={'decision':'approve'},headers=headers)
        assert resp.status_code==200 and resp.json()['outcome']=='answered'
        assert calls==['dado particular']
        assert 'dado particular' not in str(client.get('/api/audit',headers=headers).json())
        assert core.buno_health()['reachable'] is True
        assert client.post(f"/api/actions/{pending['id']}/decision",json={'decision':'approve'},headers=headers).status_code==409


def test_buno_error_event_does_not_return_partial_answer():
    response='event: chunk\ndata: {"text":"Fragmento"}\n\nevent: error\ndata: {"code":"llm_error"}\n\n'
    bridge=BunoHealthBridge(bearer_token='token',transport=httpx.MockTransport(
        lambda request: httpx.Response(200,text=response)))
    with pytest.raises(BunoConnectionError): bridge.chat('Olá')
