from __future__ import annotations
import asyncio, getpass, os, sys

# Lailaba AI monochrome terminal palette: #000000, #2b2b2b, #ffffff.
# ANSI bright-white and gray text are used on the user's black terminal background.
WHITE = "\033[38;2;255;255;255m"
GRAY_BG = "\033[48;2;43;43;43m"
BLACK_BG = "\033[48;2;0;0;0m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _paint(text: str, *codes: str, enabled: bool = True) -> str:
    if not enabled or not sys.stdout.isatty():
        return text
    return "".join(codes) + text + RESET


def confirm_tool(tool,args):
    print("\n" + _paint("LAILABA AI · PERMISSION REQUEST", BOLD, WHITE))
    print(_paint(f"Tool: {tool.name} · Risk: {tool.risk}", GRAY_BG, WHITE))
    print(f"Arguments: {args}")
    if tool.name in {"write_file","edit_file","create_directory"}:
        print("This may modify workspace files.")
    if tool.name in {"terminal_execute","run_tests"}:
        print("This runs a shell command. Review the command and working directory carefully.")
    answer=input("Allow this action? [y/N] ").strip().lower()
    return answer in {"y","yes"}

async def async_confirm(tool,args): return await asyncio.to_thread(confirm_tool,tool,args)

def hidden_api_key(prompt="Enter API key: ")->str:
    if not sys.stdin.isatty(): raise RuntimeError("No interactive terminal available. Set LAILABA_API_KEY in the environment.")
    return getpass.getpass(prompt).strip()

def banner(workspace,skills,tools,no_color=False,provider="Lailaba AI"):
    use_color = not no_color
    art = r""" _       _ _       _           _        _    ___ 
| | __ _(_) | __ _| |__   __ _| |__  / \  |_ _|
| |/ _` | | |/ _` | '_ \ / _` | '_ \/ _ \  | | 
| | (_| | | | (_| | |_) | (_| | |_) / ___ \ | | 
|_|\__,_|_|_|\__,_|_.__/ \__,_|_.__/_/   \_\___|"""
    print(_paint(art, BLACK_BG, BOLD, WHITE, enabled=use_color))
    print(_paint("YOUR INTELLIGENCE LAYER · PUT INTELLIGENCE TO WORK", GRAY_BG, WHITE, enabled=use_color))
    print(_paint("─" * 64, GRAY_BG, WHITE, enabled=use_color))
    print(f"Workspace  {workspace}")
    print(f"Provider   {provider}")
    print(f"Skills     {skills} available     Tools  {tools} available")
    print(_paint("Type /help for commands · Mutating actions require approval by default.", GRAY_BG, WHITE, enabled=use_color))
    print()

def assistant_prefix(no_color: bool = False) -> str:
    return _paint("Lailaba › ", BOLD, WHITE, enabled=not no_color)
