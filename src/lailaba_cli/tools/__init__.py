from .registry import Tool, ToolRegistry
from .filesystem import build_filesystem_tools
from .terminal import build_terminal_tools
from .web import build_web_tools
from .git import build_git_tools
from .utilities import build_utility_tools
from .agent_features import build_agent_feature_tools

def build_registry(cfg):
    registry=ToolRegistry()
    build_filesystem_tools(registry,cfg)
    build_terminal_tools(registry,cfg)
    build_web_tools(registry,cfg)
    build_git_tools(registry,cfg)
    build_utility_tools(registry)
    build_agent_feature_tools(registry,cfg)
    return registry
