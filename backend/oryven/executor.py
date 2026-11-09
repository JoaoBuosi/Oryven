"""Tiny allowlisted executors. No arbitrary URL, shell, or file operations."""
from pathlib import Path
import os
import subprocess
import sys
import webbrowser
from .models import SearchIntent, AppLaunchIntent
from .governance import ApprovalStore


class ExecutionError(Exception):
    pass


class BrowserExecutor:
    def __init__(self, opener=None):
        self.opener = opener or webbrowser.open

    def execute(self, intent: SearchIntent) -> str:
        if not isinstance(intent, SearchIntent):
            raise ExecutionError("Ferramenta não autorizada para este MVP.")
        url = ApprovalStore.target_for(intent)
        try:
            launched = self.opener(url, new=2)
        except Exception as exc:
            raise ExecutionError("O sistema não conseguiu solicitar a abertura do navegador.") from exc
        if launched is False:
            raise ExecutionError("O navegador não confirmou o recebimento da solicitação de abertura.")
        return "Enviei a pesquisa ao navegador. Não consigo confirmar o carregamento completo da página."


class WindowsAppExecutor:
    """Only known Windows utilities, with fixed absolute executable paths."""
    BINARIES = {"notepad": "notepad.exe", "calculator": "calc.exe", "explorer": "explorer.exe"}

    def __init__(self, *, launcher=None, windows_dir: Path | None = None, platform: str | None = None):
        self.launcher = launcher or subprocess.Popen
        self.windows_dir = windows_dir or Path(os.environ.get("WINDIR", r"C:\Windows"))
        self.platform = platform or sys.platform

    def execute(self, intent: AppLaunchIntent) -> str:
        if not isinstance(intent, AppLaunchIntent) or intent.app_id not in self.BINARIES:
            raise ExecutionError("Aplicativo não permitido.")
        if self.platform != "win32":
            raise ExecutionError("Abertura de aplicativos suportada apenas no Windows.")
        binary = (self.windows_dir / "System32" / self.BINARIES[intent.app_id]).resolve()
        if not binary.is_file():
            raise ExecutionError("Aplicativo do Windows não encontrado no caminho esperado.")
        try:
            self.launcher([str(binary)], shell=False, close_fds=True)
        except (OSError, ValueError) as exc:
            raise ExecutionError("Não consegui iniciar o aplicativo permitido.") from exc
        return f"Solicitei a abertura de {intent.app_id}. O estado da interface ainda não é verificado."
