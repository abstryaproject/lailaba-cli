import json, os
import pytest
from lailaba_cli import credentials
from lailaba_cli.config import config_home

def test_save_mask_and_no_overwrite(tmp_path,monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path))
    monkeypatch.setenv("LAILABA_API_KEY","")
    monkeypatch.setattr(credentials,"_keyring",lambda:None)
    assert credentials.save_api_key("secret-test-key").startswith("protected")
    assert credentials.get_api_key()=="secret-test-key"
    assert credentials.mask_key("secret-test-key").endswith("-key")
    with pytest.raises(FileExistsError): credentials.save_api_key("different-key")
    if os.name!="nt": assert (config_home()/"credentials.json").stat().st_mode & 0o077 == 0

def test_environment_key_precedes_file(tmp_path,monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path)); monkeypatch.setenv("LAILABA_API_KEY","environment-key")
    assert credentials.get_api_key()=="environment-key"


def test_lailaba_environment_key_is_not_used_for_third_party_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("LAILABA_API_KEY", "lailaba-env-key")
    monkeypatch.delenv("LAILABA_THIRD_PARTY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert credentials.get_api_key("lailaba") == "lailaba-env-key"
    assert credentials.get_api_key("openai-compatible") is None


def test_provider_specific_environment_key_is_supported(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("LAILABA_API_KEY", raising=False)
    monkeypatch.setenv("LAILABA_THIRD_PARTY_API_KEY", "third-party-env-key")
    assert credentials.get_api_key("openai-compatible") == "third-party-env-key"
