from pathlib import Path
import pytest
from lailaba_cli import checkpoints, tasks
from lailaba_cli.config import AppConfig
from lailaba_cli.tools.registry import ToolRegistry
from lailaba_cli.tools.filesystem import build_filesystem_tools


def test_checkpoint_restore_existing_file(tmp_path, monkeypatch):
    cfg_home=tmp_path/"config"
    monkeypatch.setenv("XDG_CONFIG_HOME",str(cfg_home))
    workspace=tmp_path/"project"; workspace.mkdir()
    target=workspace/"demo.txt"; target.write_text("before",encoding="utf-8")
    cfg=AppConfig(workspace=str(workspace),workspace_roots=[str(workspace)])
    checkpoint=checkpoints.create_checkpoint(target,workspace,cfg.roots)
    target.write_text("after",encoding="utf-8")
    result=checkpoints.rollback_checkpoint(checkpoint["id"],workspace,cfg.roots)
    assert result["restored"] is True
    assert target.read_text(encoding="utf-8")=="before"


def test_checkpoint_rollback_removes_new_file(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path/"config"))
    workspace=tmp_path/"project"; workspace.mkdir()
    target=workspace/"new.txt"
    cfg=AppConfig(workspace=str(workspace),workspace_roots=[str(workspace)])
    checkpoint=checkpoints.create_checkpoint(target,workspace,cfg.roots)
    target.write_text("created",encoding="utf-8")
    result=checkpoints.rollback_checkpoint(checkpoint["id"],workspace,cfg.roots)
    assert result["removed_new_file"] is True
    assert not target.exists()


def test_tasks_persist_and_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path/"config"))
    workspace=tmp_path/"project"; workspace.mkdir()
    task=tasks.add_task(workspace,"Add tests","cover the rollback flow")
    assert tasks.list_tasks(workspace,False)[0]["id"]==task["id"]
    tasks.complete_task(workspace,task["id"])
    assert tasks.list_tasks(workspace,False)==[]
    assert tasks.list_tasks(workspace)[0]["done"] is True


@pytest.mark.asyncio
async def test_write_file_creates_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path/"config"))
    workspace=tmp_path/"project"; workspace.mkdir()
    cfg=AppConfig(workspace=str(workspace),workspace_roots=[str(workspace)],require_confirmation_for_writes=False)
    reg=ToolRegistry(); build_filesystem_tools(reg,cfg)
    result=await reg.execute("write_file",{"path":"note.txt","content":"hello"})
    assert result["ok"]
    assert result["result"]["checkpoint_id"]
    assert (workspace/"note.txt").read_text(encoding="utf-8")=="hello"
