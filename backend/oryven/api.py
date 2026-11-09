"""Loopback-only HTTP API for the Oryven desktop UI.

This is a single-user development server, not a remote or multi-tenant API.
"""
from pathlib import Path
import shutil
import json
from dataclasses import replace
import secrets
import time

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from .apps import AppDiscoveryError
from .config import Settings
from .core import OryvenCore
from .governance import ApprovalError
from .browser_control import BrowserControlError
from .buno_bridge import BunoConnectionError
from .missions import MissionError
from .window_actions import WindowActionError
from .computer_control import ComputerControlError
from .developer_runtime import DeveloperRuntimeError
from .work_runtime import WorkRuntimeError
from .professional_runtime import ProfessionalRuntimeError
from .models import (CommandRequest, DecisionRequest, MissionVerification, BrowserInspectionRequest, WindowInspectionRequest,
                     WindowFocusRequest, WindowButtonRequest, BunoChatRequest, DeveloperActionRequest, ProfessionalTaskRequest,
                     WorkActionRequest, SkillProposalRequest, SkillMissionRequest, DynamicAppLaunchRequest, WindowControlRequest, WindowVisualSnapshotRequest, WindowUnderstandingRequest, MultiAppMissionRequest, MissionContextRequest, WindowTextInputRequest, AutonomousMissionRequest, FunctionalMVPRequest)
from .skills import SkillError
from .voice import VoiceUnavailable
from .accounts import AccountStore, AccountError
from .device_vault import DeviceSessionVault, DeviceVaultError
from .account_email import SendGridMailer, EmailDeliveryError
from .vision_provider import VisionProviderError
from .multi_app_planner import MultiAppPlannerError
from .autonomous_orchestrator import AutonomousMissionError
from .buno_mission_planner import BunoMissionPlannerError
from .projects import ProjectError
from .professional_memory import ProfessionalMemoryError
from .release_info import VERSION, RELEASE_CHANNEL, BUILD_TARGET
from .functional_mvp import FunctionalMVPError
from .commercial import CommercialError, COMMERCIAL_TERMS_VERSION, PRIVACY_VERSION, DataPortability
from .remote_services import PilotServiceClient, RemoteServicesConfig, RemoteServiceError

class VoiceProfileRequest(BaseModel):
    assistant_name: str | None = Field(default=None, min_length=2, max_length=32)
    language: str | None = Field(default=None, min_length=2, max_length=16)
    background_listening_enabled: bool | None = None
    speak_on_startup: bool | None = None
    wake_enabled: bool | None = None

class SpeakRequest(BaseModel):
    text: str | None = Field(default=None, max_length=350)

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)

class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")

class EmailOnlyRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=72)
    remember_device: bool = True

class ResetPasswordRequest(EmailCodeRequest):
    new_password: str = Field(min_length=8, max_length=72)


class OnboardingRequest(BaseModel):
    assistant_named: bool | None = None
    voice_configured: bool | None = None
    workspace_configured: bool | None = None
    permissions_reviewed: bool | None = None

class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    workspace: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=1000)
    favorite_agents: list[str] = Field(default_factory=list, max_length=12)

class ProjectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=1000)
    favorite_agents: list[str] | None = Field(default=None, max_length=12)

class MemoryWriteRequest(BaseModel):
    content: str = Field(min_length=2, max_length=1200)
    kind: str = Field(default="fact", pattern=r"^(fact|preference|decision|project_note)$")
    project_id: str | None = None

class MemorySettingsRequest(BaseModel):
    enabled: bool

class ActiveProjectRequest(BaseModel):
    project_id: str | None = None

class ContextPreviewRequest(BaseModel):
    objective: str = Field(min_length=2, max_length=2000)
    context: dict = Field(default_factory=dict)

class LicenseActivateRequest(BaseModel):
    license_key: str = Field(min_length=8, max_length=300)

class CheckoutRequest(BaseModel):
    plan: str = Field(default="pilot", pattern="^(pilot|pro)$")


class ConsentRequest(BaseModel):
    kind: str = Field(pattern=r"^(terms|privacy)$")
    version: str = Field(min_length=3, max_length=80)
    accepted: bool = True

class TelemetrySettingsRequest(BaseModel):
    enabled: bool

class FeedbackRequest(BaseModel):
    category: str = Field(pattern=r"^(bug|idea|experience|support)$")
    message: str = Field(min_length=3, max_length=2000)
    include_diagnostics: bool = False

class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=8, max_length=72)


ALLOWED_ORIGINS = {
    "http://127.0.0.1:5173", "http://localhost:5173",
    "http://127.0.0.1:8765", "http://localhost:8765",
    "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost",
}


