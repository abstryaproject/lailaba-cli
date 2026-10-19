from __future__ import annotations
import json, os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

DEFAULT_API_BASE_URL = "https://100.57.251.241.nip.io/api/v1"

def config_home() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "lailaba-cli"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "lailaba-cli"

@dataclass
class AppConfig:
    workspace: str = field(default_factory=lambda: str(Path.cwd()))
    provider: str = "lailaba"
    api_base_url: str = DEFAULT_API_BASE_URL
    model_name: str = ""
    workspace_roots: list[str] = field(default_factory=list)
    max_iterations: int = 12
    max_tool_calls: int = 30
    task_timeout_seconds: int = 600
    tool_timeout_seconds: int = 45
    max_tool_output_chars: int = 12000
    allow_writes: bool = True
    allow_shell: bool = True
    allow_network: bool = True
    require_confirmation_for_writes: bool = True
    require_confirmation_for_shell: bool = True
    require_confirmation_for_installs: bool = True
    require_confirmation_for_deletes: bool = True
    allow_private_web_destinations: bool = False
    enabled_skills: list[str] = field(default_factory=list)
    disabled_skills: list[str] = field(default_factory=list)
    mcp_servers: list[dict] = field(default_factory=list)

    @classmethod
    def model_validate(cls, raw: dict) -> "AppConfig":
        # Keep compatibility with the previous Pydantic model while avoiding
        # pydantic-core's Rust extension, which does not have Android/Termux wheels.
        allowed = {item.name for item in fields(cls)}
        if not isinstance(raw, dict):
            raise ValueError("Configuration must be a JSON object")
        return cls(**{key: value for key, value in raw.items() if key in allowed})

    def model_dump(self) -> dict:
        return asdict(self)

    @property
    def roots(self) -> list[Path]:
        roots = self.workspace_roots or [self.workspace]
        return [Path(p).expanduser().resolve() for p in roots]

def ensure_dirs() -> Path:
    root = config_home()
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        root.chmod(0o700)
    for name in ("sessions", "skills", "logs"):
        (root / name).mkdir(exist_ok=True)
        if os.name != "nt": (root / name).chmod(0o700)
    return root

def load_config() -> AppConfig:
    root = ensure_dirs(); path = root / "config.json"
    if not path.exists():
        cfg = AppConfig()
        save_config(cfg)
        return cfg
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(raw)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Configuration could not be loaded: {exc.__class__.__name__}. Fix {path} or run setup again.") from None

def save_config(cfg: AppConfig) -> None:
    root = ensure_dirs(); path = root / "config.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg.model_dump(), indent=2) + "\n", encoding="utf-8")
    if os.name != "nt": tmp.chmod(0o600)
    tmp.replace(path)
