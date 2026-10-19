import httpx, pytest
from lailaba_cli.api_client import LailabaAPI, APIError

@pytest.mark.asyncio
async def test_models_and_chat(monkeypatch):
    calls=[]
    class Client:
        def __init__(self,*a,**kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def request(self,method,url,headers,**kwargs):
            calls.append((method,url,headers,kwargs))
            if url.endswith("/models"): return httpx.Response(200,json={"data":[{"id":"test-model"}]},request=httpx.Request(method,url))
            return httpx.Response(200,json={"choices":[{"message":{"role":"assistant","content":"ok"}}]},request=httpx.Request(method,url))
    monkeypatch.setattr(httpx,"AsyncClient",Client)
    api=LailabaAPI("https://example.invalid/api/v1","secret")
    result=await api.chat([{"role":"user","content":"hi"}])
    assert result["choices"][0]["message"]["content"]=="ok"
    assert calls[0][1].endswith("/models") and calls[1][1].endswith("/chat/completions")
    assert calls[0][2]["Authorization"]=="Bearer secret"

@pytest.mark.asyncio
async def test_auth_error(monkeypatch):
    class Client:
        def __init__(self,*a,**kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def request(self,method,url,headers,**kwargs): return httpx.Response(401,json={},request=httpx.Request(method,url))
    monkeypatch.setattr(httpx,"AsyncClient",Client)
    with pytest.raises(APIError,match="Authentication failed"):
        await LailabaAPI("https://example.invalid/api/v1","x").models()

@pytest.mark.asyncio
async def test_explicit_model_skips_models_discovery(monkeypatch):
    calls=[]
    class Client:
        def __init__(self,*a,**kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*a): pass
        async def request(self,method,url,headers,**kwargs):
            calls.append((method,url,kwargs))
            return httpx.Response(200,json={"choices":[{"message":{"role":"assistant","content":"ok"}}]},request=httpx.Request(method,url))
    monkeypatch.setattr(httpx,"AsyncClient",Client)
    api=LailabaAPI("https://example.invalid/v1","secret",model="vendor/model-1",provider_name="test provider")
    await api.chat([{"role":"user","content":"hi"}])
    assert len(calls)==1
    assert calls[0][1].endswith("/chat/completions")
    assert calls[0][2]["json"]["model"]=="vendor/model-1"
