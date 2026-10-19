from __future__ import annotations
import os, fnmatch
from pathlib import Path
from typing import Any
from ..config import AppConfig
from ..permissions import path_in_roots, PermissionDenied
from ..checkpoints import create_checkpoint
from .registry import Tool, ToolRegistry, obj_schema

MAX_READ = 200_000

def build_filesystem_tools(reg: ToolRegistry, cfg: AppConfig):
    async def list_directory(path: str = ".") -> dict[str, Any]:
        p = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots)
        if not p.is_dir(): raise NotADirectoryError(str(p))
        entries = []
        for x in sorted(p.iterdir(), key=lambda v: (not v.is_dir(), v.name.lower()))[:500]:
            entries.append({"name": x.name, "type": "directory" if x.is_dir() else "file", "size": x.stat().st_size if x.is_file() else None})
        return {"path": str(p), "entries": entries}
    async def read_file(path: str, max_chars: int = 20000) -> dict[str, Any]:
        p = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots, allow_missing=False)
        if not p.is_file(): raise FileNotFoundError(str(p))
        if p.stat().st_size > MAX_READ: raise ValueError("File is too large to read directly; use search or a smaller range.")
        data = p.read_text(encoding="utf-8", errors="replace")
        return {"path": str(p), "content": data[:max(1,min(max_chars,50000))], "truncated": len(data)>max_chars}
    async def write_file(path: str, content: str) -> dict[str, Any]:
        if not cfg.allow_writes: raise PermissionDenied("File writes are disabled by policy.")
        p = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots)
        if len(content) > 500000: raise ValueError("Content exceeds 500 KB limit.")
        existed = p.exists()
        checkpoint = create_checkpoint(p, cfg.workspace, cfg.roots)
        p.parent.mkdir(parents=True, exist_ok=True); p.write_text(content, encoding="utf-8")
        return {"path": str(p), "bytes_written": p.stat().st_size, "overwrote_existing_file": existed, "checkpoint_id": checkpoint["id"]}
    async def edit_file(path: str, old_text: str, new_text: str) -> dict[str, Any]:
        p = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots, allow_missing=False)
        if not cfg.allow_writes: raise PermissionDenied("File writes are disabled by policy.")
        content = p.read_text(encoding="utf-8")
        if not old_text or content.count(old_text) != 1: raise ValueError("The target text must occur exactly once; file left unchanged.")
        checkpoint = create_checkpoint(p, cfg.workspace, cfg.roots)
        p.write_text(content.replace(old_text,new_text,1), encoding="utf-8")
        return {"path": str(p), "edited": True, "checkpoint_id": checkpoint["id"]}
    async def create_directory(path: str) -> dict[str, Any]:
        if not cfg.allow_writes: raise PermissionDenied("Directory creation is disabled by policy.")
        p = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots)
        p.mkdir(parents=True, exist_ok=True); return {"path": str(p), "exists": True}
    async def search_files(query: str, path: str = ".", glob: str = "*") -> list[dict[str, Any]]:
        root = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots)
        results=[]
        for f in root.rglob("*"):
            if len(results)>=100: break
            if not f.is_file() or any(part in {".git", ".venv", "node_modules", "__pycache__"} for part in f.parts): continue
            if not fnmatch.fnmatch(f.name,glob) or f.stat().st_size>MAX_READ: continue
            try:
                for i,line in enumerate(f.read_text(encoding="utf-8",errors="ignore").splitlines(),1):
                    if query.casefold() in line.casefold(): results.append({"path":str(f),"line":i,"text":line[:500]})
                    if len(results)>=100: break
            except OSError: continue
        return results
    async def find_text(query: str, path: str = ".") -> list[dict[str, Any]]: return await search_files(query,path)
    async def inspect_file_metadata(path: str) -> dict[str, Any]:
        p = path_in_roots(Path(cfg.workspace) / path if not Path(path).is_absolute() else path, cfg.roots, allow_missing=False); s=p.stat()
        return {"path":str(p),"is_file":p.is_file(),"is_directory":p.is_dir(),"size_bytes":s.st_size,"modified_time":s.st_mtime}
    S = {"path":{"type":"string"}}
    reg.register(Tool("list_directory","List entries in a workspace directory.",obj_schema({"path":{"type":"string","default":"."}}),list_directory))
    reg.register(Tool("read_file","Read a text file within workspace roots.",obj_schema({"path":{"type":"string"},"max_chars":{"type":"integer","minimum":1,"maximum":50000,"default":20000}},["path"]),read_file))
    reg.register(Tool("write_file","Create or replace a workspace text file. Existing content may be overwritten.",obj_schema({"path":{"type":"string"},"content":{"type":"string"}},["path","content"]),write_file,risk="write",permission="write",confirmation=cfg.require_confirmation_for_writes))
    reg.register(Tool("edit_file","Replace one exact, unique text occurrence in a workspace file.",obj_schema({"path":{"type":"string"},"old_text":{"type":"string"},"new_text":{"type":"string"}},["path","old_text","new_text"]),edit_file,risk="write",permission="write",confirmation=cfg.require_confirmation_for_writes))
    reg.register(Tool("create_directory","Create a directory within workspace roots.",obj_schema({"path":{"type":"string"}},["path"]),create_directory,risk="write",permission="write",confirmation=cfg.require_confirmation_for_writes))
    reg.register(Tool("search_files","Search file contents within the workspace.",obj_schema({"query":{"type":"string"},"path":{"type":"string","default":"."},"glob":{"type":"string","default":"*"}},["query"]),search_files))
    reg.register(Tool("find_text","Find text in project files.",obj_schema({"query":{"type":"string"},"path":{"type":"string","default":"."}},["query"]),find_text))
    reg.register(Tool("inspect_file_metadata","Inspect basic metadata for a workspace path.",obj_schema({"path":{"type":"string"}},["path"]),inspect_file_metadata))
