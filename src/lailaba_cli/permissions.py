from __future__ import annotations
import os, re, shlex
from pathlib import Path
from .config import AppConfig

class PermissionDenied(RuntimeError): pass

DANGEROUS = [r'\brm\s+(-[^\s]*r[^\s]*f|-[^\s]*f[^\s]*r)', r'\bmkfs\b', r'\bdd\s+if=', r'\bshutdown\b', r'\breboot\b', r'\b(chmod|chown)\s+-R\b', r'>\s*/dev/', r'\bsudo\b', r'\bsu\s+-?\b', r'\bgit\s+push\s+.*--force\b', r'\bdrop\s+database\b', r'\btruncate\s+table\b']

def path_in_roots(path: str | Path, roots: list[Path], *, allow_missing: bool = True) -> Path:
    p = Path(path).expanduser()
    # Resolve parent for new files while still checking symlink targets.
    resolved = p.resolve(strict=not allow_missing)
    for root in roots:
        try: resolved.relative_to(root.resolve()); return resolved
        except ValueError: continue
    raise PermissionDenied(f"Path is outside the configured workspace roots: {p}")

def check_command(command: str, cfg: AppConfig) -> None:
    if not cfg.allow_shell: raise PermissionDenied("Terminal execution is disabled by policy.")
    if not command.strip() or len(command) > 4000: raise PermissionDenied("Command is empty or exceeds the command length limit.")
    for pattern in DANGEROUS:
        if re.search(pattern, command, re.I): raise PermissionDenied("Command denied by the destructive/system-command policy.")
    # Avoid common shell escapes and privilege escalation; normal commands still go through confirmation.
    if re.search(r'(^|[;&|])\s*(curl|wget)\b.*\|\s*(sh|bash)', command, re.I):
        raise PermissionDenied("Piping downloaded content directly into a shell is denied.")
    try: parts = shlex.split(command, posix=os.name != "nt")
    except ValueError: raise PermissionDenied("Command could not be parsed safely.") from None
    if parts and parts[0] in {"sudo", "su", "doas"}: raise PermissionDenied("Privilege escalation is denied.")
