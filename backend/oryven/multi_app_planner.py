"""Deterministic multi-app mission templates for Oryven 0.14.2.

The planner creates typed steps; it never grants permissions. Ambiguous file context is
returned as missing input instead of guessing which user file to open.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any


class MultiAppPlannerError(ValueError):
    pass


class MultiAppPlanner:
    @staticmethod
    def recognizes_excel_report(text: str) -> bool:
        folded = text.casefold()
        return ("excel" in folded or "planilha" in folded or "xlsx" in folded) and ("word" in folded or "relat" in folded)

    def plan(self, objective: str, *, workspace: str | None = None, spreadsheet_path: str | None = None,
             report_path: str | None = None) -> dict[str, Any]:
        if not self.recognizes_excel_report(objective):
            raise MultiAppPlannerError("Ainda não há template multi-app seguro para este objetivo.")
        missing = []
        if not workspace: missing.append("workspace")
        if not spreadsheet_path: missing.append("spreadsheet_path")
        if missing:
            return {"status": "needs_context", "objective": objective, "missing": missing, "permissions_granted": False, "steps": []}
        report_path = report_path or "oryven-report.docx"
        if Path(spreadsheet_path).suffix.lower() != ".xlsx":
            raise MultiAppPlannerError("O fluxo Excel→Word exige um arquivo .xlsx.")
        if Path(report_path).suffix.lower() != ".docx":
            raise MultiAppPlannerError("O relatório do fluxo Excel→Word deve ser .docx.")
        return {
            "status": "ready",
            "objective": objective,
            "permissions_granted": False,
            "steps": [
                {"skill_id": "office.open.document", "arguments": {"workspace": workspace, "path": spreadsheet_path}},
                {"skill_id": "office.report.from.xlsx", "arguments": {
                    "workspace": workspace, "path": spreadsheet_path, "output": report_path,
                    "title": "Relatório gerado pelo Oryven",
                }},
                {"skill_id": "office.open.document", "arguments": {"workspace": workspace, "path": report_path}},
            ],
            "note": "Cada etapa continua sujeita a autorização e verificação independente.",
        }
