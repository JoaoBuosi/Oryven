"""Governed universal work runtime for Oryven.

The runtime exposes exact, named operations for files and supervised terminal commands.
It deliberately avoids shell=True and confines filesystem operations to approved roots.
Every mutating or command action is expected to arrive through ApprovalStore.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

from .models import WorkActionIntent


class WorkRuntimeError(ValueError):
    pass


@dataclass(frozen=True)
class WorkResult:
    action: str
    workspace: str
    target: str
    data: dict

    def as_dict(self) -> dict:
        return {
            "action": self.action,
            "workspace": self.workspace,
            "target": self.target,
            **self.data,
        }


class WorkRuntime:
    DEFAULT_EXECUTABLES = frozenset({
        "git", "python", "python3", "py", "node", "npm", "npx", "mvn",
        "java", "javac", "gradle", "docker", "vercel",
    })

    def __init__(self, allowed_roots: tuple[Path, ...] = (), timeout_seconds: int = 120,
                 terminal_executables: tuple[str, ...] = ()):
        self.allowed_roots = tuple(Path(p).expanduser().resolve() for p in allowed_roots)
        self.timeout_seconds = max(5, min(int(timeout_seconds), 900))
        configured = {v.strip().casefold() for v in terminal_executables if v.strip()}
        self.terminal_executables = frozenset(configured) if configured else self.DEFAULT_EXECUTABLES

    def _workspace(self, raw: str) -> Path:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            raise WorkRuntimeError("Workspace deve usar caminho absoluto.")
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise WorkRuntimeError("Workspace não existe ou não pode ser acessado.") from exc
        if not resolved.is_dir():
            raise WorkRuntimeError("Workspace precisa ser uma pasta.")
        if self.allowed_roots and not any(resolved == root or root in resolved.parents for root in self.allowed_roots):
            raise WorkRuntimeError("Workspace fora das pastas autorizadas do Oryven.")
        return resolved

    @staticmethod
    def _inside(base: Path, candidate: Path) -> bool:
        return candidate == base or base in candidate.parents

    def _target(self, workspace: Path, raw: str, *, must_exist: bool | None = None) -> Path:
        raw = raw or "."
        rel = Path(raw)
        if rel.is_absolute():
            raise WorkRuntimeError("Use caminho relativo ao workspace para arquivos.")
        try:
            candidate = (workspace / rel).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            raise WorkRuntimeError("Caminho inválido.") from exc
        if not self._inside(workspace, candidate):
            raise WorkRuntimeError("Caminho tenta sair do workspace autorizado.")
        if must_exist is True and not candidate.exists():
            raise WorkRuntimeError("Arquivo ou pasta não encontrado.")
        if must_exist is False and candidate.exists():
            raise WorkRuntimeError("Destino já existe.")
        return candidate

    @staticmethod
    def _truncate(text: str, limit: int = 16000) -> str:
        text = text or ""
        return text if len(text) <= limit else text[:limit] + "\n...[saída truncada]"

    def _list(self, workspace: Path, target: Path) -> dict:
        if not target.is_dir():
            raise WorkRuntimeError("filesystem.list exige uma pasta.")
        rows = []
        try:
            for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold()))[:200]:
                stat = item.stat()
                rows.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": None if item.is_dir() else stat.st_size,
                })
        except OSError as exc:
            raise WorkRuntimeError("Não foi possível listar a pasta.") from exc
        return WorkResult("filesystem.list", str(workspace), str(target.relative_to(workspace)), {"entries": rows}).as_dict()

    def _read(self, workspace: Path, target: Path) -> dict:
        if not target.is_file():
            raise WorkRuntimeError("filesystem.read exige um arquivo.")
        try:
            size = target.stat().st_size
            if size > 1_000_000:
                raise WorkRuntimeError("Arquivo excede o limite de leitura do MVP (1 MB).")
            data = target.read_bytes()
            if b"\x00" in data:
                raise WorkRuntimeError("Arquivo binário não é aceito por filesystem.read.")
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise WorkRuntimeError("Arquivo não está em UTF-8.") from exc
        except OSError as exc:
            raise WorkRuntimeError("Não foi possível ler o arquivo.") from exc
        return WorkResult("filesystem.read", str(workspace), str(target.relative_to(workspace)), {
            "content": text,
            "bytes": size,
        }).as_dict()

    def _write(self, intent: WorkActionIntent, workspace: Path, target: Path, append: bool) -> dict:
        if target.exists() and target.is_dir():
            raise WorkRuntimeError("Destino é uma pasta, não um arquivo.")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            content = intent.content or ""
            if append:
                with target.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
            else:
                # Same-directory atomic replace where supported.
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", delete=False,
                                                 dir=target.parent, prefix=".oryven-", suffix=".tmp") as fh:
                    fh.write(content)
                    temp_name = fh.name
                os.replace(temp_name, target)
        except OSError as exc:
            raise WorkRuntimeError("Não foi possível gravar o arquivo.") from exc
        return WorkResult(intent.action, str(workspace), str(target.relative_to(workspace)), {
            "bytes_written": len((intent.content or "").encode("utf-8")),
            "mode": "append" if append else "replace",
        }).as_dict()

    def _mkdir(self, workspace: Path, target: Path) -> dict:
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkRuntimeError("Não foi possível criar a pasta.") from exc
        return WorkResult("filesystem.mkdir", str(workspace), str(target.relative_to(workspace)), {"created": True}).as_dict()

    def _terminal(self, intent: WorkActionIntent, workspace: Path) -> dict:
        executable_name = (intent.executable or "").strip()
        if not executable_name or Path(executable_name).name != executable_name:
            raise WorkRuntimeError("Informe somente o nome do executável permitido.")
        normalized = executable_name.casefold()
        if normalized.endswith(".exe"):
            normalized = normalized[:-4]
        if normalized not in self.terminal_executables:
            raise WorkRuntimeError("Executável não permitido pelo terminal supervisionado.")
        executable = shutil.which(executable_name) or shutil.which(normalized)
        if not executable:
            raise WorkRuntimeError(f"Executável não encontrado: {executable_name}.")
        args = list(intent.args or [])
        if len(args) > 32 or any(len(arg) > 500 or "\x00" in arg for arg in args):
            raise WorkRuntimeError("Argumentos do terminal excedem os limites do MVP.")
        env = os.environ.copy()
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        env.setdefault("CI", "1")
        try:
            completed = subprocess.run(
                [executable, *args], cwd=workspace, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=self.timeout_seconds,
                shell=False, env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkRuntimeError(f"Comando excedeu {self.timeout_seconds}s e foi encerrado.") from exc
        except OSError as exc:
            raise WorkRuntimeError("Falha ao iniciar o comando supervisionado.") from exc
        result = WorkResult("terminal.run", str(workspace), executable_name, {
            "argv": [executable_name, *args],
            "returncode": completed.returncode,
            "stdout": self._truncate(completed.stdout),
            "stderr": self._truncate(completed.stderr),
        }).as_dict()
        if completed.returncode != 0:
            raise WorkRuntimeError(
                f"Comando terminou com código {completed.returncode}.\n"
                f"{self._truncate(completed.stderr or completed.stdout, 2000)}"
            )
        return result

    def validate(self, intent: WorkActionIntent) -> None:
        workspace = self._workspace(intent.workspace)
        if intent.action == "terminal.run":
            if not intent.executable:
                raise WorkRuntimeError("terminal.run exige executable.")
            return
        target = self._target(workspace, intent.path, must_exist=True if intent.action in {"filesystem.list", "filesystem.read"} else None)
        if intent.action in {"filesystem.write_text", "filesystem.append_text"} and intent.content is None:
            raise WorkRuntimeError(f"{intent.action} exige content.")
        if intent.action == "filesystem.mkdir" and target.exists() and not target.is_dir():
            raise WorkRuntimeError("Já existe um arquivo nesse destino.")

    def execute(self, intent: WorkActionIntent) -> dict:
        if not isinstance(intent, WorkActionIntent):
            raise WorkRuntimeError("Ação profissional inválida.")
        workspace = self._workspace(intent.workspace)
        if intent.action == "terminal.run":
            return self._terminal(intent, workspace)
        target = self._target(workspace, intent.path, must_exist=True if intent.action in {"filesystem.list", "filesystem.read"} else None)
        if intent.action == "filesystem.list":
            return self._list(workspace, target)
        if intent.action == "filesystem.read":
            return self._read(workspace, target)
        if intent.action == "filesystem.write_text":
            return self._write(intent, workspace, target, append=False)
        if intent.action == "filesystem.append_text":
            return self._write(intent, workspace, target, append=True)
        if intent.action == "filesystem.mkdir":
            return self._mkdir(workspace, target)
        raise WorkRuntimeError("Ação profissional não suportada.")
