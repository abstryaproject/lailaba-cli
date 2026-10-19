from lailaba_cli import memory


def test_memory_add_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "ensure_dirs", lambda: tmp_path)
    (tmp_path / "sessions").mkdir()
    (tmp_path / "skills").mkdir()
    (tmp_path / "logs").mkdir()
    path = memory.add_memory("Prefer concise responses")
    assert path.read_text(encoding="utf-8").strip() == "- Prefer concise responses"
    memory.add_memory("Project is Lailaba CLI")
    assert "Prefer concise responses" in memory.read_memory()
    assert "Project is Lailaba CLI" in memory.read_memory()
    memory.write_memory("")
    assert memory.read_memory() == ""
