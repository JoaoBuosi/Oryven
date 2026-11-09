"""Official end-to-end Functional MVP journeys for Oryven 0.18.

These flows are product contracts, not hidden privileges. They only build typed plans;
all execution still goes through MissionStore + ApprovalStore one action at a time.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import SkillMissionStep


class FunctionalMVPError(ValueError):
    pass


@dataclass(frozen=True)
class FunctionalFlow:
    id: str
    name: str
    description: str
    category: str
    requires: tuple[str, ...]
    success: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "requires": list(self.requires),
            "success": self.success,
        }


FLOWS = (
    FunctionalFlow(
        "development.validate",
        "Development",
        "Inspeciona um projeto de software e executa a suíte de testes compatível detectada.",
        "development",
        ("active_project", "workspace"),
        "Workspace inspecionado e testes concluídos sem erro.",
    ),
    FunctionalFlow(
        "office.report",
        "Office & Data",
        "Analisa uma planilha XLSX e gera um relatório DOCX verificável.",
        "office",
        ("active_project", "spreadsheet_path", "report_path"),
        "Relatório DOCX criado a partir da análise da planilha.",
    ),
    FunctionalFlow(
        "research.organize",
        "Research & Knowledge",
        "Organiza o conhecimento do workspace e gera um inventário estruturado sem copiar segredos.",
        "research",
        ("active_project",),
        "Conhecimento local indexado e retornado como resultado estruturado.",
    ),
    FunctionalFlow(
        "computer.workspace",
        "Computer Assistant",
        "Lista e lê arquivos autorizados do projeto para executar tarefas locais de produtividade.",
        "computer",
        ("active_project",),
        "Workspace acessado dentro dos limites autorizados, sem sair do projeto ativo.",
    ),
    FunctionalFlow(
        "professional.multi_app",
        "Professional Multi-App",
        "Gera um relatório a partir de XLSX e o abre no aplicativo associado do Windows.",
        "multi_app",
        ("active_project", "spreadsheet_path", "report_path"),
        "Relatório gerado e abertura do artefato proposta no aplicativo associado.",
    ),
)


class FunctionalMVPPlanner:
    def __init__(self, skill_catalog):
        self.skill_catalog = skill_catalog

    @staticmethod
    def _flow(flow_id: str) -> FunctionalFlow:
        flow = next((item for item in FLOWS if item.id == flow_id), None)
        if flow is None:
            raise FunctionalMVPError("Fluxo Functional MVP desconhecido.")
        return flow

    @staticmethod
    def _test_skill(workspace: Path) -> str | None:
        if (workspace / "pom.xml").exists():
            return "test.maven"
        if (workspace / "package.json").exists():
            return "test.npm"
        if any((workspace / marker).exists() for marker in ("pyproject.toml", "pytest.ini", "setup.cfg", "requirements.txt")):
            return "test.python"
        return None

    def plan(self, flow_id: str, *, active_project: dict | None, context: dict[str, Any] | None = None) -> dict[str, Any]:
        flow = self._flow(flow_id)
        context = dict(context or {})
        if active_project is None:
            return self._needs(flow, ["active_project"])

        workspace = str(active_project.get("workspace") or "").strip()
        if not workspace:
            return self._needs(flow, ["workspace"])
        context.setdefault("workspace", workspace)
        root = Path(workspace).expanduser()
        steps: list[SkillMissionStep] = []
        missing: list[str] = []

        if flow_id == "development.validate":
            steps.append(SkillMissionStep(skill_id="workspace.inspect", arguments={"workspace": workspace}))
            if (root / ".git").exists():
                steps.append(SkillMissionStep(skill_id="git.status", arguments={"workspace": workspace}))
            test_skill = self._test_skill(root)
            if test_skill:
                steps.append(SkillMissionStep(skill_id=test_skill, arguments={"workspace": workspace}))
            else:
                missing.append("test_runner")

        elif flow_id == "office.report":
            source = str(context.get("spreadsheet_path") or context.get("path") or "").strip()
            output = str(context.get("report_path") or context.get("output") or "").strip()
            if not source:
                missing.append("spreadsheet_path")
            if not output:
                missing.append("report_path")
            if not missing:
                steps.append(SkillMissionStep(skill_id="office.report.from.xlsx", arguments={
                    "workspace": workspace, "path": source, "output": output,
                    "title": str(context.get("title") or "Relatório Oryven"),
                }))

        elif flow_id == "research.organize":
            steps.append(SkillMissionStep(skill_id="knowledge.organize", arguments={
                "workspace": workspace, "path": str(context.get("path") or ".")
            }))

        elif flow_id == "computer.workspace":
            path = str(context.get("path") or ".")
            steps.append(SkillMissionStep(skill_id="filesystem.list", arguments={"workspace": workspace, "path": path}))
            read_path = str(context.get("read_path") or "").strip()
            if read_path:
                steps.append(SkillMissionStep(skill_id="filesystem.read", arguments={"workspace": workspace, "path": read_path}))

        elif flow_id == "professional.multi_app":
            source = str(context.get("spreadsheet_path") or context.get("path") or "").strip()
            output = str(context.get("report_path") or context.get("output") or "").strip()
            if not source:
                missing.append("spreadsheet_path")
            if not output:
                missing.append("report_path")
            if not missing:
                steps.extend([
                    SkillMissionStep(skill_id="office.report.from.xlsx", arguments={
                        "workspace": workspace, "path": source, "output": output,
                        "title": str(context.get("title") or "Relatório Oryven"),
                    }),
                    SkillMissionStep(skill_id="office.open.document", arguments={
                        "workspace": workspace, "path": output,
                    }),
                ])

        if missing:
            return self._needs(flow, missing)
        if not steps:
            return self._needs(flow, ["supported_steps"])
        for step in steps:
            self.skill_catalog.build_intent(step.skill_id, dict(step.arguments))
        return {
            "status": "ready",
            "flow": flow.as_dict(),
            "steps": [step.model_dump() for step in steps],
            "permissions_granted": False,
            "note": "Plano Functional MVP validado localmente; nenhuma etapa foi autorizada.",
        }

    @staticmethod
    def _needs(flow: FunctionalFlow, missing: list[str]) -> dict[str, Any]:
        return {
            "status": "needs_context",
            "flow": flow.as_dict(),
            "steps": [],
            "missing": sorted(set(missing)),
            "permissions_granted": False,
            "note": "Contexto obrigatório ausente; o Oryven não adivinha arquivos, workspaces ou ferramentas.",
        }

    def list(self) -> list[dict[str, Any]]:
        return [flow.as_dict() for flow in FLOWS]
