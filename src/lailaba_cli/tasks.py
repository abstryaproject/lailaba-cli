"""Persistent, local task list used by the agent's planning tools."""
from __future__ import annotations
import json, os, time, uuid
from pathlib import Path
from .config import ensure_dirs

def tasks_path(workspace: str | Path) -> Path:
    import hashlib
    key=hashlib.sha256(str(Path(workspace).resolve()).encode()).hexdigest()[:16]
    return ensure_dirs() / "tasks" / f"{key}.json"

def _load(workspace: str | Path) -> list[dict]:
    p=tasks_path(workspace)
    try:
        data=json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        return data if isinstance(data,list) else []
    except (OSError,ValueError): return []

def _save(workspace: str | Path, items: list[dict]) -> Path:
    p=tasks_path(workspace); p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(".tmp"); tmp.write_text(json.dumps(items,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if os.name!="nt": tmp.chmod(0o600)
    tmp.replace(p); return p

def list_tasks(workspace: str | Path, include_done: bool=True) -> list[dict]:
    items=_load(workspace)
    return items if include_done else [x for x in items if not x.get("done")]

def add_task(workspace: str | Path, title: str, details: str="") -> dict:
    title=title.strip()
    if not title or len(title)>300: raise ValueError("Task title must contain 1–300 characters.")
    items=_load(workspace); item={"id":uuid.uuid4().hex[:8],"title":title,"details":details[:2000],"done":False,"created":time.time(),"updated":time.time()}
    items.append(item); _save(workspace,items); return item

def complete_task(workspace: str | Path, task_id: str, done: bool=True) -> dict:
    items=_load(workspace)
    for item in items:
        if item.get("id")==task_id:
            item["done"]=done; item["updated"]=time.time(); _save(workspace,items); return item
    raise KeyError(f"Task {task_id!r} was not found.")

def remove_task(workspace: str | Path, task_id: str) -> dict:
    items=_load(workspace)
    for i,item in enumerate(items):
        if item.get("id")==task_id:
            removed=items.pop(i); _save(workspace,items); return removed
    raise KeyError(f"Task {task_id!r} was not found.")
