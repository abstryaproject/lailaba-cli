from __future__ import annotations
import ast, operator, platform, datetime, os
from .registry import Tool, ToolRegistry, obj_schema

_ALLOWED={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv,ast.FloorDiv:operator.floordiv,ast.Mod:operator.mod,ast.Pow:operator.pow,ast.USub:operator.neg,ast.UAdd:operator.pos}
def safe_calculate(expression:str):
    if len(expression)>200: raise ValueError("Expression too long.")
    tree=ast.parse(expression,mode="eval")
    def ev(n):
        if isinstance(n,ast.Expression): return ev(n.body)
        if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)) and not isinstance(n.value,bool): return n.value
        if isinstance(n,ast.BinOp) and type(n.op) in _ALLOWED:
            if isinstance(n.op,ast.Pow) and abs(ev(n.right))>10: raise ValueError("Exponent too large.")
            result=_ALLOWED[type(n.op)](ev(n.left),ev(n.right))
            if abs(result)>1e100: raise ValueError("Result too large.")
            return result
        if isinstance(n,ast.UnaryOp) and type(n.op) in _ALLOWED: return _ALLOWED[type(n.op)](ev(n.operand))
        raise ValueError("Only basic arithmetic is supported.")
    return ev(tree)

def build_utility_tools(reg:ToolRegistry):
    async def get_current_time()->dict: return {"local":datetime.datetime.now().astimezone().isoformat(),"utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    async def calculate(expression:str)->dict: return {"expression":expression,"result":safe_calculate(expression)}
    async def inspect_environment()->dict: return {"platform":platform.platform(),"python":platform.python_version(),"cwd":os.getcwd()}
    reg.register(Tool("get_current_time","Get current local and UTC time.",obj_schema({}),get_current_time))
    reg.register(Tool("calculate","Evaluate basic numeric arithmetic without executing code.",obj_schema({"expression":{"type":"string"}},["expression"]),calculate))
    reg.register(Tool("inspect_environment","Inspect basic platform metadata; does not reveal environment variables.",obj_schema({}),inspect_environment))
