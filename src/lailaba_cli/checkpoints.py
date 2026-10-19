"""Workspace file checkpoints for safe, reversible agent edits."""
from __future__ import annotations
import base64, hashlib, json, os, time, uuid
from pathlib import Path
from .config import ensure_dirs
from .permissions import path_in_roots

MAX_CHECKPOINT_BYTES = 1_000_000

def _workspace_id(workspace: str | Path) -> str:
    return hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:16]

def checkpoint_root(workspace: str | Path) -> Path:
    root = ensure_dirs() / "checkpoints" / _workspace_id(workspace)
    root.mkdir(parents=True, exist_ok=True)
    if os.name != "nt": root.chmod(0o700)
    return root

def create_checkpoint(path: str | Path, workspace: str | Path, roots: list[Path]) -> dict:
    p = path_in_roots(path, roots)
    exists = p.is_file()
    content = b""
    if exists:
        if p.stat().st_size > MAX_CHECKPOINT_BYTES:
            raise ValueError(f"Cannot checkpoint files larger than {MAX_CHECKPOINT_BYTES} bytes.")
        content = p.read_bytes()
    cid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    item = {"id": cid, "created": time.time(), "workspace": str(Path(workspace).resolve()),
            "path": str(p), "existed": exists, "content_b64": base64.b64encode(content).decode("ascii")}
    dest = checkpoint_root(workspace) / f"{cid}.json"
    dest.write_text(json.dumps(item, ensure_ascii=False) + "\n", encoding="utf-8")
    if os.name != "nt": dest.chmod(0o600)
    return {"id": cid, "path": str(p), "captured_existing_file": exists}

def list_checkpoints(workspace: str | Path, limit: int = 30) -> list[dict]:
    out=[]
    for f in sorted(checkpoint_root(workspace).glob("*.json"), key=lambda p:p.stat().st_mtime, reverse=True)[:max(1,min(limit,100))]:
        try:
            d=json.loads(f.read_text(encoding="utf-8"))
            out.append({"id":d["id"],"created":d["created"],"path":d["path"],"existed":d["existed"]})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out

def rollback_checkpoint(checkpoint_id: str | None, workspace: str | Path, roots: list[Path]) -> dict:
    root=checkpoint_root(workspace)
    if checkpoint_id:
        if not checkpoint_id.replace("-", "").isalnum(): raise ValueError("Invalid checkpoint ID.")
        f=root / f"{checkpoint_id}.json"
    else:
        entries=sorted(root.glob("*.json"), key=lambda p:p.stat().st_mtime, reverse=True)
        if not entries: raise FileNotFoundError("No checkpoints are available for this workspace.")
        f=entries[0]
    if not f.is_file(): raise FileNotFoundError("Checkpoint not found in this workspace.")
    d=json.loads(f.read_text(encoding="utf-8"))
    if Path(d.get("workspace", "")).resolve() != Path(workspace).resolve(): raise ValueError("Checkpoint workspace mismatch.")
    p=path_in_roots(d["path"], roots)
    if d.get("existed"):
        raw=base64.b64decode(d.get("content_b64", ""), validate=True)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp=p.with_name(p.name + ".lailaba-rollback.tmp")
        tmp.write_bytes(raw); tmp.replace(p)
        return {"id":d["id"],"path":str(p),"restored":True,"bytes":len(raw)}
    if p.exists() and p.is_file(): p.unlink()
    return {"id":d["id"],"path":str(p),"restored":False,"removed_new_file":True}
