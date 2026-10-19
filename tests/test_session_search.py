import json
from lailaba_cli import sessions


def test_search_sessions_finds_terms(tmp_path, monkeypatch):
    monkeypatch.setattr(sessions, "config_home", lambda: tmp_path)
    root = tmp_path / "sessions"
    root.mkdir()
    (root / "abc.json").write_text(json.dumps({
        "id": "abc", "updated": 10,
        "messages": [{"role": "user", "content": "Build a Lailaba CLI agent"}],
    }), encoding="utf-8")
    result = sessions.search_sessions("lailaba agent")
    assert len(result) == 1
    assert result[0]["id"] == "abc"
