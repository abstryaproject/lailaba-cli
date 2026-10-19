from __future__ import annotations
import re
from pathlib import Path
from dataclasses import dataclass
from ..config import config_home

@dataclass
class SkillInfo:
    name:str; description:str; path:Path; enabled:bool=True

def parse_skill(path:Path)->SkillInfo:
    file=path/"SKILL.md"
    if not file.is_file(): raise ValueError("Skill directory must contain SKILL.md")
    text=file.read_text(encoding="utf-8")
    if not text.startswith("---\n"): raise ValueError("SKILL.md must start with YAML-like front matter.")
    parts=text.split("---",2)
    if len(parts)<3: raise ValueError("Unclosed skill metadata front matter.")
    metadata={}
    for line in parts[1].splitlines():
        if ":" in line:
            k,v=line.split(":",1); metadata[k.strip()]=v.strip().strip('"\'')
    name=metadata.get("name",""); desc=metadata.get("description","")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}",name): raise ValueError("Skill name must be 2-64 lowercase letters, digits, or hyphens.")
    if not desc or len(desc)>300: raise ValueError("Skill description must be 1-300 characters.")
    return SkillInfo(name,desc,path.resolve())

def discover_skills(workspace:Path|None=None)->list[SkillInfo]:
    dirs=[config_home()/"skills", Path(__file__).resolve().parents[1]/"builtin_skills"]
    if workspace: dirs.insert(0,workspace/".lailaba"/"skills")
    found={}
    for d in dirs:
        if not d.is_dir(): continue
        for p in d.iterdir():
            if p.is_dir():
                try: found[parse_skill(p).name]=parse_skill(p)
                except (ValueError,OSError): continue
    return list(found.values())

def load_skill(name:str,workspace:Path|None=None)->tuple[SkillInfo,str]:
    for s in discover_skills(workspace):
        if s.name==name:
            text=(s.path/"SKILL.md").read_text(encoding="utf-8")
            return s,text.split("---",2)[2].strip()
    raise KeyError(f"Skill not found: {name}")
