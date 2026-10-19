"""Minimal MCP stdio client for explicitly configured Model Context Protocol servers."""
from __future__ import annotations
import asyncio, json, re
from typing import Any
from .tools.registry import Tool, ToolRegistry, obj_schema

class MCPError(RuntimeError): pass

class MCPServer:
    def __init__(self, name: str, command: str, args: list[str] | None = None):
        self.name=name; self.command=command; self.args=args or []
        self.proc: asyncio.subprocess.Process | None=None
        self._id=0; self.tools: list[dict[str, Any]]=[]

    async def start(self):
        if self.proc and self.proc.returncode is None: return
        self.proc=await asyncio.create_subprocess_exec(self.command,*self.args,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        try:
            await self.request("initialize",{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"lailaba-cli","version":"0.6.0"}})
            await self.notify("notifications/initialized",{})
            result=await self.request("tools/list",{})
            self.tools=result.get("tools",[]) if isinstance(result,dict) else []
            if not isinstance(self.tools,list): self.tools=[]
        except Exception:
            await self.close(); raise

    async def _read_message(self):
        if not self.proc or not self.proc.stdout: raise MCPError("MCP server is not running")
        line=await asyncio.wait_for(self.proc.stdout.readline(),timeout=30)
        if not line: raise MCPError("MCP server closed its output")
        try: data=json.loads(line.decode("utf-8"))
        except Exception: raise MCPError("MCP server emitted invalid JSON on stdout; stdout must be reserved for protocol messages") from None
        if not isinstance(data,dict): raise MCPError("MCP server returned a malformed message")
        return data

    async def request(self, method: str, params: dict[str,Any]):
        if not self.proc or not self.proc.stdin: raise MCPError("MCP server is not running")
        self._id+=1; req_id=self._id
        payload={"jsonrpc":"2.0","id":req_id,"method":method,"params":params}
        self.proc.stdin.write((json.dumps(payload,separators=(",",":"))+"\n").encode()); await self.proc.stdin.drain()
        for _ in range(100):
            msg=await self._read_message()
            if msg.get("id") != req_id: continue
            if "error" in msg: raise MCPError(str(msg["error"])[:1000])
            return msg.get("result",{})
        raise MCPError("MCP server did not answer the request")

    async def notify(self, method: str, params: dict[str,Any]):
        if not self.proc or not self.proc.stdin: return
        self.proc.stdin.write((json.dumps({"jsonrpc":"2.0","method":method,"params":params},separators=(",",":"))+"\n").encode()); await self.proc.stdin.drain()

    async def call_tool(self, name: str, arguments: dict[str,Any]):
        await self.start()
        result=await self.request("tools/call",{"name":name,"arguments":arguments})
        if isinstance(result,dict) and result.get("isError"):
            raise MCPError(json.dumps(result.get("content",[]),ensure_ascii=False)[:2000])
        return result

    async def close(self):
        if self.proc and self.proc.returncode is None:
            self.proc.terminate()
            try: await asyncio.wait_for(self.proc.wait(),timeout=2)
            except asyncio.TimeoutError: self.proc.kill(); await self.proc.wait()
        self.proc=None

class MCPManager:
    def __init__(self, configs: list[dict[str,Any]]):
        self.servers: dict[str,MCPServer]={}
        for cfg in configs:
            if not isinstance(cfg,dict): continue
            name=str(cfg.get("name", "")); command=str(cfg.get("command", "")); args=cfg.get("args",[])
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}",name) or not command or not isinstance(args,list) or not all(isinstance(a,str) for a in args): continue
            self.servers[name]=MCPServer(name,command,args)
        self._loaded=False

    async def load_into(self, registry: ToolRegistry, log=print):
        if self._loaded: return
        self._loaded=True
        for server_name,server in self.servers.items():
            try:
                await server.start()
                for remote in server.tools:
                    if not isinstance(remote,dict): continue
                    original=str(remote.get("name", ""))
                    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}",original): continue
                    tool_name=f"mcp_{server_name}_{re.sub(r'[^a-zA-Z0-9_]', '_', original)}"
                    schema=remote.get("inputSchema")
                    if not isinstance(schema,dict) or schema.get("type")!="object": schema=obj_schema({})
                    # MCP tools can have external side effects. Always request approval.
                    async def handler(_server=server,_name=original,**kwargs): return await _server.call_tool(_name,kwargs)
                    registry.register(Tool(tool_name,f"MCP server {server_name}: {str(remote.get('description',''))[:400] or original}",schema,handler,risk="external",permission="mcp",timeout=60,confirmation=True))
                log(f"[mcp] {server_name}: loaded {len(server.tools)} tool(s)")
            except Exception as exc: log(f"[mcp:error] {server_name}: {exc.__class__.__name__}: {str(exc)[:300]}")

    async def close(self):
        await asyncio.gather(*(s.close() for s in self.servers.values()),return_exceptions=True)
