import json, sys
from pathlib import Path
import pytest
from lailaba_cli.mcp import MCPServer
import lailaba_cli.scheduler as scheduler

@pytest.mark.asyncio
async def test_mcp_stdio_initialize_list_and_call():
    script = r'''import sys,json
for line in sys.stdin:
 m=json.loads(line); method=m.get("method"); rid=m.get("id")
 if method=="initialize": result={"protocolVersion":"2024-11-05","capabilities":{"tools":{}},"serverInfo":{"name":"test","version":"1"}}
 elif method=="tools/list": result={"tools":[{"name":"echo","description":"Echo input","inputSchema":{"type":"object","properties":{"text":{"type":"string"}},"required":["text"]}}]}
 elif method=="tools/call": result={"content":[{"type":"text","text":m["params"]["arguments"]["text"]}]}
 else: continue
 if rid is not None: print(json.dumps({"jsonrpc":"2.0","id":rid,"result":result}),flush=True)
'''
    server = MCPServer("test", sys.executable, ["-u", "-c", script])
    try:
        await server.start()
        assert server.tools[0]["name"] == "echo"
        result = await server.call_tool("echo", {"text": "hello"})
        assert result["content"][0]["text"] == "hello"
    finally:
        await server.close()

def test_scheduler_add_list_remove(monkeypatch, tmp_path):
    monkeypatch.setattr(scheduler, "config_home", lambda: tmp_path)
    item = scheduler.add_job("review tests", 15, str(tmp_path))
    assert item["every_minutes"] == 15
    assert scheduler.list_jobs()[0]["id"] == item["id"]
    assert scheduler.remove_job(item["id"])
    assert scheduler.list_jobs() == []
