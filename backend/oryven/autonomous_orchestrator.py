"""Supervised autonomous mission orchestration for Oryven 0.15.

Autonomy means planning, verification and recovery. It never means permission.
Every side-effecting intent still passes through ApprovalStore one action at a time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
import sqlite3

from .models import (
    ExecutableIntent, WorkActionIntent, DeveloperActionIntent, ProfessionalActionIntent,
    WindowVisualSnapshotIntent, WindowUnderstandIntent, WindowListIntent, WindowTreeIntent,
    SkillMissionStep,
)
from .skills import SkillCatalog
from .professional_agents import ProfessionalAgentRegistry


class AutonomousMissionError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MissionAutonomyStore:
    """Small metadata store. Mission steps remain in MissionStore."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS autonomous_missions (
                mission_id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                max_steps INTEGER NOT NULL,
                recovery_budget INTEGER NOT NULL,
                recovery_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_note TEXT NOT NULL DEFAULT ''
            )""")

    def _db(self):
        conn = sqlite3.connect(str(self.path), timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def register(self, mission_id: str, objective: str, route: dict, max_steps: int, recovery_budget: int):
        now = _now()
        with self._lock, self._db() as db:
            db.execute("""INSERT OR REPLACE INTO autonomous_missions
                (mission_id, objective, agent_id, agent_name, max_steps, recovery_budget, recovery_used, created_at, updated_at, last_note)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, '')""",
                (mission_id, objective[:1200], route["agent_id"], route["name"], max_steps,
                 recovery_budget, now, now))

    def get(self, mission_id: str) -> dict:
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM autonomous_missions WHERE mission_id=?", (mission_id,)).fetchone()
            if row is None:
                raise AutonomousMissionError("Missão não está registrada como autônoma supervisionada.")
            return dict(row)

    def consume_recovery(self, mission_id: str, note: str) -> dict:
        with self._lock, self._db() as db:
            row = db.execute("SELECT * FROM autonomous_missions WHERE mission_id=?", (mission_id,)).fetchone()
            if row is None:
                raise AutonomousMissionError("Missão autônoma não encontrada.")
            if row["recovery_used"] >= row["recovery_budget"]:
                raise AutonomousMissionError("Orçamento de recuperação esgotado.")
            db.execute("UPDATE autonomous_missions SET recovery_used=recovery_used+1, updated_at=?, last_note=? WHERE mission_id=?",
                       (_now(), note[:500], mission_id))
        return self.get(mission_id)

    def note(self, mission_id: str, note: str):
        with self._lock, self._db() as db:
            db.execute("UPDATE autonomous_missions SET updated_at=?, last_note=? WHERE mission_id=?",
                       (_now(), note[:500], mission_id))


@dataclass(frozen=True)
class AdaptivePlan:
    status: str
    objective: str
    route: dict
    steps: tuple[SkillMissionStep, ...]
    missing: tuple[str, ...] = ()
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "objective": self.objective,
            "agent": self.route,
            "steps": [s.model_dump() for s in self.steps],
            "missing": list(self.missing),
            "reason": self.reason,
            "permissions_granted": False,
        }


class AdaptiveMissionPlanner:
    """Deterministic first-party planner. No guessed paths, credentials or app identities."""
    def __init__(self, agents: ProfessionalAgentRegistry, skills: SkillCatalog):
        self.agents = agents
        self.skills = skills

    @staticmethod
    def _project_test_skill(workspace: Path) -> str | None:
        if (workspace / "pom.xml").exists():
            return "test.maven"
        if (workspace / "package.json").exists():
            return "test.npm"
        python_markers = ("pyproject.toml", "pytest.ini", "setup.cfg", "requirements.txt")
        if any((workspace / marker).exists() for marker in python_markers):
            return "test.python"
        return None

    def plan(self, objective: str, context: dict | None = None,
             explicit_steps: list[SkillMissionStep] | None = None) -> AdaptivePlan:
        context = dict(context or {})
        route = self.agents.plan(objective)["route"]
        if explicit_steps:
            if len(explicit_steps) > 8:
                raise AutonomousMissionError("Missão autônoma aceita no máximo oito etapas.")
            for step in explicit_steps:
                self.skills.build_intent(step.skill_id, dict(step.arguments))
            return AdaptivePlan("ready", objective, route, tuple(explicit_steps), reason="Plano tipado fornecido e validado.")

        workspace_raw = str(context.get("workspace") or "").strip()
        workspace = Path(workspace_raw).expanduser() if workspace_raw else None
        path = str(context.get("path") or context.get("spreadsheet_path") or "").strip()
        output = str(context.get("output") or context.get("report_path") or "").strip()
        steps: list[SkillMissionStep] = []
        missing: list[str] = []
        agent_id = route["agent_id"]

        if agent_id in {"software.engineering", "devops.platform"}:
            if not workspace_raw:
                missing.append("workspace")
            else:
                steps.extend([
                    SkillMissionStep(skill_id="workspace.inspect", arguments={"workspace": workspace_raw}),
                    SkillMissionStep(skill_id="git.status", arguments={"workspace": workspace_raw}),
                ])
                if workspace and workspace.exists():
                    test_skill = self._project_test_skill(workspace)
                    if test_skill:
                        steps.append(SkillMissionStep(skill_id=test_skill, arguments={"workspace": workspace_raw}))
        elif agent_id == "marketing.growth":
            if not workspace_raw:
                missing.append("workspace")
            else:
                out = output or "oryven-marketing-plan.md"
                steps.append(SkillMissionStep(skill_id="marketing.plan", arguments={
                    "workspace": workspace_raw, "path": out, "objective": objective,
                    "audience": str(context.get("audience") or "A definir pelo usuário"),
                    "channels": list(context.get("channels") or []),
                }))
        elif agent_id in {"data.analytics", "ai.ml"}:
            if not workspace_raw:
                missing.append("workspace")
            if not path:
                missing.append("path")
            if not missing:
                steps.append(SkillMissionStep(skill_id="analytics.analyze", arguments={"workspace": workspace_raw, "path": path}))
        elif agent_id == "finance.analysis":
            if not workspace_raw:
                missing.append("workspace")
            if not path:
                missing.append("path")
            if not missing:
                steps.append(SkillMissionStep(skill_id="finance.workbook.analyze", arguments={"workspace": workspace_raw, "path": path}))
        elif agent_id == "office.productivity":
            if not workspace_raw:
                missing.append("workspace")
            if not path:
                missing.append("path")
            if not output:
                missing.append("output")
            if not missing:
                steps.append(SkillMissionStep(skill_id="office.report.from.xlsx", arguments={
                    "workspace": workspace_raw, "path": path, "output": output,
                    "title": str(context.get("title") or "Relatório Oryven"),
                }))
        else:
            if not workspace_raw:
                missing.append("workspace")
            else:
                steps.append(SkillMissionStep(skill_id="knowledge.organize", arguments={
                    "workspace": workspace_raw, "path": str(context.get("path") or ".")
                }))

        if missing:
            return AdaptivePlan("needs_context", objective, route, tuple(), tuple(sorted(set(missing))),
                                "Contexto essencial ausente; o Oryven não adivinha arquivos ou workspaces.")
        if not steps:
            return AdaptivePlan("needs_steps", objective, route, tuple(), (),
                                "Nenhum template seguro foi encontrado; forneça etapas tipadas ou contexto adicional.")
        for step in steps:
            self.skills.build_intent(step.skill_id, dict(step.arguments))
        return AdaptivePlan("ready", objective, route, tuple(steps), reason="Plano adaptativo local criado com contexto explícito.")


class SupervisedMissionPolicy:
    """Verification and recovery rules. These rules never grant approval."""
    READ_ONLY_PROFESSIONAL = {
        "spreadsheet.analyze", "spreadsheet.xlsx.analyze", "analytics.analyze", "design.assist",
        "database.query", "knowledge.organize", "cad.assets.inspect", "bim.assets.inspect",
        "media.assets.inspect", "ecommerce.catalog.audit", "crm.pipeline.analyze", "logistics.analyze",
        "hr.organize", "finance.workbook.analyze", "support.triage",
    }
    OUTPUT_PROFESSIONAL = {
        "documents.compose", "documents.docx.compose", "datasets.prepare", "maya.assist", "blender.assist",
        "presentation.compose", "presentation.pptx.compose", "pdf.compose", "marketing.plan",
        "operations.sop.compose", "accounting.reconcile.preview", "office.report.from.xlsx",
        "spreadsheet.xlsx.create",
    }

    def automatic_verification(self, intent: ExecutableIntent) -> tuple[bool | None, str]:
        """True/False = machine-verifiable. None = human/visual confirmation still required."""
        if isinstance(intent, WorkActionIntent):
            root = Path(intent.workspace).expanduser()
            if intent.action in {"filesystem.list", "filesystem.read", "terminal.run"}:
                return True, "A ferramenta concluiu sem erro e não exige confirmação visual adicional."
            target = (root / intent.path).resolve(strict=False)
            if intent.action == "filesystem.mkdir":
                return target.is_dir(), "Pasta verificada no filesystem." if target.is_dir() else "Pasta não encontrada após execução."
            if intent.action in {"filesystem.write_text", "filesystem.append_text"}:
                return target.is_file(), "Arquivo verificado no filesystem." if target.is_file() else "Arquivo não encontrado após execução."
        if isinstance(intent, DeveloperActionIntent):
            if intent.action in {"git.push", "deploy.vercel.preview", "deploy.vercel.production"}:
                return None, "Ação externa concluída pela ferramenta, mas requer confirmação humana/externa."
            return True, "Runtime de desenvolvimento concluiu a operação sem erro."
        if isinstance(intent, ProfessionalActionIntent):
            if intent.action in self.READ_ONLY_PROFESSIONAL:
                return True, "Skill analítica/leitura concluída sem erro."
            if intent.action in self.OUTPUT_PROFESSIONAL:
                raw = intent.arguments.get("output") or intent.arguments.get("path")
                if raw:
                    target = (Path(intent.workspace).expanduser() / str(raw)).resolve(strict=False)
                    ok = target.is_file()
                    return ok, "Artefato de saída verificado." if ok else "Artefato esperado não foi encontrado."
            if intent.action in {"office.open.document", "maya.execute", "blender.execute"}:
                return None, "Ação em aplicativo externo requer confirmação visual."
        if isinstance(intent, (WindowVisualSnapshotIntent, WindowUnderstandIntent, WindowListIntent, WindowTreeIntent)):
            return True, "Operação observacional concluída."
        return None, "Esta etapa exige confirmação humana ou percepção adicional."

    def recovery_for(self, intent: ExecutableIntent) -> ExecutableIntent | None:
        """One low-risk diagnostic step. The original failed step is retried only after this step succeeds."""
        if isinstance(intent, (DeveloperActionIntent, WorkActionIntent, ProfessionalActionIntent)):
            workspace = getattr(intent, "workspace", "")
            if workspace:
                return WorkActionIntent(action="filesystem.list", workspace=workspace, path=".")
        return None
