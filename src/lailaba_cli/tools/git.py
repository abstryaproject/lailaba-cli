from __future__ import annotations
import asyncio, shutil
from pathlib import Path
from ..config import AppConfig
from ..permissions import path_in_roots
from .registry import Tool, ToolRegistry, obj_schema

async def _git(args:list[str],cwd:Path)->dict:
    if not shutil.which("git"): raise RuntimeError("Git is not installed.")
    p=await asyncio.create_subprocess_exec("git",*args,cwd=str(cwd),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try: out,err=await asyncio.wait_for(p.communicate(),15)
    except asyncio.TimeoutError: p.kill(); await p.wait(); raise RuntimeError("Git command timed out.")
    return {"exit_code":p.returncode,"stdout":out.decode(errors="replace")[:10000],"stderr":err.decode(errors="replace")[:2000],"cwd":str(cwd)}

def build_git_tools(reg:ToolRegistry,cfg:AppConfig):
    async def root(path:str=".")->Path:
        p=path_in_roots(Path(cfg.workspace)/path if not Path(path).is_absolute() else path,cfg.roots,allow_missing=False)
        return p
    async def git_status(path:str=".")->dict: return await _git(["status","--short","--branch"],await root(path))
    async def git_diff(path:str=".")->dict: return await _git(["diff","--"],await root(path))
    async def git_log(path:str=".",limit:int=10)->dict: return await _git(["log",f"-{max(1,min(limit,50))}","--oneline","--decorate"],await root(path))
    async def git_branch(path:str=".")->dict: return await _git(["branch","--show-current"],await root(path))
    for name,desc,handler,props in [
        ("git_status","Show Git working-tree status.",git_status,{"path":{"type":"string","default":"."}}),
        ("git_diff","Show unstaged Git diff; does not change the repository.",git_diff,{"path":{"type":"string","default":"."}}),
        ("git_log","Show recent one-line Git history.",git_log,{"path":{"type":"string","default":"."},"limit":{"type":"integer","minimum":1,"maximum":50,"default":10}}),
        ("git_branch","Show current Git branch.",git_branch,{"path":{"type":"string","default":"."}})]:
        reg.register(Tool(name,desc,obj_schema(props),handler))
