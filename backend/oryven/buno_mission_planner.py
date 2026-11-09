"""Buno AI mission planning with strict Oryven-side validation.

The Buno model is a proposer, never an executor. Model output is treated as untrusted
JSON and must pass strict schemas plus the installed skill catalog before a mission can
be created. No permission is granted by planning or correction.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import SkillMissionStep
from .professional_agents import ProfessionalAgentRegistry
from .skills import SkillCatalog, SkillError


class BunoMissionPlannerError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposedStep(_Strict):
    skill_id: str = Field(min_length=2, max_length=120)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ProposedPlan(_Strict):
    agent_id: str = Field(min_length=2, max_length=100)
    rationale: str = Field(default="", max_length=1200)
    steps: list[ProposedStep] = Field(min_length=1, max_length=8)


class ProposedRecovery(_Strict):
    rationale: str = Field(default="", max_length=800)
    step: ProposedStep


@dataclass(frozen=True)
class ValidatedAIPlan:
    objective: str
    agent: dict
    steps: tuple[SkillMissionStep, ...]
    rationale: str
    corrected: bool = False

    def as_dict(self) -> dict:
        return {
            "status": "ready",
            "objective": self.objective,
            "agent": self.agent,
            "steps": [s.model_dump() for s in self.steps],
            "rationale": self.rationale,
            "planner": "buno-ai",
            "corrected": self.corrected,
            "permissions_granted": False,
        }


def _parse_json_object(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or not raw.strip():
        raise BunoMissionPlannerError("Buno não retornou um plano JSON.")
    text = raw.strip()
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    elif text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BunoMissionPlannerError("Buno retornou um plano que não é JSON estrito.") from exc
    if not isinstance(value, dict):
        raise BunoMissionPlannerError("O plano Buno precisa ser um objeto JSON.")
    return value


class BunoAIMissionPlanner:
    def __init__(self, agents: ProfessionalAgentRegistry, skills: SkillCatalog):
        self.agents = agents
        self.skills = skills

    SAFE_CONTEXT_KEYS = {
        "workspace", "path", "spreadsheet_path", "report_path", "output", "title",
        "audience", "channels", "app_name", "language", "format", "objective_hint",
        "active_project_id", "project_name", "project_description", "memory_notes",
    }

    @classmethod
    def _safe_context(cls, context: dict | None) -> dict:
        safe: dict[str, Any] = {}
        for key, value in dict(context or {}).items():
            if key not in cls.SAFE_CONTEXT_KEYS:
                continue
            if isinstance(value, str):
                safe[key] = value[:1000]
            elif isinstance(value, (int, float, bool)) or value is None:
                safe[key] = value
            elif isinstance(value, list):
                safe[key] = [str(item)[:200] for item in value[:20]]
        return safe

    def _allowed_skills(self, objective: str, agent_id: str | None = None) -> tuple[dict, list[dict]]:
        planned = self.agents.plan(objective, agent_id)
        agent = planned["agent"]
        recommended = self.skills.recommend(planned["recommended_tool_families"], limit=30)
        executable = [m for m in recommended if m.get("executable")]
        # Always include safe universal/work/developer skills so the model can bridge domains.
        universal_prefixes = ("filesystem.", "workspace.", "git.", "test.", "build.", "terminal.", "browser.", "app.", "computer.")
        known = {m["id"] for m in executable}
        for manifest in self.skills.list():
            if manifest.get("executable") and manifest["id"].startswith(universal_prefixes) and manifest["id"] not in known:
                executable.append(manifest); known.add(manifest["id"])
        executable.sort(key=lambda m: m["id"])
        return agent, executable[:40]

    @staticmethod
    def _catalog_payload(manifests: list[dict]) -> list[dict]:
        return [{
            "id": m["id"], "inputs": m.get("inputs", {}), "risk": m.get("risk", "low"),
            "permissions": m.get("permissions", []), "description": m.get("description", "")[:220],
        } for m in manifests]

    def _prompt(self, objective: str, context: dict, agent: dict, manifests: list[dict], max_steps: int,
                correction_error: str = "") -> str:
        payload = {
            "task": "Create a supervised Oryven mission plan",
            "objective": objective,
            "context": context,
            "selected_agent": {"id": agent["id"], "name": agent["name"], "sector": agent["sector"]},
            "allowed_skills": self._catalog_payload(manifests),
            "max_steps": max_steps,
            "rules": [
                "Return JSON only; no markdown or prose outside JSON.",
                "Use only skill IDs in allowed_skills.",
                "Never invent paths, credentials, handles, app IDs or files that are absent from context.",
                "Do not add approval, permission, execute, auto_approve or bypass fields.",
                "Prefer the minimum number of steps needed.",
                "Every side effect will be separately authorized by Oryven; do not claim permission.",
            ],
            "response_schema": {
                "agent_id": agent["id"],
                "rationale": "short explanation",
                "steps": [{"skill_id": "allowed.skill", "arguments": {}}],
            },
        }
        if correction_error:
            payload["previous_plan_error"] = correction_error[:1000]
            payload["rules"].append("Correct the prior validation error and return a complete replacement plan.")
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _resolve_bindings(value: Any, bindings: dict[str, str] | None):
        if not bindings:
            return value
        if isinstance(value, str):
            return bindings.get(value, value)
        if isinstance(value, list):
            return [BunoAIMissionPlanner._resolve_bindings(v, bindings) for v in value]
        if isinstance(value, dict):
            return {k: BunoAIMissionPlanner._resolve_bindings(v, bindings) for k, v in value.items()}
        return value

    def _validate(self, objective: str, raw: str, max_steps: int, allowed_ids: set[str], expected_agent_id: str, bindings: dict[str, str] | None = None) -> ValidatedAIPlan:
        try:
            proposed = ProposedPlan.model_validate(_parse_json_object(raw))
        except ValidationError as exc:
            raise BunoMissionPlannerError("Plano Buno violou o schema estrito.") from exc
        if len(proposed.steps) > max_steps:
            raise BunoMissionPlannerError("Plano Buno excedeu o limite de etapas.")
        if proposed.agent_id != expected_agent_id:
            raise BunoMissionPlannerError("Buno tentou trocar o agente roteado pelo Oryven.")
        try:
            agent_manifest = self.agents.get(proposed.agent_id)
            agent = {
                "agent_id": agent_manifest["id"],
                "name": agent_manifest["name"],
                "sector": agent_manifest["sector"],
                "confidence": 1.0,
                "matched_terms": [],
                "reason": "Agente proposto pela Buno AI e validado contra o catálogo local.",
            }
        except KeyError as exc:
            raise BunoMissionPlannerError("Buno selecionou um agente inexistente.") from exc
        steps: list[SkillMissionStep] = []
        for item in proposed.steps:
            if item.skill_id not in allowed_ids:
                raise BunoMissionPlannerError(f"Buno selecionou skill fora do catálogo permitido: {item.skill_id}.")
            try:
                # Catalog validation rejects unknown argument names and non-executable skills.
                resolved_args = self._resolve_bindings(dict(item.arguments), bindings)
                self.skills.build_intent(item.skill_id, resolved_args)
            except SkillError as exc:
                raise BunoMissionPlannerError(f"Skill inválida no plano Buno: {item.skill_id}: {exc}") from exc
            steps.append(SkillMissionStep(skill_id=item.skill_id, arguments=resolved_args))
        return ValidatedAIPlan(objective, agent, tuple(steps), proposed.rationale)

    def plan(self, bridge, objective: str, context: dict | None = None, max_steps: int = 8, bindings: dict[str, str] | None = None) -> ValidatedAIPlan:
        max_steps = max(1, min(int(max_steps), 8))
        context = self._safe_context(context)
        routed = self.agents.plan(objective)
        agent, manifests = self._allowed_skills(objective, routed["route"]["agent_id"])
        allowed = {m["id"] for m in manifests}
        prompt = self._prompt(objective, context, agent, manifests, max_steps)
        raw = bridge.plan_json(prompt)
        try:
            return self._validate(objective, raw, max_steps, allowed, agent["id"], bindings)
        except BunoMissionPlannerError as first:
            # One bounded model correction. The corrected output is validated from scratch.
            correction_prompt = self._prompt(objective, context, agent, manifests, max_steps, str(first))
            corrected_raw = bridge.plan_json(correction_prompt)
            plan = self._validate(objective, corrected_raw, max_steps, allowed, agent["id"], bindings)
            return ValidatedAIPlan(plan.objective, plan.agent, plan.steps, plan.rationale, corrected=True)

    def recovery_step(self, bridge, objective: str, failed_skill: str, failed_arguments: dict,
                      error_summary: str, context: dict | None = None, bindings: dict[str, str] | None = None) -> SkillMissionStep:
        context = self._safe_context(context)
        routed = self.agents.plan(objective)
        agent, manifests = self._allowed_skills(objective, routed["route"]["agent_id"])
        allowed = {m["id"] for m in manifests}
        safe_failed = {}
        for key in ("workspace", "path", "executable", "action"):
            if key in failed_arguments and failed_arguments[key] is not None:
                safe_failed[key] = str(failed_arguments[key])[:500]
        if isinstance(failed_arguments.get("args"), list):
            safe_failed["arg_count"] = len(failed_arguments["args"])
        payload = {
            "task": "Propose exactly one supervised diagnostic/recovery step for a failed Oryven mission step",
            "objective": objective,
            "context": context,
            "failed_step": {"skill_id": failed_skill, "arguments": safe_failed, "error": error_summary[:700]},
            "allowed_skills": self._catalog_payload(manifests),
            "rules": [
                "Return JSON only.", "Propose one step only.", "Use only allowed skills.",
                "Never invent credentials or paths absent from context/failed step.",
                "Prefer read-only diagnostic actions.", "Do not include permission or approval fields.",
            ],
            "response_schema": {"rationale": "short", "step": {"skill_id": "allowed.skill", "arguments": {}}},
        }
        raw = bridge.plan_json(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        try:
            proposed = ProposedRecovery.model_validate(_parse_json_object(raw))
        except ValidationError as exc:
            raise BunoMissionPlannerError("Recuperação Buno violou o schema estrito.") from exc
        if proposed.step.skill_id not in allowed:
            raise BunoMissionPlannerError("Recuperação Buno selecionou skill fora do catálogo permitido.")
        try:
            resolved_args = self._resolve_bindings(dict(proposed.step.arguments), bindings)
            self.skills.build_intent(proposed.step.skill_id, resolved_args)
        except SkillError as exc:
            raise BunoMissionPlannerError("Recuperação Buno contém argumentos inválidos.") from exc
        return SkillMissionStep(skill_id=proposed.step.skill_id, arguments=resolved_args)
