from __future__ import annotations
from pathlib import Path
from ..config import AppConfig
from ..checkpoints import list_checkpoints, rollback_checkpoint
from ..tasks import add_task, complete_task, list_tasks, remove_task
from .registry import Tool, ToolRegistry, obj_schema


def build_agent_feature_tools(reg: ToolRegistry, cfg: AppConfig):
    async def todo_add(title: str, details: str = "") -> dict:
        return add_task(cfg.workspace, title, details)
    async def todo_list(include_done: bool = True) -> list[dict]:
        return list_tasks(cfg.workspace, include_done)
    async def todo_complete(task_id: str) -> dict:
        return complete_task(cfg.workspace, task_id, True)
    async def todo_reopen(task_id: str) -> dict:
        return complete_task(cfg.workspace, task_id, False)
    async def todo_remove(task_id: str) -> dict:
        return remove_task(cfg.workspace, task_id)
    async def checkpoints_list(limit: int = 20) -> list[dict]:
        return list_checkpoints(cfg.workspace, limit)
    async def file_rollback(checkpoint_id: str = "") -> dict:
        return rollback_checkpoint(checkpoint_id or None, cfg.workspace, cfg.roots)

    reg.register(Tool("todo_add", "Add a task to Lailaba CLI's persistent workspace task list.", obj_schema({"title":{"type":"string","minLength":1,"maxLength":300},"details":{"type":"string","maxLength":2000,"default":""}}, ["title"]), todo_add, risk="write", permission="write"))
    reg.register(Tool("todo_list", "List persistent workspace tasks and their completion status.", obj_schema({"include_done":{"type":"boolean","default":True}}), todo_list))
    reg.register(Tool("todo_complete", "Mark a workspace task as complete by task ID.", obj_schema({"task_id":{"type":"string"}}, ["task_id"]), todo_complete, risk="write", permission="write"))
    reg.register(Tool("todo_reopen", "Reopen a completed workspace task by task ID.", obj_schema({"task_id":{"type":"string"}}, ["task_id"]), todo_reopen, risk="write", permission="write"))
    reg.register(Tool("todo_remove", "Remove a workspace task by task ID.", obj_schema({"task_id":{"type":"string"}}, ["task_id"]), todo_remove, risk="write", permission="write", confirmation=True))
    reg.register(Tool("checkpoints_list", "List recent automatic checkpoints created before file writes and edits.", obj_schema({"limit":{"type":"integer","minimum":1,"maximum":100,"default":20}}), checkpoints_list))
    reg.register(Tool("file_rollback", "Restore a file to its pre-edit checkpoint. Requires explicit user confirmation.", obj_schema({"checkpoint_id":{"type":"string","default":""}}), file_rollback, risk="write", permission="write", confirmation=True))
