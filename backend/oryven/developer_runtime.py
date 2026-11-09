"""Approved developer operations for the Oryven MVP.

This module intentionally exposes named operations instead of arbitrary shell commands.
Every call is expected to arrive through ApprovalStore as a one-shot exact action.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess

from .models import DeveloperActionIntent


class DeveloperRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class DeveloperResult:
    action: str
    workspace: str
    returncode: int
    stdout: str
    stderr: str

    def as_dict(self):
        return {
            "action": self.action,
            "workspace": self.workspace,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class DeveloperRuntime:
    COMMANDS = {
        "git.status": ("git", "status", "--short", "--branch"),
        "git.diff": ("git", "diff", "--stat"),
        "git.push": ("git", "push"),
        "test.python": ("python", "-m", "pytest", "-q"),
        "test.npm": ("npm", "test", "--", "--runInBand"),
        "test.maven": ("mvn", "test", "-q"),
        "build.npm": ("npm", "run", "build"),
        "build.maven": ("mvn", "package", "-DskipTests"),
        "deploy.vercel.preview": ("vercel", "--yes"),
        "deploy.vercel.production": ("vercel", "--prod", "--yes"),
    }

    def __init__(self, allowed_roots: tuple[Path, ...] = (), timeout_seconds: int = 180):
        self.allowed_roots = tuple(Path(p).expanduser().resolve() for p in allowed_roots)
        self.timeout_seconds = max(10, min(timeout_seconds, 900))

    def _workspace(self, raw: str) -> Path:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise DeveloperRuntimeError("Workspace deve usar caminho absoluto.")
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DeveloperRuntimeError("Workspace não existe ou não pode ser acessado.") from exc
        if not resolved.is_dir():
            raise DeveloperRuntimeError("Workspace precisa ser uma pasta.")
        if self.allowed_roots and not any(resolved == root or root in resolved.parents for root in self.allowed_roots):
            raise DeveloperRuntimeError("Workspace fora das pastas autorizadas do Oryven.")
        return resolved

    @staticmethod
    def _truncate(text: str, limit: int = 12000) -> str:
        text = text or ""
        return text if len(text) <= limit else text[:limit] + "\n...[saida truncada]"

    def inspect(self, workspace: Path) -> DeveloperResult:
        names = []
        try:
            for item in sorted(workspace.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))[:120]:
                names.append(("[dir] " if item.is_dir() else "[file] ") + item.name)
        except OSError as exc:
            raise DeveloperRuntimeError("Não foi possível listar o workspace.") from exc
        return DeveloperResult("workspace.inspect", str(workspace), 0, "\n".join(names), "")

    def execute(self, intent: DeveloperActionIntent) -> dict:
        if not isinstance(intent, DeveloperActionIntent):
            raise DeveloperRuntimeError("Ação de desenvolvimento inválida.")
        workspace = self._workspace(intent.workspace)
        if intent.action == "workspace.inspect":
            return self.inspect(workspace).as_dict()
        command = self.COMMANDS.get(intent.action)
        if command is None:
            raise DeveloperRuntimeError("Ação de desenvolvimento não suportada.")
        executable = shutil.which(command[0])
        if not executable:
            raise DeveloperRuntimeError(f"Ferramenta necessária não encontrada: {command[0]}.")
        argv = [executable, *command[1:]]
        env = os.environ.copy()
        # Prevent interactive credential/password prompts from hanging a desktop agent.
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        env.setdefault("CI", "1")
        try:
            completed = subprocess.run(
                argv,
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                shell=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise DeveloperRuntimeError(f"Ação excedeu {self.timeout_seconds}s e foi encerrada.") from exc
        except OSError as exc:
            raise DeveloperRuntimeError("Falha ao iniciar a ferramenta de desenvolvimento.") from exc
        result = DeveloperResult(
            intent.action,
            str(workspace),
            completed.returncode,
            self._truncate(completed.stdout),
            self._truncate(completed.stderr),
        )
        if completed.returncode != 0:
            raise DeveloperRuntimeError(
                f"{intent.action} terminou com código {completed.returncode}.\n"
                f"{self._truncate(completed.stderr or completed.stdout, 2000)}"
            )
        return result.as_dict()
