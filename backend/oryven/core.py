"""MVP orchestrator: perceive -> propose -> approve -> execute -> audit -> report."""
from collections import deque
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path
import sys
from .release_info import VERSION
import time

from .audit import AuditLog
from .config import Settings
from .executor import BrowserExecutor, WindowsAppExecutor, ExecutionError
from .governance import ApprovalStore
from .intent import parse_intent, strip_wake, parse_dynamic_app_name
from .models import Event, SearchIntent
from .missions import MissionStore, MissionError, plan_text, split_steps
from .voice import Speaker, VoiceListener
from .voice_profile import VoiceProfile
from .elevenlabs_tts import ElevenLabsSpeaker
from .computer_control import WindowInspector, ComputerControlError
from .window_actions import WindowActions, WindowActionError
from .browser_control import PlaywrightInspector, BrowserControlError
from .buno_bridge import BunoHealthBridge, BunoConnectionError
from .chat_memory import ChatMemory
from .developer_runtime import DeveloperRuntime, DeveloperRuntimeError
from .professional_agents import ProfessionalAgentRegistry
from .skills import SkillCatalog, SkillError
from .work_runtime import WorkRuntime, WorkRuntimeError
from .professional_runtime import ProfessionalRuntime, ProfessionalRuntimeError
from .ml.intent_router import LocalIntentRouter
from .apps import AppCatalog, AppDiscoveryError
from .visual_perception import VisualPerception, VisualPerceptionError
from .vision_provider import ScreenUnderstanding, StructuredScreenProvider, OllamaVisionProvider, VisionProviderError
from .multi_app_planner import MultiAppPlanner, MultiAppPlannerError
from .autonomous_orchestrator import (AdaptiveMissionPlanner, MissionAutonomyStore,
    SupervisedMissionPolicy, AutonomousMissionError)
from .buno_mission_planner import BunoAIMissionPlanner, BunoMissionPlannerError
from .projects import ProjectStore, ProjectError
from .professional_memory import ProfessionalMemory, ProfessionalMemoryError
from .onboarding import OnboardingState
from .context_engine import ContextEngine
from .mission_intelligence import MissionIntelligenceStore
from .functional_mvp import FunctionalMVPPlanner, FunctionalMVPError
from .commercial import CommercialStore, DataPortability
from .models import (AppLaunchIntent, WindowListIntent, WindowTreeIntent, BrowserInspectIntent, BunoChatIntent,
                     WindowFocusIntent, WindowButtonIntent, DeveloperActionIntent, WorkActionIntent,
                     DynamicAppLaunchIntent, WindowControlInvokeIntent, WindowVisualSnapshotIntent, WindowUnderstandIntent,
                     WindowTextInputIntent, ProfessionalActionIntent)


