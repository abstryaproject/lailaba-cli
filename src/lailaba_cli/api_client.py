from __future__ import annotations
import asyncio, json
from typing import Any
import httpx

class APIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message); self.status_code = status_code

class LailabaAPI:
    """Client for Lailaba AI and OpenAI-compatible chat-completions APIs."""
    def __init__(self, base_url: str, api_key: str, timeout: float = 60, model: str | None = None, provider_name: str = "API provider"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = httpx.Timeout(timeout, connect=min(timeout, 15))
        self._discovered_model: str | None = model.strip() if isinstance(model, str) and model.strip() else None
        self.provider_name = provider_name

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False, verify=True) as client:
                response = await client.request(method, f"{self.base_url}/{path.lstrip('/')}", headers=headers, **kwargs)
        except httpx.TimeoutException: raise APIError(f"The {self.provider_name} request timed out. Check connectivity and retry.") from None
        except httpx.HTTPError as exc: raise APIError(f"Could not connect to {self.provider_name} ({exc.__class__.__name__}). Check connectivity and TLS certificates.") from None
        if response.status_code in (301, 302, 303, 307, 308): raise APIError("The API redirected the request; automatic redirects are disabled for credential safety.", response.status_code)
        if response.status_code == 401: raise APIError("Authentication failed. Check the configured API key.", 401)
        if response.status_code == 403: raise APIError("The API denied access to this resource.", 403)
        if response.status_code == 429: raise APIError("The API rate limit was reached. Wait before retrying.", 429)
        if response.status_code >= 500: raise APIError(f"The {self.provider_name} returned server error HTTP {response.status_code}.", response.status_code)
        if response.status_code >= 400:
            detail = ""
            try: detail = str(response.json().get("error", {}).get("message", ""))[:300]
            except Exception: pass
            raise APIError(f"The API rejected the request (HTTP {response.status_code}). {detail}".strip(), response.status_code)
        try: data = response.json()
        except (ValueError, json.JSONDecodeError): raise APIError("The API returned malformed JSON.") from None
        if not isinstance(data, dict): raise APIError("The API returned an unexpected response format.")
        return data

    async def models(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "models")
        items = data.get("data", data.get("models", []))
        if not isinstance(items, list): raise APIError("The models endpoint response did not contain a model list.")
        return [x for x in items if isinstance(x, dict)]

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, model: str | None = None) -> dict[str, Any]:
        if not model:
            if not self._discovered_model:
                models = await self.models()
                if not models: raise APIError("No models were returned by the API. Verify account access and provider compatibility.")
                self._discovered_model = str(models[0].get("id") or models[0].get("name") or models[0].get("model") or "")
                if not self._discovered_model: raise APIError("Model discovery returned no usable model identifier.")
            model = self._discovered_model
        body: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
        if tools: body["tools"] = tools; body["tool_choice"] = "auto"
        return await self._request("POST", "chat/completions", json=body)

    async def verify(self) -> tuple[bool, str]:
        try:
            models = await self.models()
            return (True, f"Connection verified; {len(models)} model(s) available.") if models else (False, "Connected, but the models endpoint returned no models.")
        except APIError as exc: return False, str(exc)
