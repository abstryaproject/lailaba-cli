import pytest
from lailaba_cli.config import AppConfig, DEFAULT_API_BASE_URL
from lailaba_cli.provider import api_for_config, model_ids, validate_base_url


def test_default_provider_keeps_lailaba_endpoint_and_automatic_model():
    cfg = AppConfig()
    api = api_for_config(cfg, "secret")
    assert cfg.provider == "lailaba"
    assert api.base_url == DEFAULT_API_BASE_URL
    assert api._discovered_model is None


def test_openai_compatible_provider_uses_saved_url_and_model():
    cfg = AppConfig(provider="openai-compatible", api_base_url="https://api.example.com/v1", model_name="example-model")
    api = api_for_config(cfg, "secret")
    assert api.base_url == "https://api.example.com/v1"
    assert api._discovered_model == "example-model"
    assert api.provider_name == "OpenAI-compatible provider"


@pytest.mark.parametrize("url", ["https://api.example.com/v1", "http://localhost:8000/v1", "http://127.0.0.1:1234/v1"])
def test_valid_base_urls(url):
    assert validate_base_url(url) == url


@pytest.mark.parametrize("url", ["", "api.example.com/v1", "ftp://api.example.com", "http://api.example.com/v1", "https://user:pass@example.com/v1", "https://example.com/v1?secret=x", "https://example.com:bad/v1"])
def test_rejects_unsafe_or_invalid_base_urls(url):
    with pytest.raises(ValueError):
        validate_base_url(url)


def test_model_ids_extracts_common_identifiers():
    assert model_ids([{"id": "one"}, {"name": "two"}, {"model": "three"}, {"id": "one"}, {}]) == ["one", "two", "three"]


def test_setup_wizard_configures_third_party_only_after_key_and_model_validation(monkeypatch):
    import asyncio
    from lailaba_cli import cli
    cfg = AppConfig()
    saved = {}
    answers = iter(["https://api.vendor.example/v1", "vendor-model"])
    monkeypatch.setattr(cli, "load_config", lambda: cfg)
    monkeypatch.setattr(cli, "get_api_key", lambda *args: None)
    monkeypatch.setattr(cli, "_yes", lambda *a, **kw: False)
    async def probe(url):
        assert url == "https://api.vendor.example/v1"
        return "Endpoint reachable (HTTP 401); authentication will be checked with your API key."
    monkeypatch.setattr(cli, "probe_base_url", probe)
    monkeypatch.setattr(cli, "hidden_api_key", lambda *a, **kw: "valid-test-key")
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    async def models(self):
        assert self.api_key == "valid-test-key"
        assert self.base_url == "https://api.vendor.example/v1"
        return [{"id": "vendor-model"}, {"id": "other-model"}]
    monkeypatch.setattr("lailaba_cli.api_client.LailabaAPI.models", models)
    monkeypatch.setattr(cli, "save_api_key", lambda key, overwrite=False, provider=None: saved.update(key=key, provider=provider) or "test store")
    monkeypatch.setattr(cli, "save_config", lambda new_cfg: saved.update(config=new_cfg))
    assert asyncio.run(cli.setup_flow()) == 0
    assert saved["key"] == "valid-test-key"
    assert saved["config"].provider == "openai-compatible"
    assert saved["config"].api_base_url == "https://api.vendor.example/v1"
    assert saved["config"].model_name == "vendor-model"
