from pathlib import Path
from .discovery import parse_skill

def validate_skill(path:str)->dict:
    p=Path(path).expanduser().resolve(); info=parse_skill(p)
    files=[str(x.relative_to(p)) for x in p.rglob("*") if x.is_file()]
    warnings=[]
    if any(x.endswith((".sh",".py",".js",".bat",".ps1")) for x in files): warnings.append("Contains scripts; inspect them before running. Scripts are never auto-executed.")
    return {"valid":True,"name":info.name,"description":info.description,"files":files,"warnings":warnings}