def create_app(core: OryvenCore | None = None, account_store: AccountStore | None = None,
               mailer: SendGridMailer | None = None, vault: DeviceSessionVault | None = None) -> FastAPI:
    settings = core.settings if core is not None else Settings.from_env()
    app = FastAPI(title="Oryven Local API", version=VERSION, docs_url=None, redoc_url=None)
    app.state.base_settings = settings
    app.state.core = core
    app.state.active_user_id = None
    app.state.auth_required = core is None
    app.state.account_store = account_store or AccountStore(settings.data_dir / "accounts.sqlite3")
    app.state.mailer = mailer or SendGridMailer(
        settings.sendgrid_api_key,
        settings.sendgrid_from_email,
        settings.sendgrid_from_name,
        settings.email_hook_url,
        settings.email_hook_secret,
    )
    app.state.vault = vault or DeviceSessionVault(settings.data_dir / "device_session.bin")
    app.state.pilot_service = PilotServiceClient(RemoteServicesConfig(settings.pilot_service_url, settings.pilot_service_token))
    app.state.access_tokens = {}
    app.state.login_attempts = {}
    app.state.session_token = secrets.token_urlsafe(32)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
    app.add_middleware(CORSMiddleware, allow_origins=sorted(ALLOWED_ORIGINS),
                       allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"],
                       allow_headers=["X-Oryven-Session", "Content-Type", "Authorization"])

    @app.middleware("http")
    async def reject_foreign_origins(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "Origem não autorizada"})
        return await call_next(request)

    def local_authorized(x_oryven_session: str | None = Header(default=None)):
        if not x_oryven_session or not secrets.compare_digest(x_oryven_session, app.state.session_token):
            raise HTTPException(401, "Sessão local inválida")

    def switch_user(user_id: str):
        if not app.state.auth_required:
            return
        if app.state.active_user_id == user_id and app.state.core is not None:
            return
        old_core = app.state.core
        if old_core is not None:
            try:
                old_core.listener.stop()
            except Exception:
                pass
        user_dir = app.state.base_settings.data_dir / "users" / user_id
        app.state.core = OryvenCore(replace(app.state.base_settings, data_dir=user_dir))
        app.state.active_user_id = user_id

    def issue_access(user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        app.state.access_tokens[token] = (user_id, time.time() + 8 * 60 * 60)
        return token

    def purge_access_for_user(user_id: str):
        for token, value in list(app.state.access_tokens.items()):
            if value[0] == user_id:
                app.state.access_tokens.pop(token, None)

    def authorized(x_oryven_session: str | None = Header(default=None), authorization: str | None = Header(default=None)):
        local_authorized(x_oryven_session)
        if not app.state.auth_required:
            return "legacy-local-user"
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Conta Oryven não autenticada")
        token = authorization[7:].strip()
        value = app.state.access_tokens.get(token)
        if value is None or value[1] <= time.time():
            app.state.access_tokens.pop(token, None)
            raise HTTPException(401, "Sessão da conta expirada")
        user_id = value[0]
        switch_user(user_id)
        return user_id

    def require_paid_pilot():
        if not app.state.auth_required:
            return
        commercial = app.state.core.commercial
        ent = commercial.entitlement()
        consents = commercial.consents()
        if not consents["terms"]["accepted"] or not consents["privacy"]["accepted"]:
            raise HTTPException(451, "Aceite os Termos do Piloto e a Política de Privacidade antes de usar os fluxos comerciais.")
        if ent.status != "active" or ent.plan not in {"pilot", "pro"}:
            raise HTTPException(402, "Ative uma licença Pilot ou Pro para iniciar os fluxos comerciais.")

    def check_rate(key: str, limit: int, window: int = 60):
        now = time.time()
        recent = [v for v in app.state.login_attempts.get(key, []) if now - v < window]
        if len(recent) >= limit:
            raise HTTPException(429, "Muitas tentativas. Aguarde e tente novamente.")
        recent.append(now)
        app.state.login_attempts[key] = recent

    def auth_response(user, remember_device: bool = True):
        previous = app.state.vault.load()
        if previous:
            app.state.account_store.revoke_device_session(previous)
            try:
                app.state.vault.clear()
            except DeviceVaultError:
                pass
        if remember_device:
            _session_id, refresh = app.state.account_store.create_device_session(user.id)
            try:
                app.state.vault.save(refresh)
            except DeviceVaultError as exc:
                app.state.account_store.revoke_device_session(refresh)
                raise HTTPException(503, str(exc)) from exc
        access = issue_access(user.id)
        switch_user(user.id)
        return {"access_token": access, "token_type": "bearer", "user": user.as_dict()}

    @app.get("/api/health")
    def health():
        return {"status": "ok", "product": "oryven", "version": VERSION, "release_channel": RELEASE_CHANNEL, "build_target": BUILD_TARGET}

    @app.get("/api/session")
    def session():
        # Readable only by same-origin/explicitly allowed desktop UI due to CORS.
        return {"session_token": app.state.session_token}

    @app.post("/api/auth/register", dependencies=[Depends(local_authorized)])
    def register_account(body: RegisterRequest):
        check_rate("register:" + body.email.lower(), 5, 300)
        try:
            user = app.state.account_store.register(body.name, body.email, body.password)
            code = app.state.account_store.create_code(user.id, "verify_email")
            app.state.mailer.send_code(user.email, code, "verify_email")
        except AccountError as exc:
            raise HTTPException(422, str(exc)) from exc
        except EmailDeliveryError as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"verification_required": True, "email": user.email, "message": "Código enviado para verificação."}

    @app.post("/api/auth/verify-email", dependencies=[Depends(local_authorized)])
    def verify_email(body: EmailCodeRequest):
        try:
            user = app.state.account_store.consume_code(body.email, body.code, "verify_email")
            return auth_response(user, True)
        except AccountError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/auth/resend-verification", dependencies=[Depends(local_authorized)])
    def resend_verification(body: EmailOnlyRequest):
        # Generic response prevents account enumeration.
        try:
            user = app.state.account_store.get_user_by_email(body.email)
            if user is not None and not user.email_verified:
                code = app.state.account_store.create_code(user.id, "verify_email")
                app.state.mailer.send_code(user.email, code, "verify_email")
        except (AccountError, EmailDeliveryError):
            pass
        return {"sent": True, "message": "Se a conta puder receber um novo código, ele será enviado."}

    @app.post("/api/auth/login", dependencies=[Depends(local_authorized)])
    def login_account(body: LoginRequest):
        check_rate("login:" + body.email.lower(), 10, 60)
        try:
            user = app.state.account_store.authenticate(body.email, body.password)
            return auth_response(user, body.remember_device)
        except AccountError as exc:
            raise HTTPException(401, str(exc)) from exc

    @app.post("/api/auth/restore", dependencies=[Depends(local_authorized)])
    def restore_account():
        refresh = app.state.vault.load()
        if not refresh:
            raise HTTPException(401, "Nenhuma sessão persistente disponível")
        user = app.state.account_store.validate_device_session(refresh)
        if user is None:
            app.state.vault.clear()
            raise HTTPException(401, "Sessão persistente inválida ou expirada")
        access = issue_access(user.id)
        switch_user(user.id)
        return {"access_token": access, "token_type": "bearer", "user": user.as_dict()}

    @app.post("/api/auth/forgot-password", dependencies=[Depends(local_authorized)])
    def forgot_password(body: EmailOnlyRequest):
        check_rate("forgot:" + body.email.lower(), 5, 300)
        try:
            user = app.state.account_store.get_user_by_email(body.email)
            if user is not None:
                code = app.state.account_store.create_code(user.id, "reset_password")
                app.state.mailer.send_code(user.email, code, "reset_password")
        except (AccountError, EmailDeliveryError):
            pass
        return {"sent": True, "message": "Se houver uma conta para este e-mail, enviaremos um código de recuperação."}

    @app.post("/api/auth/reset-password", dependencies=[Depends(local_authorized)])
    def reset_password(body: ResetPasswordRequest):
        try:
            user = app.state.account_store.change_password_with_code(body.email, body.code, body.new_password)
        except AccountError as exc:
            raise HTTPException(422, str(exc)) from exc
        purge_access_for_user(user.id)
        try:
            app.state.vault.clear()
        except DeviceVaultError:
            pass
        if app.state.active_user_id == user.id:
            try:
                app.state.core.listener.stop()
            except Exception:
                pass
            app.state.core = None
            app.state.active_user_id = None
        return {"status": "password_reset", "message": "Senha alterada. Entre novamente."}

    @app.get("/api/auth/me")
    def account_me(user_id: str = Depends(authorized)):
        user = app.state.account_store.get_user(user_id)
        if user is None:
            raise HTTPException(404, "Conta não encontrada")
        return user.as_dict()

    @app.post("/api/auth/logout")
    def logout_account(user_id: str = Depends(authorized)):
        refresh = app.state.vault.load()
        if refresh:
            app.state.account_store.revoke_device_session(refresh)
        app.state.vault.clear()
        purge_access_for_user(user_id)
        if app.state.active_user_id == user_id and app.state.core is not None:
            try:
                app.state.core.listener.stop()
            except Exception:
                pass
            app.state.core = None
            app.state.active_user_id = None
        return {"status": "logged_out"}

    @app.get("/api/status", dependencies=[Depends(authorized)])
    def status():
        return app.state.core.status()

    @app.get("/api/demo/readiness", dependencies=[Depends(authorized)])
    def demo_readiness():
        return app.state.core.demo_readiness()

    @app.get("/api/mvp/flows", dependencies=[Depends(authorized)])
    def functional_mvp_flows():
        return app.state.core.list_functional_mvp_flows()

    @app.post("/api/mvp/flows/{flow_id}/plan", dependencies=[Depends(authorized)])
    def functional_mvp_plan(flow_id: str, body: FunctionalMVPRequest):
        try:
            return app.state.core.plan_functional_mvp_flow(flow_id, body.context)
        except (FunctionalMVPError, SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/mvp/flows/{flow_id}/start", dependencies=[Depends(authorized)])
    def functional_mvp_start(flow_id: str, body: FunctionalMVPRequest):
        require_paid_pilot()
        try:
            result = app.state.core.start_functional_mvp_flow(flow_id, body.objective, body.context)
            app.state.core.commercial.record_event("mvp_flow.started", {"flow": flow_id, "status": "started", "version": VERSION, "surface": "desktop"})
            return result
        except (FunctionalMVPError, MissionError, SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            app.state.core.commercial.record_event("mvp_flow.error", {"flow": flow_id, "status": "error", "error_class": type(exc).__name__, "version": VERSION, "surface": "desktop"})
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/events", dependencies=[Depends(authorized)])
    def events(after: int = Query(default=0, ge=0)):
        return app.state.core.events_after(after)

    @app.post("/api/commands", dependencies=[Depends(authorized)])
    def commands(body: CommandRequest):
        return {"pending": app.state.core.submit(body.text)}

    @app.get("/api/actions/pending", dependencies=[Depends(authorized)])
    def pending():
        return [p.model_dump() for p in app.state.core.approvals.list_pending()]

    @app.post("/api/actions/{action_id}/decision", dependencies=[Depends(authorized)])
    def decide(action_id: str, body: DecisionRequest):
        try:
            result = app.state.core.decide(action_id, body.decision)
            app.state.core.commercial.record_event("authorization.decision", {"status": body.decision, "version": VERSION, "surface": "desktop"})
            return result
        except (ApprovalError, MissionError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/control/windows/propose", dependencies=[Depends(authorized)])
    def propose_windows():
        return {"pending": app.state.core.propose_window_list()}

    @app.post("/api/control/window/propose", dependencies=[Depends(authorized)])
    def propose_window(body: WindowInspectionRequest):
        return {"pending": app.state.core.propose_window_tree(body.handle)}

    @app.post("/api/perception/window/propose", dependencies=[Depends(authorized)])
    def propose_window_visual(body: WindowVisualSnapshotRequest):
        try:
            return {"pending": app.state.core.propose_window_visual_snapshot(body.handle)}
        except (WindowActionError, ComputerControlError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/perception/window/understand/propose", dependencies=[Depends(authorized)])
    def propose_window_understanding(body: WindowUnderstandingRequest):
        try:
            return {"pending": app.state.core.propose_window_understanding(body.handle, body.prompt)}
        except (WindowActionError, ComputerControlError, VisionProviderError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/control/window/focus/propose", dependencies=[Depends(authorized)])
    def propose_window_focus(body: WindowFocusRequest):
        try:
            return {"pending": app.state.core.propose_window_focus(body.handle)}
        except (WindowActionError, ComputerControlError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/control/window/button/propose", dependencies=[Depends(authorized)])
    def propose_window_button(body: WindowButtonRequest):
        try:
            return {"pending": app.state.core.propose_window_button(body.handle, body.path)}
        except (WindowActionError, ComputerControlError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/control/window/invoke/propose", dependencies=[Depends(authorized)])
    def propose_window_invoke(body: WindowControlRequest):
        try:
            return {"pending": app.state.core.propose_window_invoke(body.handle, body.path)}
        except (WindowActionError, ComputerControlError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/control/window/text/propose", dependencies=[Depends(authorized)])
    def propose_window_text(body: WindowTextInputRequest):
        try:
            return {"pending": app.state.core.propose_window_set_text(body.handle, body.path, body.text, body.replace)}
        except (WindowActionError, ComputerControlError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/apps/launch/propose", dependencies=[Depends(authorized)])
    def propose_dynamic_app(body: DynamicAppLaunchRequest):
        try:
            return {"pending": app.state.core.propose_app_launch(body.app_name)}
        except AppDiscoveryError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/control/browser/propose", dependencies=[Depends(authorized)])
    def propose_browser(body: BrowserInspectionRequest):
        try:
            return {"pending": app.state.core.propose_browser_inspection(body.url)}
        except BrowserControlError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/integrations/buno/health", dependencies=[Depends(authorized)])
    def buno_health():
        try:
            return app.state.core.buno_health()
        except BunoConnectionError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/integrations/buno/chat/propose", dependencies=[Depends(authorized)])
    def propose_buno_chat(body: BunoChatRequest):
        try:
            return {"pending": app.state.core.propose_buno_chat(body.message)}
        except BunoConnectionError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/chat/history", dependencies=[Depends(authorized)])
    def chat_history():
        return {"messages": app.state.core.chat_memory.list_messages()}

    @app.delete("/api/chat/history", dependencies=[Depends(authorized)])
    def clear_chat_history():
        return app.state.core.chat_memory.clear()

    @app.post("/api/developer/propose", dependencies=[Depends(authorized)])
    def propose_developer(body: DeveloperActionRequest):
        try:
            return {"pending": app.state.core.propose_developer_action(body.action, body.workspace)}
        except DeveloperRuntimeError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/work/propose", dependencies=[Depends(authorized)])
    def propose_work(body: WorkActionRequest):
        try:
            return {"pending": app.state.core.propose_work_action(
                body.action, body.workspace, body.path, body.content, body.executable, body.args
            )}
        except (WorkRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/skills/{skill_id}/propose", dependencies=[Depends(authorized)])
    def propose_skill(skill_id: str, body: SkillProposalRequest):
        try:
            return {"pending": app.state.core.propose_skill(skill_id, body.arguments)}
        except (SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/ml/intent", dependencies=[Depends(authorized)])
    def classify_intent(body: CommandRequest):
        return {"route": app.state.core.classify_intent(body.text)}

    @app.get("/api/agents", dependencies=[Depends(authorized)])
    def professional_agents():
        return {"agents": app.state.core.list_professional_agents(), "execution": "governed"}

    @app.post("/api/agents/plan", dependencies=[Depends(authorized)])
    def professional_plan(body: ProfessionalTaskRequest):
        try:
            return app.state.core.professional_plan(body.objective, body.agent_id)
        except (ValueError, KeyError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/skills", dependencies=[Depends(authorized)])
    def create_skill_mission(body: SkillMissionRequest):
        try:
            return app.state.core.start_skill_mission(body.objective, body.steps)
        except (MissionError, SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/missions/context", dependencies=[Depends(authorized)])
    def mission_context():
        return app.state.core.get_mission_context()

    @app.post("/api/missions/context", dependencies=[Depends(authorized)])
    def set_mission_context(body: MissionContextRequest):
        try:
            return app.state.core.set_mission_context(body.workspace, body.spreadsheet_path, body.report_path)
        except (MissionError, WorkRuntimeError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/multi-app/plan", dependencies=[Depends(authorized)])
    def plan_multi_app(body: MultiAppMissionRequest):
        try:
            return app.state.core.plan_multi_app_mission(body.objective, body.workspace, body.spreadsheet_path, body.report_path)
        except MultiAppPlannerError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/multi-app/start", dependencies=[Depends(authorized)])
    def start_multi_app(body: MultiAppMissionRequest):
        if not body.workspace or not body.spreadsheet_path:
            raise HTTPException(422, "workspace e spreadsheet_path são obrigatórios para iniciar a missão.")
        try:
            return app.state.core.start_multi_app_mission(body.objective, body.workspace, body.spreadsheet_path, body.report_path)
        except (MultiAppPlannerError, MissionError, SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/ai/plan", dependencies=[Depends(authorized)])
    def plan_buno_ai(body: AutonomousMissionRequest):
        try:
            return app.state.core.plan_buno_ai_mission(body.objective, body.context, body.max_steps)
        except (BunoMissionPlannerError, BunoConnectionError, AutonomousMissionError, MissionError,
                SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/ai/start", dependencies=[Depends(authorized)])
    def start_buno_ai(body: AutonomousMissionRequest):
        try:
            return app.state.core.start_buno_ai_mission(
                body.objective, body.context, body.max_steps, body.recovery_budget
            )
        except (BunoMissionPlannerError, BunoConnectionError, AutonomousMissionError, MissionError,
                SkillError, WorkRuntimeError, ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/autonomous/plan", dependencies=[Depends(authorized)])
    def plan_autonomous(body: AutonomousMissionRequest):
        try:
            return app.state.core.plan_autonomous_mission(
                body.objective, body.context, body.steps, body.max_steps, body.recovery_budget
            )
        except (AutonomousMissionError, MissionError, SkillError, WorkRuntimeError,
                ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/missions/autonomous/start", dependencies=[Depends(authorized)])
    def start_autonomous(body: AutonomousMissionRequest):
        try:
            return app.state.core.start_autonomous_mission(
                body.objective, body.context, body.steps, body.max_steps, body.recovery_budget
            )
        except (AutonomousMissionError, MissionError, SkillError, WorkRuntimeError,
                ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/missions/{mission_id}/autonomous", dependencies=[Depends(authorized)])
    def autonomous_status(mission_id: str):
        try:
            return app.state.core.autonomous_mission_status(mission_id)
        except (AutonomousMissionError, MissionError) as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/missions/{mission_id}/autonomous/advance", dependencies=[Depends(authorized)])
    def autonomous_advance(mission_id: str):
        try:
            return app.state.core.autonomous_advance(mission_id)
        except (AutonomousMissionError, MissionError, SkillError, WorkRuntimeError,
                ProfessionalRuntimeError, DeveloperRuntimeError, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/missions", dependencies=[Depends(authorized)])
    def missions():
        return app.state.core.missions.list()

    @app.post("/api/missions", dependencies=[Depends(authorized)])
    def create_mission(body: CommandRequest):
        try:
            return app.state.core.start_mission(body.text)
        except MissionError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/missions/{mission_id}", dependencies=[Depends(authorized)])
    def mission(mission_id: str):
        try:
            return app.state.core.missions.get(mission_id)
        except MissionError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/missions/{mission_id}/intelligence", dependencies=[Depends(authorized)])
    def mission_intelligence(mission_id: str):
        try:
            return app.state.core.mission_intelligence_view(mission_id)
        except MissionError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/missions/{mission_id}/resume", dependencies=[Depends(authorized)])
    def resume(mission_id: str):
        try:
            return app.state.core.resume_mission(mission_id)
        except MissionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/missions/{mission_id}/verify", dependencies=[Depends(authorized)])
    def verify(mission_id: str, body: MissionVerification):
        try:
            return app.state.core.verify_mission_step(mission_id, body.confirmed)
        except MissionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/missions/{mission_id}/cancel", dependencies=[Depends(authorized)])
    def cancel(mission_id: str):
        try:
            return app.state.core.cancel_mission(mission_id)
        except MissionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.delete("/api/missions/{mission_id}", dependencies=[Depends(authorized)])
    def delete_mission(mission_id: str):
        try:
            return app.state.core.delete_mission(mission_id)
        except MissionError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/onboarding", dependencies=[Depends(authorized)])
    def onboarding_status():
        return app.state.core.onboarding_status()

    @app.patch("/api/onboarding", dependencies=[Depends(authorized)])
    def update_onboarding(body: OnboardingRequest):
        return app.state.core.update_onboarding(**body.model_dump(exclude_none=True))

    @app.get("/api/context", dependencies=[Depends(authorized)])
    def context_status():
        return app.state.core.context_status()

    @app.patch("/api/context/active-project", dependencies=[Depends(authorized)])
    def context_active_project(body: ActiveProjectRequest):
        try:
            return app.state.core.set_active_project(body.project_id)
        except ProjectError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/context/preview", dependencies=[Depends(authorized)])
    def context_preview(body: ContextPreviewRequest):
        return app.state.core.context_preview(body.objective, body.context)

    @app.get("/api/projects", dependencies=[Depends(authorized)])
    def projects():
        return {"projects": app.state.core.list_projects()}

    @app.post("/api/projects", dependencies=[Depends(authorized)])
    def create_project(body: ProjectCreateRequest):
        try:
            return app.state.core.create_project(body.name, body.workspace, body.description, body.favorite_agents)
        except ProjectError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.patch("/api/projects/{project_id}", dependencies=[Depends(authorized)])
    def update_project(project_id: str, body: ProjectUpdateRequest):
        try:
            return app.state.core.update_project(project_id, **body.model_dump(exclude_none=True))
        except ProjectError as exc:
            raise HTTPException(404 if "não encontrado" in str(exc) else 400, str(exc)) from exc

    @app.delete("/api/projects/{project_id}", dependencies=[Depends(authorized)])
    def delete_project(project_id: str):
        try:
            return app.state.core.delete_project(project_id)
        except ProjectError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/memory/professional", dependencies=[Depends(authorized)])
    def professional_memory(project_id: str | None = None, limit: int = Query(default=200, ge=1, le=500)):
        try:
            return {"enabled": app.state.core.professional_memory.enabled(), "memories": app.state.core.list_professional_memory(project_id, limit)}
        except ProjectError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.post("/api/memory/professional", dependencies=[Depends(authorized)])
    def remember_professional(body: MemoryWriteRequest):
        try:
            return app.state.core.remember_professional(body.content, body.kind, body.project_id)
        except (ProfessionalMemoryError, ProjectError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.patch("/api/memory/professional/settings", dependencies=[Depends(authorized)])
    def professional_memory_settings(body: MemorySettingsRequest):
        return app.state.core.set_professional_memory_enabled(body.enabled)

    @app.delete("/api/memory/professional/{item_id}", dependencies=[Depends(authorized)])
    def forget_professional(item_id: str):
        try:
            return app.state.core.forget_professional(item_id)
        except ProfessionalMemoryError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.delete("/api/memory/professional", dependencies=[Depends(authorized)])
    def clear_professional_memory(project_id: str | None = None):
        try:
            return app.state.core.clear_professional_memory(project_id)
        except ProjectError as exc:
            raise HTTPException(404, str(exc)) from exc

    @app.get("/api/voice/profile", dependencies=[Depends(authorized)])
    def voice_profile():
        return app.state.core.get_voice_profile()

    @app.patch("/api/voice/profile", dependencies=[Depends(authorized)])
    def update_voice_profile(body: VoiceProfileRequest):
        try:
            return app.state.core.update_voice_profile(**body.model_dump(exclude_none=True))
        except (VoiceUnavailable, ValueError) as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/voice/speak", dependencies=[Depends(authorized)])
    def speak(body: SpeakRequest):
        return app.state.core.speak_test(body.text)

    @app.post("/api/voice/speech/stop", dependencies=[Depends(authorized)])
    def stop_speech():
        return app.state.core.stop_speaking()

    @app.post("/api/voice/start", dependencies=[Depends(authorized)])
    def start_voice():
        try:
            app.state.core.listener.start()
        except VoiceUnavailable as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"status": "starting"}

    @app.post("/api/voice/stop", dependencies=[Depends(authorized)])
    def stop_voice():
        app.state.core.listener.stop()
        return {"status": "stopped"}

    @app.post("/api/stop", dependencies=[Depends(authorized)])
    def stop():
        return app.state.core.emergency_stop()

    @app.get("/api/skills", dependencies=[Depends(authorized)])
    def skills():
        return {"skills": app.state.core.list_skills(), "dynamic_execution": False,
                "execution": "named adapters + one-shot approval"}

    @app.get("/api/apps", dependencies=[Depends(authorized)])
    def apps():
        return {"apps": app.state.core.app_catalog.list(), "complete": False,
                "note": "Inventário parcial; launchable=true indica alvo local descoberto que pode ser proposto para abertura."}

    @app.get("/api/commercial/status", dependencies=[Depends(authorized)])
    def commercial_status():
        c = app.state.core.commercial
        return {"entitlement": c.entitlement().as_dict(), "consents": c.consents(),
                "telemetry_enabled": c.telemetry_enabled(), "terms_version": COMMERCIAL_TERMS_VERSION,
                "privacy_version": PRIVACY_VERSION, "support_email": app.state.base_settings.support_email,
                "update_manifest_configured": bool(app.state.base_settings.update_manifest_url),
                "billing_provider": "stripe" if app.state.base_settings.pilot_service_url else "not-configured",
                "pilot_service_configured": bool(app.state.base_settings.pilot_service_url),
                "permissions_granted": False}

    @app.post("/api/commercial/billing/checkout", dependencies=[Depends(authorized)])
    def commercial_checkout(body: CheckoutRequest, user_id: str = Depends(authorized)):
        user = app.state.account_store.get_user(user_id) if app.state.auth_required else None
        email = user.email if user is not None else "local@oryven.invalid"
        try:
            return app.state.pilot_service.create_checkout(user_id=user_id, email=email, plan=body.plan)
        except RemoteServiceError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/commercial/billing/sync", dependencies=[Depends(authorized)])
    def commercial_billing_sync(user_id: str = Depends(authorized)):
        try:
            remote = app.state.pilot_service.entitlement(user_id=user_id)
        except RemoteServiceError as exc:
            raise HTTPException(503, str(exc)) from exc
        plan = str(remote.get("plan") or "free").lower()
        status = str(remote.get("status") or "inactive").lower()
        if plan not in {"free", "pilot", "pro"}:
            raise HTTPException(502, "Entitlement remoto inválido.")
        local_status = "active" if status in {"active", "trialing", "paid", "complete"} and plan in {"pilot", "pro"} else "inactive"
        ent = app.state.core.commercial.set_entitlement(plan if local_status == "active" else "free", local_status if local_status == "active" else "active", "stripe-webhook")
        return {"entitlement": ent.as_dict(), "remote": {"plan": plan, "status": status}, "permissions_granted": False}

    @app.post("/api/commercial/license/activate", dependencies=[Depends(authorized)])
    def commercial_activate(body: LicenseActivateRequest):
        try:
            ent = app.state.core.commercial.activate_license(body.license_key, app.state.base_settings.license_key_sha256)
            return {"entitlement": ent.as_dict()}
        except CommercialError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/commercial/consent", dependencies=[Depends(authorized)])
    def commercial_consent(body: ConsentRequest):
        try:
            return app.state.core.commercial.accept(body.kind, body.version, body.accepted)
        except CommercialError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.patch("/api/commercial/telemetry", dependencies=[Depends(authorized)])
    def commercial_telemetry(body: TelemetrySettingsRequest):
        return {"enabled": app.state.core.commercial.set_telemetry(body.enabled), "opt_in": True,
                "remote_configured": bool(app.state.base_settings.pilot_service_url)}

    @app.post("/api/commercial/telemetry/sync", dependencies=[Depends(authorized)])
    def commercial_telemetry_sync():
        if not app.state.core.commercial.telemetry_enabled():
            return {"synced": 0, "enabled": False}
        if not app.state.base_settings.pilot_service_url:
            raise HTTPException(503, "Backend de telemetria remoto não configurado.")
        batch = app.state.core.commercial.telemetry_batch(100)
        synced=[]
        for item in batch:
            try:
                app.state.pilot_service.telemetry(item["event"], item["properties"])
                synced.append(item["id"])
            except RemoteServiceError:
                break
        app.state.core.commercial.delete_telemetry_ids(synced)
        return {"synced": len(synced), "remaining": len(app.state.core.commercial.telemetry_batch(1)) > 0}

    @app.post("/api/commercial/feedback", dependencies=[Depends(authorized)])
    def commercial_feedback(body: FeedbackRequest, user_id: str = Depends(authorized)):
        try:
            local = app.state.core.commercial.feedback(body.category, body.message, body.include_diagnostics)
            remote = False
            if app.state.base_settings.pilot_service_url:
                diagnostics = support_diagnostics() if body.include_diagnostics else {}
                try:
                    app.state.pilot_service.feedback(user_id=user_id, category=body.category, message=body.message, diagnostics=diagnostics)
                    remote = True
                except RemoteServiceError:
                    remote = False
            return {**local, "remote_delivered": remote}
        except CommercialError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/commercial/export", dependencies=[Depends(authorized)])
    def commercial_export():
        output = app.state.core.settings.data_dir / "exports" / f"oryven-export-{int(time.time())}.zip"
        return DataPortability.export_user_data(app.state.core.settings.data_dir, output)

    @app.get("/api/commercial/export/{filename}", dependencies=[Depends(authorized)])
    def commercial_export_download(filename: str):
        if not filename.startswith("oryven-export-") or not filename.endswith(".zip") or "/" in filename or "\\" in filename:
            raise HTTPException(404, "Exportação não encontrada")
        target = app.state.core.settings.data_dir / "exports" / filename
        if not target.exists(): raise HTTPException(404, "Exportação não encontrada")
        return FileResponse(target, media_type="application/zip", filename=filename)

    @app.get("/api/support/diagnostics", dependencies=[Depends(authorized)])
    def support_diagnostics():
        core = app.state.core
        buno = core.buno_health()
        return {"version": VERSION, "release_channel": RELEASE_CHANNEL, "core": "online",
                "voice": {"provider": core.status()["voice_provider"], "model_installed": core.status()["model_installed"]},
                "buno": {"reachable": bool(buno.get("reachable")), "bridge_mode": buno.get("bridge_mode")},
                "pending_approvals": len(core.approvals.list_pending()), "active_project": (core.context_engine.status().get("active_project") or {}).get("name"),
                "secrets_included": False}

    @app.get("/api/update/status", dependencies=[Depends(authorized)])
    def update_status():
        return {"current_version": VERSION, "channel": RELEASE_CHANNEL,
                "manifest_configured": bool(app.state.base_settings.update_manifest_url),
                "automatic_install": bool(app.state.base_settings.update_manifest_url),
                "signed_updates_required": True,
                "note": "Tauri updater only accepts signed update artifacts."}

    @app.delete("/api/account", dependencies=[Depends(authorized)])
    def delete_account(body: AccountDeleteRequest, user_id: str = Depends(authorized)):
        if not app.state.auth_required:
            raise HTTPException(409, "Exclusão de conta não se aplica ao modo local legado")
        user = app.state.account_store.get_user(user_id)
        if user is None:
            raise HTTPException(404, "Conta não encontrada")
        try:
            app.state.account_store.authenticate(user.email, body.password)
        except AccountError as exc:
            raise HTTPException(401, "Senha inválida") from exc
        try: app.state.core.listener.stop()
        except Exception: pass
        app.state.account_store.revoke_all_sessions(user_id)
        purge_access_for_user(user_id)
        try: app.state.vault.clear()
        except Exception: pass
        user_dir = app.state.base_settings.data_dir / "users" / user_id
        app.state.core = None; app.state.active_user_id = None
        if user_dir.exists(): shutil.rmtree(user_dir)
        app.state.account_store.delete_user(user_id)
        return {"status": "deleted", "local_user_data_deleted": True}

    @app.get("/api/audit", dependencies=[Depends(authorized)])
    def audit():
        return app.state.core.audit.list()

    @app.delete("/api/audit", dependencies=[Depends(authorized)])
    def clear_audit():
        app.state.core.audit.clear()
        return {"status": "cleared"}

    return app


app = create_app()
