from __future__ import annotations
import json, time, uuid
from pathlib import Path
from .config import config_home, ensure_dirs

class Session:
    def __init__(self, session_id: str | None = None):
        self.id=session_id or (time.strftime("%Y%m%d-%H%M%S")+"-"+uuid.uuid4().hex[:6])
        self.messages=[]
    def save(self):
        root=ensure_dirs()/"sessions"; path=root/f"{self.id}.json"
        safe=list(self.messages)
        path.write_text(json.dumps({"id":self.id,"updated":time.time(),"messages":safe},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        if __import__('os').name!="nt": path.chmod(0o600)
    @classmethod
    def load(cls, session_id: str) -> "Session":
        if not session_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in session_id):
            raise ValueError("Invalid session ID.")
        path = config_home() / "sessions" / f"{session_id}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        messages = data.get("messages")
        if not isinstance(messages, list) or not all(isinstance(x, dict) for x in messages):
            raise ValueError("Session file has an invalid message format.")
        session = cls(session_id)
        session.messages = messages
        return session

def recent_sessions(limit:int=10)->list[dict]:
    root=config_home()/"sessions"
    if not root.exists(): return []
    out=[]
    for p in sorted(root.glob("*.json"),key=lambda x:x.stat().st_mtime,reverse=True)[:limit]:
        try:
            d=json.loads(p.read_text(encoding="utf-8")); out.append({"id":d.get("id",p.stem),"updated":d.get("updated"),"path":str(p)})
        except Exception: continue
    return out

def search_sessions(query: str, limit: int = 10) -> list[dict]:
    terms = [term.casefold() for term in query.split() if term]
    if not terms: return []
    root = config_home() / "sessions"
    if not root.exists(): return []
    matches = []
    for path in root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            messages = data.get("messages", [])
            texts = [str(m.get("content", "")) for m in messages if isinstance(m, dict)]
            haystack = "\\n".join(texts).casefold()
            if all(term in haystack for term in terms):
                excerpt = next((t.replace("\\n", " ")[:180] for t in texts if all(term in t.casefold() for term in terms)), "")
                matches.append({"id": data.get("id", path.stem), "updated": data.get("updated", 0), "excerpt": excerpt})
        except (OSError, ValueError, TypeError):
            continue
    return sorted(matches, key=lambda item: item.get("updated", 0), reverse=True)[:limit]