class OryvenCore:
    def __init__(self, settings: Settings, executor: BrowserExecutor | None = None,
                 speaker: Speaker | None = None, listener: VoiceListener | None = None,
                 clock=None, app_executor: WindowsAppExecutor | None = None,
                 window_inspector: WindowInspector | None = None,
                 browser_inspector: PlaywrightInspector | None = None,
                 buno_bridge: BunoHealthBridge | None = None,
                 window_actions: WindowActions | None = None,
                 app_catalog: AppCatalog | None = None,
                 visual_perception: VisualPerception | None = None, screen_understanding: ScreenUnderstanding | None = None):
        self.settings = settings
        self._clock = clock or time.monotonic
        self._awake_until = 0.0
        self._lock = RLock()
        self._events: deque[Event] = deque(maxlen=120)
        self._event_id = 0
        self.approvals = ApprovalStore(ttl_seconds=settings.approval_seconds)
        self.audit = AuditLog(settings.data_dir / "audit.sqlite3")
        self.missions = MissionStore(settings.data_dir / "missions.sqlite3")
        self.chat_memory = ChatMemory(settings.data_dir / "chat_memory.sqlite3")
        self.projects = ProjectStore(settings.data_dir / "projects.sqlite3")
        self.professional_memory = ProfessionalMemory(settings.data_dir / "professional_memory.sqlite3")
        self.onboarding = OnboardingState(settings.data_dir / "onboarding.json")
        self.context_engine = ContextEngine(settings.data_dir / "context.json", self.projects, self.professional_memory)
        self.mission_intelligence = MissionIntelligenceStore(settings.data_dir / "mission_intelligence.sqlite3")
        self.developer = DeveloperRuntime(settings.developer_roots, settings.developer_timeout_seconds)
        self.professional_agents = ProfessionalAgentRegistry()
        self.skill_catalog = SkillCatalog(Path(__file__).resolve().parents[2] / "skills" / "builtin")
        self.work = WorkRuntime(settings.work_roots, settings.work_timeout_seconds, settings.terminal_executables)
        self.professional = ProfessionalRuntime(self.work)
        self.intent_router = LocalIntentRouter(Path(__file__).resolve().parent / "ml" / "intent_model.json")
        self.voice_profile_path = settings.data_dir / "voice_profile.json"
        self.voice_profile = VoiceProfile.load(self.voice_profile_path)
        self.executor = executor or BrowserExecutor()
        self.app_executor = app_executor or WindowsAppExecutor()
        self.window_inspector = window_inspector or WindowInspector()
        self.window_actions = window_actions or WindowActions(self.window_inspector)
        self.app_catalog = app_catalog or AppCatalog()
        self.visual_perception = visual_perception or VisualPerception()
        if screen_understanding is not None:
            self.screen_understanding = screen_understanding
        else:
            vision = None
            if settings.vision_provider == "ollama" and settings.vision_model:
                try:
                    vision = OllamaVisionProvider(settings.vision_ollama_url, settings.vision_model, settings.vision_timeout_seconds)
                except VisionProviderError:
                    vision = None
            self.screen_understanding = ScreenUnderstanding(StructuredScreenProvider(), vision)
        self.multi_app_planner = MultiAppPlanner()
        self.autonomous_planner = AdaptiveMissionPlanner(self.professional_agents, self.skill_catalog)
        self.functional_mvp = FunctionalMVPPlanner(self.skill_catalog)
        self.commercial = CommercialStore(settings.data_dir / "commercial.sqlite3")
        self.autonomy = MissionAutonomyStore(settings.data_dir / "autonomous_missions.sqlite3")
        self.autonomous_policy = SupervisedMissionPolicy()
        self.buno_mission_planner = BunoAIMissionPlanner(self.professional_agents, self.skill_catalog)
        self._mission_context: dict[str, str] = {}
        self.browser_inspector = browser_inspector or PlaywrightInspector()
        self.buno_bridge = buno_bridge  # lazy; invalid config does not prevent offline boot

        if speaker is not None:
            self.speaker = speaker
        elif settings.elevenlabs_enabled and settings.elevenlabs_api_key and settings.elevenlabs_voice_id:
            self.speaker = ElevenLabsSpeaker(settings.elevenlabs_api_key, settings.elevenlabs_voice_id,
                                            settings.elevenlabs_model_id)
        else:
            self.speaker = Speaker()
        self.listener = listener or VoiceListener(settings.model_dir, self.handle_voice_text, self.voice_error, self.speaker)
        self.emit("system", f"Oryven iniciado como {self.voice_profile.assistant_name}. Microfone controlado pelas suas preferências.")
        if self.voice_profile.speak_on_startup:
            self.speaker.say(f"Olá. Eu sou {self.voice_profile.assistant_name}. Estou pronto para ajudar.")
        if self.voice_profile.background_listening_enabled:
            try:
                self.listener.start()
                self.emit("voice", "Escuta em segundo plano iniciada por preferência previamente autorizada.")
            except Exception as exc:
                self.emit("error", f"Escuta automática indisponível: {type(exc).__name__}")

    def emit(self, kind: str, message: str):
        with self._lock:
            self._event_id += 1
            event = Event(id=self._event_id, kind=kind, message=message,
                          at=datetime.now(timezone.utc).isoformat())
            self._events.append(event)
            return event

    def events_after(self, after: int = 0):
        with self._lock:
            return [e.model_dump() for e in self._events if e.id > after]

    def voice_error(self, message: str):
        self.emit("error", message)

    def handle_voice_text(self, text: str):
        detected, remaining = self.voice_profile.match_wake(text)
        if detected:
            with self._lock:
                self._awake_until = self._clock() + self.settings.wake_seconds
            self.emit("voice", "Palavra de ativação reconhecida.")
            if not remaining:
                self.speaker.say("Estou ouvindo.")
                return None
            return self.submit(remaining)
        with self._lock:
            awake = self._clock() < self._awake_until
        if not awake:
            return None
        return self.submit(text)

    def submit(self, text: str):
        if self.multi_app_planner.recognizes_excel_report(text):
            plan = self.plan_multi_app_mission(text, self._mission_context.get("workspace"),
                                               self._mission_context.get("spreadsheet_path"),
                                               self._mission_context.get("report_path"))
            if plan["status"] == "ready":
                with self._lock:
                    self._awake_until = 0.0
                return self.start_multi_app_mission(text, self._mission_context["workspace"],
                                                    self._mission_context["spreadsheet_path"],
                                                    self._mission_context.get("report_path"))
            self.emit("mission", "Missão multi-app reconhecida, mas falta contexto seguro: " + ", ".join(plan["missing"]))
            self.speaker.say("Reconheci a missão. Selecione a planilha e o workspace na interface antes de continuar.")
            return plan
        if len(split_steps(text)) > 1:
            try:
                return self.start_mission(text)
            except MissionError:
                self.emit("error", "A missão não foi criada: uma das etapas não é permitida.")
                self.speaker.say("Não posso executar essa missão.")
                return None
        intent = parse_intent(text)
        if intent is None:
            app_name = parse_dynamic_app_name(text)
            if app_name:
                try:
                    with self._lock:
                        self._awake_until = 0.0
                    return self.propose_app_launch(app_name)
                except AppDiscoveryError:
                    pass
            self.emit("assistant", "Comando ainda não mapeado para uma skill executável. Posso continuar pela interface profissional ou pela Buno AI.")
            self.speaker.say("Ainda não tenho uma skill executável para esse pedido.")
            return None
        with self._lock:
            self._awake_until = 0.0
        pending = self.approvals.propose(intent)
        self.audit.write(intent.kind, "proposed", pending.id)
        self.emit("approval", f"Autorização necessária: {pending.description}.")
        self.speaker.say("Posso executar essa ação? Confirme na tela.")
        return pending.model_dump()

    def propose_window_list(self):
        return self._propose_control(WindowListIntent())

    def propose_window_tree(self, handle: int):
        return self._propose_control(WindowTreeIntent(handle=handle))

    def propose_window_visual_snapshot(self, handle: int):
        return self._propose_control(self.window_actions.preview_visual_snapshot(handle))

    def propose_window_understanding(self, handle: int, prompt: str = ""):
        base = self.window_actions.preview_visual_snapshot(handle)
        return self._propose_control(WindowUnderstandIntent(**base.model_dump(exclude={"kind"}), prompt=prompt))

    def propose_browser_inspection(self, url: str):
        from .browser_control import approved_public_url
        # Validate before creating the approval; canonicalize the exact target.
        return self._propose_control(BrowserInspectIntent(url=approved_public_url(url)))

    def propose_window_focus(self, handle: int):
        return self._propose_control(self.window_actions.preview_focus(handle))

    def propose_window_button(self, handle: int, path: tuple[int, ...]):
        return self._propose_control(self.window_actions.preview_button(handle, path))

    def propose_app_launch(self, app_name: str):
        resolved = self.app_catalog.resolve(app_name)
        return self._propose_control(DynamicAppLaunchIntent(
            app_name=resolved.name, launch_target=resolved.launch_target, target_type=resolved.target_type))

    def propose_window_invoke(self, handle: int, path: tuple[int, ...]):
        return self._propose_control(self.window_actions.preview_invoke(handle, path))

    def propose_window_set_text(self, handle: int, path: tuple[int, ...], text: str, replace: bool = True):
        return self._propose_control(self.window_actions.preview_set_text(handle, path, text, replace))

    def _propose_control(self, intent):
        with self._lock:
            pending = self.approvals.propose(intent)
            self.audit.write(intent.kind, "proposed", pending.id)  # no UI contents in audit
            self.emit("approval", f"Solicitada autorização específica: {intent.kind}.")
            return pending.model_dump()

    def buno_health(self):
        # Never send text, key, computer context, cookies or other user data.
        bridge = self.buno_bridge or BunoHealthBridge(self.settings.buno_api_url, bearer_token=self.settings.buno_bearer_token)
        return bridge.check()

    def propose_buno_chat(self, message: str):
        if not message.strip():
            raise BunoConnectionError("Informe uma pergunta não vazia.")
        # Consent is tied to exact prompt digest, never an open-ended permission.
        return self._propose_control(BunoChatIntent(message=message))

    def propose_developer_action(self, action: str, workspace: str):
        # Workspace validation occurs both before approval target generation and again at execution.
        intent = DeveloperActionIntent(action=action, workspace=workspace)
        self.developer._workspace(workspace)
        return self._propose_control(intent)


    def onboarding_status(self):
        return self.onboarding.get()

    def update_onboarding(self, **patch):
        return self.onboarding.update(**patch)

    def list_projects(self):
        return self.projects.list()

    def create_project(self, name: str, workspace: str, description: str = "", favorite_agents=None):
        project = self.projects.create(name, workspace, description, favorite_agents)
        self.onboarding.update(workspace_configured=True)
        return project

    def update_project(self, project_id: str, **patch):
        return self.projects.update(project_id, **patch)

    def delete_project(self, project_id: str):
        self.context_engine.clear_if_active(project_id)
        self.professional_memory.clear(project_id)
        return self.projects.delete(project_id)

    def context_status(self):
        project = self.context_engine.active_project()
        return {"active_project": project, "permissions_granted": False}

    def set_active_project(self, project_id: str | None):
        return self.context_engine.set_active_project(project_id)

    def context_preview(self, objective: str, explicit_context: dict | None = None):
        return self.context_engine.build(objective, explicit_context).preview()

    def demo_readiness(self):
        onboarding = self.onboarding.get()
        active_project = self.context_engine.active_project()
        checks = {
            "onboarding_complete": bool(onboarding.get("completed")),
            "assistant_named": bool(onboarding.get("assistant_named")),
            "voice_configured": bool(onboarding.get("voice_configured")),
            "workspace_configured": bool(onboarding.get("workspace_configured")),
            "permissions_reviewed": bool(onboarding.get("permissions_reviewed")),
            "active_project": active_project is not None,
        }
        order = [
            ("assistant_named", "Escolha o nome do assistente", "settings"),
            ("voice_configured", "Configure voz e microfone", "settings"),
            ("workspace_configured", "Crie seu primeiro projeto", "projects"),
            ("permissions_reviewed", "Revise as regras de autorização", "home"),
            ("active_project", "Selecione um projeto ativo", "projects"),
        ]
        next_action = {"key": "create_mission", "label": "Crie sua primeira missão", "view": "home"}
        for key, label, view in order:
            if not checks[key]:
                next_action = {"key": key, "label": label, "view": view}
                break
        ready = all(checks.values())
        return {
            "ready": ready,
            "checks": checks,
            "next_action": next_action,
            "active_project": None if active_project is None else {"id": active_project["id"], "name": active_project["name"]},
            "permissions_granted": False,
        }

    def list_functional_mvp_flows(self):
        active = self.context_engine.active_project()
        flows = []
        for item in self.functional_mvp.list():
            plan = self.functional_mvp.plan(item["id"], active_project=active, context={})
            flows.append({**item, "status": plan["status"], "missing": plan.get("missing", []), "permissions_granted": False})
        return {"version": VERSION, "flows": flows, "functional_mvp": all(f["status"] == "ready" for f in flows), "permissions_granted": False}

    def plan_functional_mvp_flow(self, flow_id: str, context: dict | None = None):
        return self.functional_mvp.plan(flow_id, active_project=self.context_engine.active_project(), context=context or {})

    def start_functional_mvp_flow(self, flow_id: str, objective: str = "", context: dict | None = None):
        plan = self.plan_functional_mvp_flow(flow_id, context)
        if plan["status"] != "ready":
            return plan
        from types import SimpleNamespace
        steps = [SimpleNamespace(skill_id=item["skill_id"], arguments=item["arguments"]) for item in plan["steps"]]
        title = objective.strip() or plan["flow"]["name"]
        return self.start_skill_mission(
            title, steps, planner="functional-mvp-0.18",
            reason=f"Fluxo oficial do Functional MVP: {plan['flow']['name']}."
        )

    def professional_memory_status(self):
        return {"enabled": self.professional_memory.enabled()}

    def set_professional_memory_enabled(self, enabled: bool):
        return self.professional_memory.set_enabled(enabled)

    def list_professional_memory(self, project_id: str | None = None, limit: int = 200):
        return self.professional_memory.list(project_id, limit)

    def remember_professional(self, content: str, kind: str = "fact", project_id: str | None = None):
        if project_id is not None:
            self.projects.get(project_id)
        return self.professional_memory.remember(content, kind, project_id)

    def forget_professional(self, item_id: str):
        return self.professional_memory.delete(item_id)

    def clear_professional_memory(self, project_id: str | None = None):
        if project_id is not None:
            self.projects.get(project_id)
        return self.professional_memory.clear(project_id)

    def classify_intent(self, text: str):
        route = self.intent_router.predict(text)
        return None if route is None else {"label": route.label, "confidence": route.confidence, "source": route.source}

    def list_professional_agents(self):
        return self.professional_agents.list()

    def professional_plan(self, objective: str, agent_id: str | None = None):
        plan = self.professional_agents.plan(objective, preferred_agent_id=agent_id)
        universal_families = list(dict.fromkeys([*plan["recommended_tool_families"], "ui_automation", "windows", "app"]))
        plan["recommended_skills"] = self.skill_catalog.recommend(universal_families, limit=40)
        plan["orchestration"] = {
            "state": "draft",
            "permissions_granted": False,
            "next_step": "Escolha uma skill e proponha argumentos exatos para aprovação.",
        }
        return plan

    def list_skills(self):
        return self.skill_catalog.list()

    def build_skill_intent(self, skill_id: str, arguments: dict):
        # Live computer adapters are resolved against the current machine before approval.
        if skill_id == "app.launch.universal":
            unknown = set(arguments) - {"app_name"}
            if unknown or "app_name" not in arguments:
                raise SkillError("Argumentos inválidos para app.launch.universal.")
            resolved = self.app_catalog.resolve(str(arguments["app_name"]))
            return DynamicAppLaunchIntent(app_name=resolved.name, launch_target=resolved.launch_target, target_type=resolved.target_type)
        if skill_id == "computer.control.invoke":
            unknown = set(arguments) - {"handle", "path"}
            if unknown or not {"handle", "path"}.issubset(arguments):
                raise SkillError("Argumentos inválidos para computer.control.invoke.")
            return self.window_actions.preview_invoke(int(arguments["handle"]), tuple(arguments["path"]))
        if skill_id == "computer.control.set_text":
            unknown = set(arguments) - {"handle", "path", "text", "replace"}
            if unknown or not {"handle", "path", "text"}.issubset(arguments):
                raise SkillError("Argumentos inválidos para computer.control.set_text.")
            return self.window_actions.preview_set_text(int(arguments["handle"]), tuple(arguments["path"]),
                                                        str(arguments["text"]), bool(arguments.get("replace", True)))
        if skill_id == "computer.window.capture":
            unknown = set(arguments) - {"handle"}
            if unknown or "handle" not in arguments:
                raise SkillError("Argumentos inválidos para computer.window.capture.")
            return self.window_actions.preview_visual_snapshot(int(arguments["handle"]))
        intent = self.skill_catalog.build_intent(skill_id, arguments)
        if isinstance(intent, WorkActionIntent):
            self.work.validate(intent)
        elif isinstance(intent, DeveloperActionIntent):
            self.developer._workspace(intent.workspace)
        elif isinstance(intent, ProfessionalActionIntent):
            self.professional.validate(intent)
        return intent

    def propose_skill(self, skill_id: str, arguments: dict):
        return self._propose_control(self.build_skill_intent(skill_id, arguments))

    def set_mission_context(self, workspace: str, spreadsheet_path: str, report_path: str = "oryven-report.docx"):
        # Validate through the same work-root boundary used by professional skills.
        root = self.work._workspace(workspace)
        source = self.work._target(root, spreadsheet_path, must_exist=True)
        if source.suffix.lower() != ".xlsx":
            raise MissionError("O contexto multi-app exige uma planilha .xlsx.")
        output = self.work._target(root, report_path)
        if output.suffix.lower() != ".docx":
            raise MissionError("O relatório multi-app deve ser .docx.")
        self._mission_context = {"workspace": str(root), "spreadsheet_path": spreadsheet_path, "report_path": report_path}
        self.emit("mission", "Contexto multi-app selecionado sem executar ações.")
        return {"configured": True, "workspace": str(root), "spreadsheet_path": spreadsheet_path,
                "report_path": report_path, "permissions_granted": False}

    def get_mission_context(self):
        return {**self._mission_context, "configured": bool(self._mission_context), "permissions_granted": False}

    def plan_multi_app_mission(self, objective: str, workspace: str | None = None,
                               spreadsheet_path: str | None = None, report_path: str | None = None):
        return self.multi_app_planner.plan(objective, workspace=workspace, spreadsheet_path=spreadsheet_path, report_path=report_path)

    def start_multi_app_mission(self, objective: str, workspace: str, spreadsheet_path: str, report_path: str | None = None):
        plan = self.plan_multi_app_mission(objective, workspace, spreadsheet_path, report_path)
        if plan["status"] != "ready":
            raise MissionError("A missão multi-app precisa de contexto adicional.")
        from types import SimpleNamespace
        steps = [SimpleNamespace(skill_id=item["skill_id"], arguments=item["arguments"]) for item in plan["steps"]]
        return self.start_skill_mission(objective, steps, planner="multi-app-template", reason=plan.get("note", "Template multi-app seguro selecionado."))

    def start_skill_mission(self, objective: str, steps, *, planner: str = "typed-skill-plan", agent_id: str = "", reason: str = "Plano tipado validado localmente."):
        intents = [self.build_skill_intent(step.skill_id, step.arguments) for step in steps]
        mission = self.missions.create(objective, intents)
        self.mission_intelligence.register(mission["id"], planner=planner, agent_id=agent_id, reason_summary=reason)
        self.emit("mission", f"Missão profissional planejada: {len(intents)} etapa(s) tipada(s).")
        return self._propose_mission_step(mission["id"])

    def _buno_bridge(self):
        return self.buno_bridge or BunoHealthBridge(
            self.settings.buno_api_url, bearer_token=self.settings.buno_bearer_token
        )

    def plan_buno_ai_mission(self, objective: str, context: dict | None = None, max_steps: int = 8):
        max_steps = max(1, min(int(max_steps), 8))
        bundle = self.context_engine.build(objective, context or {})
        plan = self.buno_mission_planner.plan(self._buno_bridge(), objective, bundle.public_context, max_steps, bindings=bundle.bindings)
        data = plan.as_dict()
        # Validate again through the live runtimes/workspace boundaries before exposing a ready plan.
        for step in plan.steps:
            self.build_skill_intent(step.skill_id, dict(step.arguments))
        data["max_steps"] = max_steps
        data["recovery_budget"] = 1
        return data

    def start_buno_ai_mission(self, objective: str, context: dict | None = None, max_steps: int = 8,
                              recovery_budget: int = 1):
        max_steps = max(1, min(int(max_steps), 8))
        recovery_budget = max(0, min(int(recovery_budget), 2))
        bundle = self.context_engine.build(objective, context or {})
        plan = self.buno_mission_planner.plan(self._buno_bridge(), objective, bundle.public_context, max_steps, bindings=bundle.bindings)
        intents = [self.build_skill_intent(step.skill_id, dict(step.arguments)) for step in plan.steps]
        mission = self.missions.create(objective, intents)
        self.autonomy.register(mission["id"], objective, plan.agent, max_steps, recovery_budget)
        self.mission_intelligence.register(
            mission["id"], planner="buno-ai", agent_id=plan.agent.get("agent_id", ""),
            reason_summary=plan.rationale or "Plano dinâmico proposto pela Buno AI e validado localmente.",
            context=bundle.public_context, selected_memory_ids=bundle.selected_memory_ids,
        )
        self.audit.write("mission.buno_ai", "planned", mission["id"])
        self.emit("mission", f"Plano dinâmico Buno validado com {len(intents)} etapa(s); nenhuma permissão foi concedida.")
        return self._propose_mission_step(mission["id"])

    def plan_autonomous_mission(self, objective: str, context: dict | None = None, steps=None,
                                max_steps: int = 8, recovery_budget: int = 1):
        max_steps = max(1, min(int(max_steps), 8))
        recovery_budget = max(0, min(int(recovery_budget), 2))
        bundle = self.context_engine.build(objective, context or {})
        merged_context = {**bundle.local_context, **dict(context or {})}
        plan = self.autonomous_planner.plan(objective, merged_context, list(steps or []))
        data = plan.as_dict()
        data["max_steps"] = max_steps
        data["recovery_budget"] = recovery_budget
        if len(plan.steps) > max_steps:
            data["status"] = "needs_scope_reduction"
            data["reason"] = "O plano excede o limite de passos desta missão."
        return data

    def start_autonomous_mission(self, objective: str, context: dict | None = None, steps=None,
                                 max_steps: int = 8, recovery_budget: int = 1):
        plan = self.plan_autonomous_mission(objective, context, steps, max_steps, recovery_budget)
        if plan["status"] != "ready":
            return plan
        typed_steps = [type("Step", (), item) for item in plan["steps"]]
        intents = [self.build_skill_intent(step.skill_id, step.arguments) for step in typed_steps]
        mission = self.missions.create(objective, intents)
        self.autonomy.register(mission["id"], objective, plan["agent"], plan["max_steps"], plan["recovery_budget"])
        bundle = self.context_engine.build(objective, context or {})
        self.mission_intelligence.register(
            mission["id"], planner="local-adaptive", agent_id=plan["agent"].get("agent_id", ""),
            reason_summary=plan.get("reason", "Plano adaptativo local criado com contexto explícito."),
            context=bundle.public_context, selected_memory_ids=bundle.selected_memory_ids,
        )
        self.audit.write("mission.autonomous", "planned", mission["id"])
        self.emit("mission", f"Missão autônoma supervisionada planejada com {len(intents)} etapa(s).")
        return self._propose_mission_step(mission["id"])

    def autonomous_mission_status(self, mission_id: str):
        meta = self.autonomy.get(mission_id)
        mission = self.missions.get(mission_id)
        return {"mission": mission, "autonomy": meta, "permissions_granted": False}

    def autonomous_advance(self, mission_id: str):
        meta = self.autonomy.get(mission_id)
        mission = self.missions.get(mission_id)
        status = mission["status"]
        if status in {"awaiting_approval", "executing"}:
            return {"mission": mission, "autonomy": meta, "state": status,
                    "message": "A missão aguarda a ação humana/execução atual.", "permissions_granted": False}
        if status == "awaiting_verification":
            intent = self.missions.step_intent(mission_id, status="awaiting_verification")
            confirmed, note = self.autonomous_policy.automatic_verification(intent)
            if confirmed is None:
                self.autonomy.note(mission_id, note)
                return {"mission": mission, "autonomy": self.autonomy.get(mission_id),
                        "state": "manual_verification_required", "message": note, "permissions_granted": False}
            mission = self.missions.verify_automatic(mission_id, confirmed, note)
            self.mission_intelligence.add(mission_id, phase="verification", outcome="success" if confirmed else "failed", summary=note)
            self.autonomy.note(mission_id, note)
            self.audit.write("mission.autonomous", "auto_verified" if confirmed else "auto_verification_failed", mission_id)
            status = mission["status"]
            if status == "completed":
                return {"mission": mission, "autonomy": self.autonomy.get(mission_id),
                        "state": "completed", "message": "Missão concluída com evidências verificadas.",
                        "permissions_granted": False}
        if status == "failed":
            failed_intent = self.missions.step_intent(mission_id, status="failed")
            recovery = None
            recovery_source = "local-policy"
            if meta["recovery_used"] < meta["recovery_budget"] and self.settings.buno_bearer_token:
                try:
                    failed_skill = getattr(failed_intent, "action", getattr(failed_intent, "kind", "unknown"))
                    failed_args = failed_intent.model_dump(exclude={"kind"})
                    recovery_context = self.context_engine.build(meta["objective"], {})
                    proposed = self.buno_mission_planner.recovery_step(
                        self._buno_bridge(), meta["objective"], str(failed_skill), failed_args,
                        "A etapa falhou durante execução; proponha apenas diagnóstico de baixo risco.",
                        recovery_context.public_context, bindings=recovery_context.bindings
                    )
                    recovery = self.build_skill_intent(proposed.skill_id, dict(proposed.arguments))
                    recovery_source = "buno-ai"
                except (BunoMissionPlannerError, BunoConnectionError, SkillError, WorkRuntimeError,
                        ProfessionalRuntimeError, DeveloperRuntimeError, ValueError):
                    recovery = None
            if recovery is None:
                recovery = self.autonomous_policy.recovery_for(failed_intent)
            if recovery is None or meta["recovery_used"] >= meta["recovery_budget"]:
                self.autonomy.note(mission_id, "Falha exige revisão humana; nenhuma nova ação foi autorizada.")
                self.mission_intelligence.add(mission_id, phase="recovery", outcome="needs_review", summary="Nenhuma recuperação segura disponível ou orçamento de recuperação esgotado.")
                return {"mission": self.missions.get(mission_id), "autonomy": self.autonomy.get(mission_id),
                        "state": "needs_review", "message": "Falha sem recuperação segura disponível.",
                        "permissions_granted": False}
            self.autonomy.consume_recovery(mission_id, f"Recuperação supervisionada ({recovery_source}) inserida antes de tentar novamente a etapa exata.")
            mission = self.missions.inject_recovery(mission_id, recovery, retry_failed=True)
            self.mission_intelligence.add(mission_id, phase="recovery", outcome="injected", summary=f"Recuperação supervisionada preparada por {recovery_source}.", evidence={"source": recovery_source, "recovery_kind": recovery.kind})
            self.audit.write("mission.autonomous", f"recovery_injected:{recovery_source}", mission_id)
            self.emit("mission", f"Recuperação supervisionada preparada por {recovery_source}; exige nova autorização.")
            return self._propose_mission_step(mission_id)
        if status in {"planned", "paused"}:
            return self._propose_mission_step(mission_id)
        return {"mission": mission, "autonomy": self.autonomy.get(mission_id),
                "state": status, "message": "Nenhum avanço automático seguro está disponível neste estado.",
                "permissions_granted": False}

    def propose_work_action(self, action: str, workspace: str, path: str = ".", content: str | None = None,
                            executable: str | None = None, args: list[str] | None = None):
        intent = WorkActionIntent(action=action, workspace=workspace, path=path, content=content,
                                  executable=executable, args=args or [])
        self.work.validate(intent)
        return self._propose_control(intent)

    def _propose_mission_step(self, mission_id: str):
        index, intent = self.missions.next_intent(mission_id)
        approval = self.approvals.propose(intent)
        try:
            self.missions.proposed(mission_id, index, approval.id)
        except Exception:
            self.approvals.cancel_one(approval.id)
            raise
        self.audit.write(intent.kind, "mission_proposed", approval.id)
        self.mission_intelligence.add(mission_id, phase="proposal", outcome="awaiting_approval", summary=f"Etapa {index + 1} proposta para autorização.", step_index=index, evidence={"kind": intent.kind, "target": approval.target})
        self.emit("approval", f"Missão aguardando autorização: {approval.description}.")
        self.speaker.say("Tenho uma etapa pronta. Confirme na tela antes de executar.")
        return self.missions.get(mission_id)

    def start_mission(self, text: str):
        with self._lock:
            intents = plan_text(text)
            mission = self.missions.create(text, intents)
            self.mission_intelligence.register(mission["id"], planner="deterministic-text", reason_summary="Comandos explícitos reconhecidos pelo parser local allowlisted.")
            self.emit("mission", f"Missão planejada: {len(intents)} etapa(s) conhecida(s).")
            return self._propose_mission_step(mission["id"])

    def resume_mission(self, mission_id: str):
        with self._lock:
            m = self.missions.get(mission_id)
            if m["status"] == "awaiting_approval":
                current = next((step["action_id"] for step in m["steps"] if step["status"] == "awaiting_approval"), None)
                if current and any(a.id == current for a in self.approvals.list_pending()):
                    raise MissionError("Há uma autorização pendente; aprove, negue ou cancele.")
                self.missions.pause(mission_id)  # previously-issued token no longer exists
            return self._propose_mission_step(mission_id)

    def verify_mission_step(self, mission_id: str, confirmed: bool):
        # Dispatch only requests an action. Confirmation is always from a person.
        with self._lock:
            mission = self.missions.verify(mission_id, confirmed)
            self.mission_intelligence.add(mission_id, phase="verification", outcome="verified_by_user" if confirmed else "failed_by_user", summary="Resultado confirmado pelo usuário." if confirmed else "Usuário informou que o resultado não correspondeu ao esperado.")
            self.audit.write("mission", "user_confirmed" if confirmed else "user_reported_failure", mission_id)
            self.emit("mission", "Etapa confirmada pelo usuário." if confirmed else "Etapa marcada como falha pelo usuário.")
            if mission["status"] == "planned":
                return self._propose_mission_step(mission_id)
            return mission

    def cancel_mission(self, mission_id: str):
        with self._lock:
            mission = self.missions.get(mission_id)
            result = self.missions.cancel(mission_id)
            for step in mission["steps"]:
                if step["action_id"]:
                    self.approvals.cancel_one(step["action_id"])
            self.audit.write("mission", "cancelled", mission_id)
            self.emit("mission", "Missão cancelada. Ações já despachadas não são desfeitas.")
            return result

    def delete_mission(self, mission_id: str):
        with self._lock:
            result = self.missions.delete(mission_id)
            self.mission_intelligence.delete(mission_id)
            self.audit.write("mission", "history_deleted")
            return result

    def _mission_dispatched(self, mission_id: str | None, action_id: str, message: str):
        if mission_id:
            self.missions.resolved(mission_id, action_id, "dispatched", message)
            self.mission_intelligence.add(mission_id, phase="execution", outcome="dispatched", summary=message)

    def decide(self, action_id: str, decision: str):
        # Lock prevents stop() racing between approval check and dispatch.
        with self._lock:
            mission_id = self.missions.action_owner(action_id)
            intent = self.approvals.decide(action_id, approved=decision == "approve")
            if intent is None:
                if mission_id:
                    self.missions.resolved(mission_id, action_id, "denied", "Ação negada pelo usuário.")
                    self.mission_intelligence.add(mission_id, phase="authorization", outcome="denied", summary="A etapa foi negada pelo usuário.")
                self.audit.write("action", "denied", action_id)
                self.emit("assistant", "Ação cancelada antes da execução.")
                self.speaker.say("Ação cancelada.")
                return {"outcome": "denied", "message": "Ação negada."}
            if mission_id:
                self.missions.executing(mission_id, action_id)
            self.audit.write(intent.kind, "approved", action_id)
            try:
                if isinstance(intent, SearchIntent):
                    result = self.executor.execute(intent)
                elif isinstance(intent, AppLaunchIntent):
                    result = self.app_executor.execute(intent)
                elif isinstance(intent, DynamicAppLaunchIntent):
                    resolved = self.app_catalog.resolve(intent.app_name)
                    if (resolved.launch_target != intent.launch_target or resolved.target_type != intent.target_type):
                        raise AppDiscoveryError("O aplicativo mudou desde a autorização. Atualize o inventário e aprove novamente.")
                    data = self.app_catalog.launch(resolved)
                    self.audit.write(intent.kind, "launched", action_id)
                    self.emit("assistant", f"Abertura solicitada para {intent.app_name}.")
                    message = "Aplicativo iniciado." if data.get("verified") else "Abertura solicitada; confirme a janela resultante."
                    self._mission_dispatched(mission_id, action_id, message)
                    return {"outcome": "verified" if data.get("verified") else "unverified", "message": message, "data": data}
                elif isinstance(intent, WindowListIntent):
                    data = self.window_inspector.list_windows()
                    self.audit.write(intent.kind, "inspected", action_id)
                    self.emit("assistant", "Janelas inspecionadas após autorização. Confira os dados na tela.")
                    return {"outcome": "inspected", "message": "Metadados obtidos.", "data": data}
                elif isinstance(intent, WindowTreeIntent):
                    data = self.window_inspector.inspect_window(intent.handle)
                    self.audit.write(intent.kind, "inspected", action_id)
                    self.emit("assistant", "Árvore UIA consultada após autorização; não salvei os controles.")
                    return {"outcome": "inspected", "message": "Metadados obtidos.", "data": data}
                elif isinstance(intent, WindowVisualSnapshotIntent):
                    data = self.visual_perception.capture(intent, self.window_actions)
                    self.audit.write(intent.kind, "captured_ephemeral", action_id)
                    self.emit("assistant", "Snapshot visual capturado em memória após autorização.")
                    self._mission_dispatched(mission_id, action_id, data["message"])
                    return {"outcome": "captured", "message": data["message"], "data": data}
                elif isinstance(intent, WindowUnderstandIntent):
                    snapshot_intent = WindowVisualSnapshotIntent(**intent.model_dump(exclude={"kind", "prompt"}))
                    snapshot = self.visual_perception.capture(snapshot_intent, self.window_actions)
                    ui_tree = self.window_inspector.inspect_window(intent.handle)
                    scene = self.screen_understanding.analyze(snapshot, ui_tree, intent.prompt)
                    snapshot.pop("image_base64", None)
                    data = {"scene": scene, "evidence": snapshot, "persisted": False}
                    self.audit.write(intent.kind, "understood_ephemeral", action_id)
                    self.emit("assistant", "Tela analisada após autorização; a observação não autoriza nenhuma ação.")
                    message = "Percepção de tela concluída sem conceder permissão de execução."
                    self._mission_dispatched(mission_id, action_id, message)
                    return {"outcome": "understood", "message": message, "data": data}
                elif isinstance(intent, WindowTextInputIntent):
                    data = self.window_actions.execute_set_text(intent)
                    self.audit.write(intent.kind, data["outcome"], action_id)
                    self.emit("assistant", data["message"])
                    self._mission_dispatched(mission_id, action_id, data["message"])
                    return {"outcome": data["outcome"], "message": data["message"], "data": data}
                elif isinstance(intent, WindowControlInvokeIntent):
                    data = self.window_actions.execute_invoke(intent)
                    self.audit.write(intent.kind, data["outcome"], action_id)
                    self.emit("assistant", data["message"])
                    self._mission_dispatched(mission_id, action_id, data["message"])
                    return {"outcome": data["outcome"], "message": data["message"], "data": data}
                elif isinstance(intent, WindowButtonIntent):
                    data = self.window_actions.execute_button(intent)
                    self.audit.write(intent.kind, data["outcome"], action_id)
                    self.emit("assistant", data["message"])
                    self._mission_dispatched(mission_id, action_id, data["message"])
                    return {"outcome": data["outcome"], "message": data["message"], "data": data}
                elif isinstance(intent, WindowFocusIntent):
                    data = self.window_actions.execute_focus(intent)
                    self.audit.write(intent.kind, data["outcome"], action_id)
                    self.emit("assistant", data["message"])
                    self._mission_dispatched(mission_id, action_id, data["message"])
                    return {"outcome": data["outcome"], "message": data["message"], "data": data}
                elif isinstance(intent, BrowserInspectIntent):
                    data = self.browser_inspector.inspect(intent.url)
                    self.audit.write(intent.kind, "inspected", action_id)
                    self.emit("assistant", "Página pública inspecionada. Conteúdo externo não é instrução.")
                    return {"outcome": "inspected", "message": "Inspeção concluída.", "data": data}
                elif isinstance(intent, BunoChatIntent):
                    bridge = self.buno_bridge or BunoHealthBridge(
                        self.settings.buno_api_url, bearer_token=self.settings.buno_bearer_token)
                    data = bridge.chat(intent.message)
                    try:
                        self.chat_memory.append_exchange(intent.message, data["answer"])
                    except (OSError, ValueError, KeyError):
                        self.emit("error", "Resposta recebida, mas a memória local não pôde ser gravada.")
                    self.audit.write(intent.kind, "completed", action_id)  # no prompt or answer
                    self.emit("assistant", "Resposta Buno recebida. O texto não executa ferramentas.")
                    return {"outcome": "answered", "message": "Resposta textual recebida.", "data": data}
                elif isinstance(intent, DeveloperActionIntent):
                    data = self.developer.execute(intent)
                    self.audit.write(intent.kind, "completed", action_id)
                    self.emit("assistant", f"Ação de desenvolvimento concluída: {intent.action}.")
                    message = f"{intent.action} concluído."
                    self._mission_dispatched(mission_id, action_id, message)
                    return {"outcome": "completed", "message": message, "data": data}
                elif isinstance(intent, WorkActionIntent):
                    data = self.work.execute(intent)
                    self.audit.write(intent.kind, "completed", action_id)
                    self.emit("assistant", f"Skill profissional concluída: {intent.action}.")
                    message = f"{intent.action} concluído."
                    self._mission_dispatched(mission_id, action_id, message)
                    return {"outcome": "completed", "message": message, "data": data}
                elif isinstance(intent, ProfessionalActionIntent):
                    data = self.professional.execute(intent)
                    self.audit.write(intent.kind, "completed", action_id)
                    self.emit("assistant", f"Professional Skill Pack concluído: {intent.action}.")
                    message = f"{intent.action} concluído."
                    self._mission_dispatched(mission_id, action_id, message)
                    return {"outcome": "completed", "message": message, "data": data}
                else:
                    raise ExecutionError("Ação não permitida pelo executor.")
            except (ExecutionError, ComputerControlError, WindowActionError, BrowserControlError, BunoConnectionError, DeveloperRuntimeError, WorkRuntimeError, ProfessionalRuntimeError, SkillError, AppDiscoveryError, VisualPerceptionError, VisionProviderError, MultiAppPlannerError) as exc:
                if mission_id:
                    self.missions.resolved(mission_id, action_id, "failed", str(exc))
                    self.mission_intelligence.add(mission_id, phase="execution", outcome="failed", summary=str(exc))
                self.audit.write(intent.kind, "failed", action_id)
                self.emit("error", str(exc))
                self.speaker.say("Não consegui solicitar a ação.")
                return {"outcome": "failed", "message": str(exc)}
            if mission_id:
                self.missions.resolved(mission_id, action_id, "dispatched", result)
                self.mission_intelligence.add(mission_id, phase="execution", outcome="dispatched", summary=str(result))
            self.audit.write(intent.kind, "dispatched", action_id)
            self.emit("assistant", result)
            self.speaker.say("Solicitei a execução. Confira o resultado na tela.")
            return {"outcome": "dispatched", "message": result}


    def mission_intelligence_view(self, mission_id: str):
        # Ensure the mission belongs to this user's current data_dir before returning its evidence.
        self.missions.get(mission_id)
        return self.mission_intelligence.get(mission_id)


    def get_voice_profile(self):
        return {
            "assistant_name": self.voice_profile.assistant_name,
            "language": self.voice_profile.language,
            "background_listening_enabled": self.voice_profile.background_listening_enabled,
            "speak_on_startup": self.voice_profile.speak_on_startup,
            "wake_enabled": self.voice_profile.wake_enabled,
        }

    def update_voice_profile(self, **values):
        profile = self.voice_profile.update(**values)
        # Enabling background listening is an explicit user preference persisted locally.
        if profile.background_listening_enabled and not self.listener.running:
            self.listener.start()
        elif not profile.background_listening_enabled and self.listener.running:
            self.listener.stop()
        profile.save(self.voice_profile_path)
        self.voice_profile = profile
        self.emit("voice", f"Preferências de voz atualizadas. Nome do assistente: {profile.assistant_name}.")
        return self.get_voice_profile()

    def stop_speaking(self):
        if hasattr(self.speaker, "stop"):
            self.speaker.stop()
        self.emit("voice", "Fala interrompida pelo usuário.")
        return {"status": "stopped"}

    def speak_test(self, text: str | None = None):
        message = (text or f"Olá. Eu sou {self.voice_profile.assistant_name}.").strip()[:350]
        self.speaker.say(message)
        return {"queued": True, "provider": getattr(self.speaker, "provider", "windows-local")}

    def emergency_stop(self):
        # Stop audio/mic outside the critical section to avoid re-entrant waits.
        self.listener.stop()
        if hasattr(self.speaker, "stop"):
            self.speaker.stop()
        with self._lock:
            cancelled = self.approvals.cancel_all()
            self.missions.pause_all_pending()
            self._awake_until = 0.0
            self.audit.write("session", "stopped")
            self.emit("system", f"Parada de emergência: microfone desligado e {cancelled} autorização(ões) cancelada(s).")
            return {"cancelled": cancelled, "microphone": "off"}

    def status(self):
        return {
            "version": VERSION,
            "platform": sys.platform,
            "microphone_on": self.listener.running,
            "model_installed": self.settings.model_dir.is_dir(),
            "voice_synthesis_enabled": self.speaker.enabled,
            "voice_provider": getattr(self.speaker, "provider", "windows-local"),
            "assistant_name": self.voice_profile.assistant_name,
            "wake_enabled": self.voice_profile.wake_enabled,
            "background_listening_enabled": self.voice_profile.background_listening_enabled,
            "pending_approvals": len(self.approvals.list_pending()),
            "mode": "local-first",
            "capabilities": ["browser.search", "app.launch", "missions.manual_verification", "computer.windows.list", "computer.window.inspect", "computer.window.capture", "computer.window.understand", "computer.window.focus", "computer.button.invoke", "computer.control.invoke", "computer.control.set_text", "app.launch.dynamic", "browser.inspect", "buno.health", "buno.chat", "developer.action", "ml.intent.route", "professional.agents", "professional.plan", "professional.skills", "professional.skill.propose", "filesystem.work", "terminal.supervised", "professional.skillpacks", "missions.autonomous.supervised", "missions.buno_ai.planner", "missions.buno_ai.self_correction"],
        }
