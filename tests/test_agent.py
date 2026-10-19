import pytest
from lailaba_cli.agent import Agent
from lailaba_cli.config import AppConfig

@pytest.mark.asyncio
async def test_agent_executes_tool_and_returns_model_result(tmp_path):
    class API:
        n=0
        async def chat(self,messages,tools,model=None):
            self.n+=1
            if self.n==1:
                return {"choices":[{"message":{"role":"assistant","content":None,"tool_calls":[{"id":"call1","type":"function","function":{"name":"calculate","arguments":"{\"expression\":\"2+3\"}"}}]}}]}
            assert any(m.get("role")=="tool" and '5' in m.get("content","") for m in messages)
            return {"choices":[{"message":{"role":"assistant","content":"The verified result is 5."}}]}
    cfg=AppConfig(workspace=str(tmp_path),workspace_roots=[str(tmp_path)],allow_network=False)
    agent=Agent(API(),cfg,confirm=None,log=lambda _:None)
    assert "delegate_tasks" in {tool.name for tool in agent.registry.list()}
    result=await agent.run("Calculate 2+3")
    assert result=="The verified result is 5."
    await agent.close()
