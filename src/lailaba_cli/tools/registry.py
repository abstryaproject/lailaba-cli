from __future__ import annotations
import asyncio, json, time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

@dataclass
class Tool:
    name: str
    description: str
    schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]
    risk: str = "read"
    permission: str = "read"
    timeout: float = 45
    confirmation: bool = False

    def api_definition(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.schema}}

class ToolRegistry:
    def __init__(self): self._tools: dict[str, Tool] = {}
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools: raise ValueError(f"Duplicate tool: {tool.name}")
        self._tools[tool.name] = tool
    def get(self, name: str) -> Tool:
        if name not in self._tools: raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]
    def list(self) -> list[Tool]: return list(self._tools.values())
    def definitions(self) -> list[dict[str, Any]]: return [t.api_definition() for t in self._tools.values()]
    async def execute(self, name: str, arguments: dict[str, Any], *, confirm=None) -> dict[str, Any]:
        start = time.monotonic()
        try:
            tool = self.get(name)
            if not isinstance(arguments, dict): raise ValueError("Tool arguments must be a JSON object.")
            required = tool.schema.get("required", [])
            props = tool.schema.get("properties", {})
            unknown = set(arguments) - set(props)
            missing = set(required) - set(arguments)
            if unknown or missing: raise ValueError(f"Invalid arguments; missing={sorted(missing)}, unknown={sorted(unknown)}")
            if tool.confirmation and confirm and not await confirm(tool, arguments):
                return {"ok": False, "error": "User declined the permission request.", "duration_seconds": round(time.monotonic()-start, 3)}
            result = await asyncio.wait_for(tool.handler(**arguments), timeout=tool.timeout)
            return {"ok": True, "result": result, "duration_seconds": round(time.monotonic()-start, 3)}
        except asyncio.TimeoutError:
            return {"ok": False, "error": "Tool execution timed out.", "duration_seconds": round(time.monotonic()-start, 3)}
        except Exception as exc:
            return {"ok": False, "error": f"{exc.__class__.__name__}: {str(exc)[:1000]}", "duration_seconds": round(time.monotonic()-start, 3)}

def obj_schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}
