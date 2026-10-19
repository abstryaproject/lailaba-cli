"""Small, user-curated persistent memory for Lailaba CLI."""
from __future__ import annotations
import os
from pathlib import Path
from .config import config_home, ensure_dirs

MAX_MEMORY_CHARS = 12000


def memory_path() -> Path:
    return ensure_dirs() / "MEMORY.md"


def read_memory() -> str:
    path = memory_path()
    try:
        return path.read_text(encoding="utf-8")[:MAX_MEMORY_CHARS] if path.exists() else ""
    except OSError:
        return ""


def write_memory(content: str) -> Path:
    text = content.strip()
    if len(text) > MAX_MEMORY_CHARS:
        raise ValueError(f"Memory is limited to {MAX_MEMORY_CHARS} characters.")
    path = memory_path()
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(text + ("\n" if text else ""), encoding="utf-8")
    if os.name != "nt": tmp.chmod(0o600)
    tmp.replace(path)
    return path


def add_memory(note: str) -> Path:
    note = note.strip()
    if not note:
        raise ValueError("Memory note cannot be empty.")
    current = read_memory().rstrip()
    updated = (current + "\n" if current else "") + f"- {note}"
    return write_memory(updated)
