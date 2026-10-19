import asyncio, os
import pytest
from pathlib import Path
from lailaba_cli.config import AppConfig
from lailaba_cli.permissions import check_command, PermissionDenied, path_in_roots
from lailaba_cli.tools.registry import ToolRegistry
from lailaba_cli.tools.terminal import build_terminal_tools

@pytest.mark.asyncio
async def test_terminal_executes_command(tmp_path):
    cfg=AppConfig(workspace=str(tmp_path),workspace_roots=[str(tmp_path)],require_confirmation_for_shell=False)
    reg=ToolRegistry(); build_terminal_tools(reg,cfg)
    r=await reg.execute("terminal_execute",{"command":"python -c 'print(2+2)'","working_directory":".","timeout_seconds":5})
    assert r["ok"] and r["result"]["exit_code"]==0 and "4" in r["result"]["stdout"]

@pytest.mark.asyncio
async def test_terminal_timeout(tmp_path):
    cfg=AppConfig(workspace=str(tmp_path),workspace_roots=[str(tmp_path)],tool_timeout_seconds=2,require_confirmation_for_shell=False)
    reg=ToolRegistry(); build_terminal_tools(reg,cfg)
    r=await reg.execute("terminal_execute",{"command":"python -c 'import time; time.sleep(4)'","working_directory":".","timeout_seconds":1})
    assert r["ok"] and r["result"]["timed_out"]

def test_dangerous_command_denied():
    cfg=AppConfig()
    with pytest.raises(PermissionDenied): check_command("sudo rm -rf /",cfg)

def test_path_escape_denied(tmp_path):
    with pytest.raises(PermissionDenied): path_in_roots(tmp_path.parent,[tmp_path])
