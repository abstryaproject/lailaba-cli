"""Persistent interval-based agent jobs. Run `schedule daemon` to execute due jobs."""
from __future__ import annotations
import json, os, time, uuid
from pathlib import Path
from .config import config_home

def _path():
    p=config_home()/"scheduled_jobs.json"; p.parent.mkdir(parents=True,exist_ok=True); return p

def _load():
    p=_path()
    if not p.exists(): return []
    try: data=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,ValueError): raise RuntimeError(f"Cannot read scheduled jobs file: {p}")
    if not isinstance(data,list): raise RuntimeError("Scheduled jobs file must contain a JSON list")
    return [x for x in data if isinstance(x,dict)]

def _save(items):
    p=_path(); tmp=p.with_suffix(".tmp"); tmp.write_text(json.dumps(items,indent=2)+"\n",encoding="utf-8")
    if os.name!="nt": tmp.chmod(0o600)
    tmp.replace(p)

def add_job(task: str, every_minutes: int, workspace: str):
    if not task.strip() or len(task)>5000: raise ValueError("Task must be 1–5000 characters")
    if not 1<=every_minutes<=43200: raise ValueError("Interval must be between 1 and 43200 minutes")
    items=_load(); item={"id":uuid.uuid4().hex[:10],"task":task.strip(),"every_minutes":every_minutes,"workspace":str(Path(workspace).resolve()),"created_at":int(time.time()),"next_run_at":int(time.time())+every_minutes*60,"enabled":True,"last_status":"never"}
    items.append(item); _save(items); return item

def list_jobs(): return _load()
def remove_job(job_id: str):
    items=_load(); updated=[x for x in items if x.get("id")!=job_id]
    if len(updated)==len(items): return False
    _save(updated); return True

def due_jobs(now: int|None=None):
    now=int(now or time.time()); items=_load(); due=[]
    for job in items:
        if job.get("enabled") and int(job.get("next_run_at",0))<=now: due.append(job)
    return due

def record_job(job_id: str, success: bool, now: int|None=None):
    now=int(now or time.time()); items=_load()
    for job in items:
        if job.get("id")==job_id:
            job["last_run_at"]=now; job["last_status"]="success" if success else "failed"
            job["next_run_at"]=now+int(job.get("every_minutes",60))*60; break
    _save(items)
