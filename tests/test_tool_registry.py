import pytest
from lailaba_cli.tools.registry import ToolRegistry, Tool, obj_schema

@pytest.mark.asyncio
async def test_tool_executes_real_handler_and_validates():
    reg=ToolRegistry(); called=[]
    async def add(x:int): called.append(x); return {"sum":x+1}
    reg.register(Tool("add","test",obj_schema({"x":{"type":"integer"}},["x"]),add))
    result=await reg.execute("add",{"x":4})
    assert result["ok"] and result["result"]=={"sum":5} and called==[4]
    invalid=await reg.execute("add",{"wrong":1})
    assert not invalid["ok"] and called==[4]
