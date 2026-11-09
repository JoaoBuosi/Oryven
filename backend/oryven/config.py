from dataclasses import dataclass, field
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    model_dir: Path
    wake_seconds: int = 20
    approval_seconds: int = 120
    buno_api_url: str = "http://127.0.0.1:8000"
    buno_bearer_token: str = field(default="", repr=False)
    elevenlabs_enabled: bool = False
    elevenlabs_api_key: str = field(default="", repr=False)
    elevenlabs_voice_id: str = ""
    elevenlabs_model_id: str = "eleven_flash_v2_5"
    developer_roots: tuple[Path, ...] = ()
    developer_timeout_seconds: int = 180
    work_roots: tuple[Path, ...] = ()
    work_timeout_seconds: int = 120
    terminal_executables: tuple[str, ...] = ()
    sendgrid_api_key: str = field(default="", repr=False)
    sendgrid_from_email: str = ""
    sendgrid_from_name: str = "Oryven by Buno AI"
    email_hook_url: str = ""
    email_hook_secret: str = field(default="", repr=False)
    vision_provider: str = "structured"
    vision_ollama_url: str = "http://127.0.0.1:11434"
    vision_model: str = ""
    vision_timeout_seconds: int = 45
    license_key_sha256: str = field(default="", repr=False)
    update_manifest_url: str = ""
    support_email: str = "support@buno.ai"
    pilot_service_url: str = ""
    pilot_service_token: str = field(default="", repr=False)

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.environ.get("ORYVEN_DATA_DIR", str(Path.home() / ".oryven-mvp"))).expanduser()
        model = Path(os.environ.get("ORYVEN_VOSK_MODEL", str(root / "models" / "vosk-model-small-pt-0.3"))).expanduser()
        roots_raw = os.environ.get("ORYVEN_DEVELOPER_ROOTS", "")
        roots = tuple(Path(v).expanduser() for v in roots_raw.split(os.pathsep) if v.strip())
        work_raw = os.environ.get("ORYVEN_WORK_ROOTS", roots_raw)
        work_roots = tuple(Path(v).expanduser() for v in work_raw.split(os.pathsep) if v.strip())
        terminal_execs = tuple(v.strip() for v in os.environ.get("ORYVEN_TERMINAL_EXECUTABLES", "").split(",") if v.strip())
        return cls(
            data_dir=root, model_dir=model,
            buno_api_url=os.environ.get("ORYVEN_BUNO_API_URL", "http://127.0.0.1:8000"),
            buno_bearer_token=os.environ.get("ORYVEN_BUNO_BEARER_TOKEN", ""),
            elevenlabs_enabled=os.environ.get("ELEVENLABS_ENABLED", "false").lower() in ("1", "true", "yes"),
            elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.environ.get("ELEVENLABS_VOICE_ID", ""),
            elevenlabs_model_id=os.environ.get("ELEVENLABS_MODEL_ID", "eleven_flash_v2_5"),
            developer_roots=roots,
            developer_timeout_seconds=int(os.environ.get("ORYVEN_DEVELOPER_TIMEOUT_SECONDS", "180")),
            work_roots=work_roots,
            work_timeout_seconds=int(os.environ.get("ORYVEN_WORK_TIMEOUT_SECONDS", "120")),
            terminal_executables=terminal_execs,
            sendgrid_api_key=os.environ.get("SENDGRID_API_KEY", ""),
            sendgrid_from_email=os.environ.get("SENDGRID_FROM_EMAIL", ""),
            sendgrid_from_name=os.environ.get("SENDGRID_FROM_NAME", "Oryven by Buno AI"),
            email_hook_url=os.environ.get("ORYVEN_EMAIL_HOOK_URL", "").strip(),
            email_hook_secret=os.environ.get("ORYVEN_EMAIL_HOOK_SECRET", "").strip(),
            vision_provider=os.environ.get("ORYVEN_VISION_PROVIDER", "structured").strip().lower(),
            vision_ollama_url=os.environ.get("ORYVEN_VISION_OLLAMA_URL", "http://127.0.0.1:11434"),
            vision_model=os.environ.get("ORYVEN_VISION_MODEL", ""),
            vision_timeout_seconds=int(os.environ.get("ORYVEN_VISION_TIMEOUT_SECONDS", "45")),
            license_key_sha256=os.environ.get("ORYVEN_LICENSE_KEY_SHA256", "").strip(),
            update_manifest_url=os.environ.get("ORYVEN_UPDATE_MANIFEST_URL", "").strip(),
            support_email=os.environ.get("ORYVEN_SUPPORT_EMAIL", "support@buno.ai").strip(),
            pilot_service_url=os.environ.get("ORYVEN_PILOT_SERVICE_URL", "").strip(),
            pilot_service_token=os.environ.get("ORYVEN_PILOT_SERVICE_TOKEN", "").strip(),
        )
