"""Dependency-free local intent classifier for Oryven.

The model only proposes a semantic route. Governance still creates a one-shot approval
for the exact executable intent before any tool is called.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import math
import re
import unicodedata

TOKEN = re.compile(r"[a-z0-9_.+-]+", re.I)


def _tokens(text: str) -> list[str]:
    text = "".join(c for c in unicodedata.normalize("NFD", text.casefold()) if unicodedata.category(c) != "Mn")
    return TOKEN.findall(text)


@dataclass(frozen=True)
class Route:
    label: str
    confidence: float
    source: str = "local-nb"


class LocalIntentRouter:
    def __init__(self, model_path: Path):
        self.model_path = Path(model_path)
        self.model = None
        if self.model_path.is_file():
            try:
                self.model = json.loads(self.model_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                self.model = None

    @property
    def ready(self) -> bool:
        return bool(self.model and self.model.get("classes"))

    def predict(self, text: str) -> Route | None:
        if not self.ready or not text.strip():
            return None
        tokens = _tokens(text)
        if not tokens:
            return None
        scores: dict[str, float] = {}
        vocab_size = max(1, len(self.model.get("vocabulary", [])))
        for label in self.model["classes"]:
            cls = self.model["stats"][label]
            score = math.log(max(cls["prior"], 1e-12))
            denom = cls["token_total"] + vocab_size
            counts = cls["token_counts"]
            for token in tokens:
                score += math.log((counts.get(token, 0) + 1) / denom)
            scores[label] = score
        peak = max(scores.values())
        exp = {k: math.exp(v - peak) for k, v in scores.items()}
        total = sum(exp.values()) or 1.0
        probs = {k: v / total for k, v in exp.items()}
        label = max(probs, key=probs.get)
        return Route(label=label, confidence=round(probs[label], 4))
