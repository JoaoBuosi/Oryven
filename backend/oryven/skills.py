"""Packaged Oryven skill catalog and safe intent construction.

Skill manifests are declarative. Building an intent never executes it and never grants
permission; the returned intent must still pass through ApprovalStore.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import (
    AppLaunchIntent, BunoChatIntent, BrowserInspectIntent, DeveloperActionIntent,
    SearchIntent, WindowListIntent, WorkActionIntent, ProfessionalActionIntent,
)


class SkillError(ValueError):
    pass


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z0-9_.-]+$")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    name: str = Field(min_length=2)
    description: str
    permissions: list[str]
    inputs: dict[str, str]
    outputs: dict[str, str] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    success_criteria: list[str]
    family: str = "general"
    executable: bool = False
    risk: str = "low"
    stage: str = "mvp"


class SkillCatalog:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self._manifests: dict[str, SkillManifest] = {}
        for path in sorted(self.directory.glob("*.json")):
            try:
                manifest = SkillManifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError, ValidationError):
                continue
            self._manifests[manifest.id] = manifest

    def list(self) -> list[dict]:
        return [self._manifests[key].model_dump() for key in sorted(self._manifests)]

    def get(self, skill_id: str) -> SkillManifest:
        manifest = self._manifests.get(skill_id)
        if manifest is None:
            raise SkillError("Skill não encontrada no pacote instalado.")
        return manifest

    def recommend(self, tool_families: list[str], limit: int = 12) -> list[dict]:
        wanted = {value.casefold() for value in tool_families}
        chosen = []
        for manifest in self._manifests.values():
            tags = {manifest.family.casefold(), *(tool.casefold() for tool in manifest.tools)}
            if wanted.intersection(tags):
                chosen.append(manifest)
        chosen.sort(key=lambda item: (not item.executable, item.risk != "low", item.id))
        return [item.model_dump() for item in chosen[:max(1, min(limit, 50))]]

    @staticmethod
    def _only(arguments: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
        unknown = set(arguments) - allowed
        if unknown:
            raise SkillError("Argumentos desconhecidos para a skill: " + ", ".join(sorted(unknown)))
        return arguments

    def build_intent(self, skill_id: str, arguments: dict[str, Any]):
        manifest = self.get(skill_id)
        if not manifest.executable:
            raise SkillError("Esta skill é apenas declarativa nesta versão e não pode executar ações.")
        try:
            if skill_id in {
                "filesystem.list", "filesystem.read", "filesystem.write_text",
                "filesystem.append_text", "filesystem.mkdir", "terminal.run",
            }:
                data = self._only(arguments, {"workspace", "path", "content", "executable", "args"})
                return WorkActionIntent(action=skill_id, **data)
            if skill_id in {
                "workspace.inspect", "git.status", "git.diff", "git.push", "test.python",
                "test.npm", "test.maven", "build.npm", "build.maven",
                "deploy.vercel.preview", "deploy.vercel.production",
            }:
                data = self._only(arguments, {"workspace"})
                return DeveloperActionIntent(action=skill_id, **data)
            if skill_id == "browser.search":
                return SearchIntent(**self._only(arguments, {"query"}))
            if skill_id == "browser.inspect":
                return BrowserInspectIntent(**self._only(arguments, {"url"}))
            if skill_id == "app.launch":
                return AppLaunchIntent(**self._only(arguments, {"app_id"}))
            if skill_id == "computer.windows.list":
                self._only(arguments, set())
                return WindowListIntent()
            if skill_id == "buno.chat":
                return BunoChatIntent(**self._only(arguments, {"message"}))
            if skill_id in {
                "documents.compose", "documents.docx.compose", "spreadsheet.analyze",
                "spreadsheet.xlsx.create", "spreadsheet.xlsx.analyze", "analytics.analyze",
                "datasets.prepare", "design.assist", "database.query", "knowledge.organize",
                "maya.assist", "maya.execute", "blender.assist", "blender.execute",
                "cad.assets.inspect", "bim.assets.inspect", "media.assets.inspect",
                "presentation.compose", "presentation.pptx.compose", "pdf.compose",
                "marketing.plan", "ecommerce.catalog.audit", "crm.pipeline.analyze",
                "operations.sop.compose", "logistics.analyze", "hr.organize",
                "finance.workbook.analyze", "accounting.reconcile.preview", "support.triage", "office.report.from.xlsx", "office.open.document",
            }:
                data = self._only(arguments, {
                    "workspace", "path", "content", "output", "query", "script", "language",
                    "title", "sections", "headers", "rows", "sheet", "sheets", "columns",
                    "objective", "audience", "channels", "items", "currency", "threshold",
                    "executable", "args", "format", "subject", "status_column", "amount_column",
                    "date_column", "category_column", "priority_column", "owner_column",
                })
                workspace = data.pop("workspace", None)
                if not workspace:
                    raise SkillError("A skill profissional exige workspace.")
                return ProfessionalActionIntent(action=skill_id, workspace=workspace, arguments=data)
        except (TypeError, ValidationError) as exc:
            raise SkillError("Argumentos inválidos para a skill selecionada.") from exc
        raise SkillError("A skill ainda não possui adaptador executável nesta versão.")


def list_skills(directory: Path) -> list[dict]:
    return SkillCatalog(directory).list()
