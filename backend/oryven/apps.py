"""Windows application inventory and exact, consent-gated launcher support.

Inventory is read-only. Launch targets are restricted to local .exe files or Start Menu
.lnk shortcuts discovered by this module; arbitrary paths supplied by API clients are
never accepted.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import sys
from typing import Iterable


class AppDiscoveryError(ValueError):
    pass


def _clean_display_icon(raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    # DisplayIcon commonly ends in `,0`. Never preserve command-line arguments.
    if value.startswith('"') and '"' in value[1:]:
        value = value[1:value.find('"', 1)]
    else:
        value = value.split(",", 1)[0].strip()
    return value


def _safe_local_target(raw: str, kind: str) -> str | None:
    try:
        path = Path(os.path.expandvars(str(raw))).expanduser()
    except (TypeError, ValueError):
        return None
    text = str(path)
    if not text or text.startswith("\\\\"):
        return None
    suffix = path.suffix.casefold()
    expected = ".exe" if kind == "executable" else ".lnk"
    if suffix != expected:
        return None
    try:
        resolved = path.resolve(strict=False)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_absolute():
        return None
    return str(resolved)


def _registry_inventory(limit: int) -> dict[str, dict[str, str]]:
    if sys.platform != "win32":
        return {}
    import winreg
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    found: dict[str, dict[str, str]] = {}
    for hive, reg_path in locations:
        try:
            root = winreg.OpenKey(hive, reg_path)
        except OSError:
            continue
        with root:
            index = 0
            while len(found) < limit:
                try:
                    key_name = winreg.EnumKey(root, index); index += 1
                except OSError:
                    break
                try:
                    with winreg.OpenKey(root, key_name) as key:
                        name = str(winreg.QueryValueEx(key, "DisplayName")[0]).strip()
                        try: version = str(winreg.QueryValueEx(key, "DisplayVersion")[0]).strip()
                        except OSError: version = ""
                        try: icon = _clean_display_icon(winreg.QueryValueEx(key, "DisplayIcon")[0])
                        except OSError: icon = ""
                    if not name or len(name) > 180:
                        continue
                    entry = {"name": name, "version": version, "launchable": False, "source": "uninstall-registry"}
                    target = _safe_local_target(icon, "executable") if icon else None
                    if target and Path(target).is_file():
                        entry.update({"launchable": True, "launch_target": target, "target_type": "executable"})
                    found.setdefault(name.casefold(), entry)
                except (OSError, ValueError, TypeError):
                    continue
    return found


def _app_paths_inventory(limit: int) -> dict[str, dict[str, str]]:
    if sys.platform != "win32":
        return {}
    import winreg
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    found: dict[str, dict[str, str]] = {}
    for hive, reg_path in locations:
        try: root = winreg.OpenKey(hive, reg_path)
        except OSError: continue
        with root:
            index = 0
            while len(found) < limit:
                try: key_name = winreg.EnumKey(root, index); index += 1
                except OSError: break
                try:
                    with winreg.OpenKey(root, key_name) as key:
                        raw = str(winreg.QueryValueEx(key, "")[0]).strip()
                    target = _safe_local_target(raw, "executable")
                    if not target or not Path(target).is_file():
                        continue
                    name = Path(target).stem
                    found[name.casefold()] = {"name": name, "version": "", "launchable": True,
                                              "launch_target": target, "target_type": "executable",
                                              "source": "app-paths"}
                except (OSError, ValueError, TypeError):
                    continue
    return found


def _start_menu_inventory(limit: int) -> dict[str, dict[str, str]]:
    if sys.platform != "win32":
        return {}
    roots = []
    for env_key, suffix in [
        ("APPDATA", Path("Microsoft/Windows/Start Menu/Programs")),
        ("PROGRAMDATA", Path("Microsoft/Windows/Start Menu/Programs")),
    ]:
        base = os.environ.get(env_key)
        if base:
            roots.append(Path(base) / suffix)
    found: dict[str, dict[str, str]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            shortcuts = root.rglob("*.lnk")
            for shortcut in shortcuts:
                if len(found) >= limit:
                    break
                target = _safe_local_target(str(shortcut), "shortcut")
                if not target:
                    continue
                name = shortcut.stem.strip()
                if name:
                    found.setdefault(name.casefold(), {"name": name, "version": "", "launchable": True,
                                                       "launch_target": target, "target_type": "shortcut",
                                                       "source": "start-menu"})
        except OSError:
            continue
    return found


def discover_installed_apps(limit: int = 250) -> list[dict]:
    if sys.platform != "win32":
        return []
    cap = max(1, min(limit, 500))
    merged = _registry_inventory(cap)
    # Prefer actually launchable sources over uninstall-only metadata.
    for source in (_app_paths_inventory(cap), _start_menu_inventory(cap)):
        for key, entry in source.items():
            prior = merged.get(key)
            if prior and prior.get("version") and not entry.get("version"):
                entry["version"] = prior["version"]
            merged[key] = entry
    return sorted(merged.values(), key=lambda x: x["name"].casefold())[:cap]


@dataclass(frozen=True)
class ResolvedApp:
    name: str
    launch_target: str
    target_type: str


class AppCatalog:
    """Resolve only targets that came from a trusted local inventory snapshot."""
    def __init__(self, *, platform: str | None = None, entries: Iterable[dict] | None = None, launcher=None):
        self.platform = platform or sys.platform
        self._entries = list(entries) if entries is not None else None
        self._launcher = launcher

    def list(self) -> list[dict]:
        if self._entries is not None:
            return [dict(v) for v in self._entries]
        return discover_installed_apps()

    def resolve(self, app_name: str) -> ResolvedApp:
        query = " ".join(str(app_name or "").split()).casefold()
        if not query:
            raise AppDiscoveryError("Informe o nome do aplicativo.")
        candidates = [e for e in self.list() if e.get("launchable") and e.get("launch_target")]
        exact = [e for e in candidates if str(e.get("name", "")).casefold() == query]
        matches = exact or [e for e in candidates if query in str(e.get("name", "")).casefold()]
        if len(matches) != 1:
            if not matches:
                raise AppDiscoveryError("Aplicativo não encontrado entre os alvos inicializáveis descobertos.")
            raise AppDiscoveryError("Nome ambíguo; escolha um aplicativo específico da lista descoberta.")
        entry = matches[0]
        target_type = str(entry.get("target_type", ""))
        target = _safe_local_target(str(entry.get("launch_target", "")), target_type)
        if not target:
            raise AppDiscoveryError("O alvo do aplicativo deixou de ser considerado seguro.")
        if self._entries is None and not Path(target).is_file():
            raise AppDiscoveryError("O alvo do aplicativo não existe mais.")
        return ResolvedApp(str(entry["name"]), target, target_type)

    def launch(self, resolved: ResolvedApp) -> dict:
        if self.platform != "win32":
            raise AppDiscoveryError("A abertura universal de aplicativos exige Windows 10/11.")
        target = _safe_local_target(resolved.launch_target, resolved.target_type)
        if not target or target != resolved.launch_target:
            raise AppDiscoveryError("Alvo do aplicativo inválido.")
        if self._launcher is not None:
            outcome = self._launcher(target, resolved.target_type)
            return {"app": resolved.name, "target_type": resolved.target_type, "launched": bool(outcome), "verified": bool(outcome)}
        try:
            if resolved.target_type == "shortcut":
                os.startfile(target)  # type: ignore[attr-defined]  # exact discovered .lnk, no shell string
                return {"app": resolved.name, "target_type": "shortcut", "launched": True, "verified": False,
                        "message": "Atalho solicitado; confirme a janela resultante."}
            proc = subprocess.Popen([target], cwd=str(Path(target).parent), shell=False,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"app": resolved.name, "target_type": "executable", "launched": True,
                    "verified": proc.pid > 0, "pid": proc.pid}
        except OSError as exc:
            raise AppDiscoveryError("O Windows não conseguiu iniciar o aplicativo selecionado.") from exc
