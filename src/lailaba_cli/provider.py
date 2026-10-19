from __future__ import annotations
from urllib.parse import urlsplit
import httpx
from .api_client import LailabaAPI
from .config import AppConfig, DEFAULT_API_BASE_URL


def provider_label(cfg: AppConfig) -> str:
    return "Lailaba AI" if cfg.provider == "lailaba" else "OpenAI-compatible provider"


def api_for_config(cfg: AppConfig, api_key: str) -> LailabaAPI:
    base_url = DEFAULT_API_BASE_URL if cfg.provider == "lailaba" else cfg.api_base_url
    model = cfg.model_name.strip() if cfg.provider != "lailaba" and cfg.model_name.strip() else None
    return LailabaAPI(base_url, api_key, model=model, provider_name=provider_label(cfg))


def validate_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    try:
        parts = urlsplit(value)
        _ = parts.port  # forces invalid-port validation
    except ValueError:
        raise ValueError("The URL has an invalid host or port.") from None
    if parts.scheme not in {"https", "http"} or not parts.hostname:
        raise ValueError("Enter a complete API base URL beginning with https:// (or http:// for localhost).")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("The API base URL must not contain credentials, a query string, or a fragment.")
    if parts.scheme == "http" and parts.hostname.lower() not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("HTTPS is required for remote providers so the API key is not sent in plaintext.")
    if not value:
        raise ValueError("The API base URL cannot be empty.")
    return value


def model_ids(models: list[dict]) -> list[str]:
    result = []
    for item in models:
        value = item.get("id") or item.get("name") or item.get("model")
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return list(dict.fromkeys(result))


async def probe_base_url(base_url: str) -> str:
    """Check that /models is reachable before asking the user for a secret.

    Authentication responses are accepted here because the key has not been
    entered yet; redirects are rejected to avoid surprising credential routing.
    """
    endpoint = base_url.rstrip("/") + "/models"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, verify=True) as client:
            response = await client.get(endpoint, headers={"Accept": "application/json"})
    except httpx.TimeoutException:
        raise ValueError("The API endpoint timed out while checking /models.") from None
    except httpx.HTTPError as exc:
        raise ValueError(f"The API endpoint could not be reached ({exc.__class__.__name__}).") from None
    if response.status_code in {301, 302, 303, 307, 308}:
        raise ValueError("The /models endpoint redirected. Enter the final API base URL directly.")
    if response.status_code in {200, 401, 403, 405, 429}:
        return f"Endpoint reachable (HTTP {response.status_code}); authentication will be checked with your API key."
    if response.status_code == 404:
        raise ValueError("The /models endpoint returned HTTP 404. Check that the base URL includes the correct API path, such as /v1.")
    if response.status_code >= 500:
        raise ValueError(f"The provider returned HTTP {response.status_code} before authentication; try again later.")
    raise ValueError(f"The /models endpoint returned unexpected HTTP {response.status_code}.")
