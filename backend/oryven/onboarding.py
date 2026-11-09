"""Per-user onboarding state."""
from __future__ import annotations
import json
from pathlib import Path


class OnboardingState:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def get(self) -> dict:
        default = {
            "completed": False,
            "assistant_named": False,
            "voice_configured": False,
            "workspace_configured": False,
            "permissions_reviewed": False,
        }
        if not self.path.exists():
            return default
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            for key in default:
                if key in raw:
                    default[key] = bool(raw[key])
        except Exception:
            pass
        default["completed"] = all(default[k] for k in ("assistant_named", "voice_configured", "workspace_configured", "permissions_reviewed"))
        return default

    def update(self, **patch) -> dict:
        state = self.get()
        for key in ("assistant_named", "voice_configured", "workspace_configured", "permissions_reviewed"):
            if key in patch and patch[key] is not None:
                state[key] = bool(patch[key])
        state["completed"] = all(state[k] for k in ("assistant_named", "voice_configured", "workspace_configured", "permissions_reviewed"))
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return state
