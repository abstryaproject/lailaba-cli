from __future__ import annotations
import asyncio, os, shlex, shutil, sys, time
from pathlib import Path
from ..config import AppConfig
from ..permissions import check_command, path_in_roots, PermissionDenied
from .registry import Tool, ToolRegistry, obj_schema

MAX_OUTPUT = 12000

def build_terminal_tools(reg: ToolRegistry, cfg: AppConfig):
    async def terminal_execute(command: str, working_directory: str = ".", timeout_seconds: int = 30) -> dict:
        check_command(command,cfg)
        cwd = path_in_roots(Path(cfg.workspace)/working_directory if not Path(working_directory).is_absolute() else working_directory,cfg.roots,allow_missing=False)
        if not cwd.is_dir(): raise NotADirectoryError(str(cwd))
        timeout = max(1,min(int(timeout_seconds),cfg.tool_timeout_seconds,120))
        # Explicit shell is used to enable normal pipelines/redirection; policy checks apply first.
        shell = os.environ.get("COMSPEC", "cmd.exe") if os.name=="nt" else "/bin/bash"
        args = [shell,"/c",command] if os.name=="nt" else [shell,"-lc",command]
        start=time.monotonic(); proc=None; timed_out=False
        try:
            proc=await asyncio.create_subprocess_exec(*args,cwd=str(cwd),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,start_new_session=(os.name!="nt"))
            try: out,err=await asyncio.wait_for(proc.communicate(),timeout=timeout)
            except asyncio.TimeoutError:
                timed_out=True
                try:
                    if os.name!="nt": os.killpg(proc.pid, __import__('signal').SIGTERM)
                    else: proc.terminate()
                except ProcessLookupError: pass
                try: out,err=await asyncio.wait_for(proc.communicate(),timeout=2)
                except asyncio.TimeoutError:
                    try: proc.kill()
                    except ProcessLookupError: pass
                    out,err=await proc.communicate()
            limit=min(cfg.max_tool_output_chars,MAX_OUTPUT)
            return {"exit_code":proc.returncode,"stdout":out.decode("utf-8","replace")[:limit],"stderr":err.decode("utf-8","replace")[:limit],"duration_seconds":round(time.monotonic()-start,3),"timed_out":timed_out,"working_directory":str(cwd),"output_truncated":len(out)>limit or len(err)>limit}
        finally:
            if proc and proc.returncode is None:
                try: proc.kill(); await proc.wait()
                except ProcessLookupError: pass
    async def get_cwd() -> dict: return {"working_directory":str(Path(cfg.workspace).resolve())}
    async def list_environment() -> dict: return {"platform":sys.platform,"python":sys.version.split()[0],"path_entries":len(os.environ.get("PATH","").split(os.pathsep)),"available_commands":{c:shutil.which(c) is not None for c in ["git","python","python3","node","npm","pytest","bash"]}}
    async def check_command_available(command: str) -> dict: return {"command":command,"available":shutil.which(command) is not None}
    async def run_tests(command: str = "python -m pytest -q", working_directory: str = ".") -> dict: return await terminal_execute(command,working_directory,60)
    common = {"command":{"type":"string"},"working_directory":{"type":"string","default":"."},"timeout_seconds":{"type":"integer","minimum":1,"maximum":120,"default":30}}
    reg.register(Tool("terminal_execute","Execute a shell command in the configured workspace. Commands are policy-checked; writes and network-affecting commands may require confirmation.",obj_schema(common,["command"]),terminal_execute,risk="shell",permission="shell",timeout=cfg.tool_timeout_seconds,confirmation=cfg.require_confirmation_for_shell))
    reg.register(Tool("terminal_get_working_directory","Return the configured workspace path.",obj_schema({}),get_cwd))
    reg.register(Tool("terminal_list_environment","Return safe environment metadata without environment variable values or secrets.",obj_schema({}),list_environment))
    reg.register(Tool("terminal_check_command","Check whether an executable is available on PATH.",obj_schema({"command":{"type":"string"}},["command"]),check_command_available))
    reg.register(Tool("run_tests","Run the requested test command in the workspace.",obj_schema({"command":{"type":"string","default":"python -m pytest -q"},"working_directory":{"type":"string","default":"."}},[]),run_tests,risk="shell",permission="shell",timeout=cfg.tool_timeout_seconds,confirmation=cfg.require_confirmation_for_shell))
