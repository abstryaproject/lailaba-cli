import json
from pathlib import Path
from lailaba_cli import config

def test_default_endpoint_and_private_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    cfg=config.load_config()
    assert cfg.provider == "lailaba"
    assert cfg.api_base_url == config.DEFAULT_API_BASE_URL
    assert cfg.model_name == ""
    assert "api_key" not in cfg.model_dump()
    path=config.config_home()/"config.json"
    assert path.exists()
    assert "api_key" not in json.loads(path.read_text())
    if __import__('os').name!="nt": assert path.stat().st_mode & 0o077 == 0

def test_cli_has_no_model_selection_option():
    from lailaba_cli.cli import build_parser
    parser=build_parser()
    assert "--model" not in parser.format_help()
    try:
        parser.parse_args(["--model", "some-model"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("CLI must not expose model selection")
