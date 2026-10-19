from __future__ import annotations
import asyncio, ipaddress, socket
from urllib.parse import urlparse, urljoin
import httpx
from html.parser import HTMLParser
from ..config import AppConfig
from ..permissions import PermissionDenied
from .registry import Tool, ToolRegistry, obj_schema

class Extractor(HTMLParser):
    def __init__(self): super().__init__(); self.text=[]; self.links=[]; self._skip=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if tag in {"script","style","noscript","svg"}: self._skip+=1
        if tag=="a" and attrs.get("href"): self.links.append({"text":"","href":attrs["href"]})
    def handle_endtag(self,tag):
        if tag in {"script","style","noscript","svg"} and self._skip: self._skip-=1
    def handle_data(self,data):
        s=data.strip()
        if s and not self._skip: self.text.append(s)
        if s and self.links: self.links[-1]["text"]=(self.links[-1]["text"]+" "+s).strip()[:200]

def validate_url(url: str, allow_private: bool=False) -> str:
    parsed=urlparse(url)
    if parsed.scheme not in {"http","https"} or not parsed.hostname: raise PermissionDenied("Only absolute HTTP/HTTPS URLs are allowed.")
    host=parsed.hostname.lower().rstrip(".")
    if host in {"localhost","metadata.google.internal"} or host.endswith(".localhost") or host.endswith(".local"): raise PermissionDenied("Local and metadata destinations are blocked.")
    try:
        addresses={ipaddress.ip_address(host)}
    except ValueError:
        try: addresses={ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host,parsed.port or (443 if parsed.scheme=="https" else 80),type=socket.SOCK_STREAM)}
        except OSError: raise PermissionDenied("The destination hostname could not be resolved safely.") from None
    if not allow_private and any(not a.is_global for a in addresses): raise PermissionDenied("Private, loopback, link-local, and reserved network destinations are blocked.")
    if parsed.username or parsed.password: raise PermissionDenied("URLs containing embedded credentials are blocked.")
    return url

class WebClient:
    def __init__(self,cfg): self.cfg=cfg
    async def fetch(self,url:str)->dict:
        current=validate_url(url,self.cfg.allow_private_web_destinations)
        for _ in range(4):
            async with httpx.AsyncClient(timeout=httpx.Timeout(15,connect=5),follow_redirects=False,verify=True,headers={"User-Agent":"LailabaCLI/0.1 (+public-page research)"}) as client:
                try: r=await client.get(current)
                except httpx.HTTPError as e: raise RuntimeError(f"Web request failed ({e.__class__.__name__}).") from None
            if r.status_code in {301,302,303,307,308}:
                location=r.headers.get("location")
                if not location: raise RuntimeError("Redirect response had no Location header.")
                current=validate_url(urljoin(current,location),self.cfg.allow_private_web_destinations); continue
            if r.status_code>=400: raise RuntimeError(f"Web server returned HTTP {r.status_code}.")
            if len(r.content)>1_500_000: raise RuntimeError("Web response exceeded the 1.5 MB limit.")
            ctype=r.headers.get("content-type","")
            if not any(t in ctype for t in ("text/html","text/plain","application/xhtml+xml")): raise RuntimeError(f"Unsupported content type: {ctype[:80]}")
            parser=Extractor(); parser.feed(r.text[:1_000_000])
            return {"url":str(r.url),"status_code":r.status_code,"title_or_text":" ".join(parser.text)[:16000],"links":[{"id":i,"text":x["text"],"url":urljoin(str(r.url),x["href"])} for i,x in enumerate(parser.links[:100])],"content_type":ctype}
        raise RuntimeError("Too many redirects.")

def build_web_tools(reg:ToolRegistry,cfg:AppConfig):
    client=WebClient(cfg)
    async def web_fetch(url:str)->dict: return await client.fetch(url)
    async def web_open(url:str)->dict: return await client.fetch(url)
    async def web_extract(url:str)->dict:
        d=await client.fetch(url); return {"url":d["url"],"text":d["title_or_text"]}
    async def web_follow_link(url:str,link_identifier:int)->dict:
        d=await client.fetch(url); links=d["links"]
        if link_identifier<0 or link_identifier>=len(links): raise ValueError("Link identifier not found on page.")
        return await client.fetch(links[link_identifier]["url"])
    async def web_search(query:str)->dict:
        # Honest no-key search via DuckDuckGo HTML, with normal SSRF and redirect checks.
        if not query.strip(): raise ValueError("Search query is required.")
        # Use URL-encoded query parameters with an explicitly safe host request.
        target="https://html.duckduckgo.com/html/"
        validate_url(target,cfg.allow_private_web_destinations)
        async with httpx.AsyncClient(timeout=15,follow_redirects=False,verify=True,headers={"User-Agent":"Mozilla/5.0 (compatible; LailabaCLI/0.1)"}) as c:
            r=await c.get(target,params={"q":query})
        if r.status_code>=400: raise RuntimeError(f"Search provider returned HTTP {r.status_code}.")
        parser=Extractor(); parser.feed(r.text[:1_000_000])
        # Extract anchors from DDG HTML; provider layout may change.
        results=[]
        for link in parser.links:
            href=link["href"]
            if link["text"] and href.startswith("http") and "duckduckgo.com" not in urlparse(href).hostname:
                try: validate_url(href,cfg.allow_private_web_destinations)
                except Exception: continue
                results.append({"title":link["text"],"url":href})
            if len(results)>=10: break
        return {"query":query,"provider":"DuckDuckGo HTML (public, no API key)","results":results,"note":"Search page parsing can change; direct page fetch is not a full search index."}
    if cfg.allow_network:
        reg.register(Tool("web_search","Search public web results using DuckDuckGo HTML; provider markup may change.",obj_schema({"query":{"type":"string"}},["query"]),web_search,timeout=25))
        reg.register(Tool("web_open","Open a public web page and extract readable text and links.",obj_schema({"url":{"type":"string"}},["url"]),web_open,timeout=20))
        reg.register(Tool("web_extract","Fetch a public page and return readable text.",obj_schema({"url":{"type":"string"}},["url"]),web_extract,timeout=20))
        reg.register(Tool("web_fetch","Fetch a public HTTP(S) page with redirect and destination checks.",obj_schema({"url":{"type":"string"}},["url"]),web_fetch,timeout=20))
        reg.register(Tool("web_follow_link","Open a link by its zero-based ID from a page's extracted links.",obj_schema({"url":{"type":"string"},"link_identifier":{"type":"integer","minimum":0}},["url","link_identifier"]),web_follow_link,timeout=20))
