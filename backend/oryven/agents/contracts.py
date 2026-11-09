"""Typed boundaries for future agent providers; not an execution engine."""
from dataclasses import dataclass
from typing import Protocol, Any


@dataclass(frozen=True)
class ProposedStep:
    skill_id: str
    arguments: dict[str, Any]
    justification: str


class Planner(Protocol):
    def propose(self, instruction: str) -> list[ProposedStep]: ...


class TextModel(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...

# Crucial: proposals are never permissions; only the governance executor may act.
