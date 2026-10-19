from pathlib import Path
import shutil
from ..config import config_home
from .discovery import parse_skill

def install_skill(source:str)->Path:
    src=Path(source).expanduser().resolve(); info=parse_skill(src)
    dest=config_home()/"skills"/info.name
    if dest.exists(): raise FileExistsError(f"Skill already exists: {info.name}")
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(src,dest,ignore=shutil.ignore_patterns("__pycache__",".git"))
    return dest
