from pathlib import Path
import pytest
from lailaba_cli.skills.discovery import parse_skill, discover_skills, load_skill
from lailaba_cli.skills.validator import validate_skill

def test_parse_and_validate_skill(tmp_path):
    d=tmp_path/".lailaba"/"skills"/"python-helper"; d.mkdir(parents=True); (d/"SKILL.md").write_text("---\nname: python-helper\ndescription: Helps debug Python code.\n---\n\nRead before edit.\n")
    info=parse_skill(d); assert info.name=="python-helper"
    assert validate_skill(str(d))["valid"] is True
    _,body=load_skill("python-helper",tmp_path)
    assert "Read before edit" in body

def test_invalid_skill_metadata(tmp_path):
    d=tmp_path/"bad"; d.mkdir(); (d/"SKILL.md").write_text("no metadata")
    with pytest.raises(ValueError): parse_skill(d)

def test_discovery_project_local(tmp_path,monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME",str(tmp_path/"cfg"))
    d=tmp_path/"project"/".lailaba"/"skills"/"hello-skill"; d.mkdir(parents=True)
    (d/"SKILL.md").write_text("---\nname: hello-skill\ndescription: A useful test skill.\n---\nhello")
    assert any(s.name=="hello-skill" for s in discover_skills(tmp_path/"project"))
