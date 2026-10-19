from __future__ import annotations
import json
from pathlib import Path
from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Static, RichLog, Input, Button, Label
from textual import work
from ..config import AppConfig, config_home
from ..credentials import mask_key
from ..provider import provider_label
from ..memory import read_memory, memory_path
from ..tasks import list_tasks
from ..checkpoints import list_checkpoints
from ..skills import discover_skills


class PermissionScreen(ModalScreen[bool]):
    CSS = """
    PermissionScreen { align: center middle; background: #000000 80%; }
    #permission-box { width: 80%; max-width: 90; height: auto; border: round #ffffff; background: #000000; padding: 1 2; }
    #permission-title { color: #ffffff; text-style: bold; padding-bottom: 1; }
    #permission-details { color: #ffffff; background: #2b2b2b; padding: 1; height: auto; max-height: 12; }
    #permission-actions { height: 3; align: right middle; padding-top: 1; }
    Button { margin-left: 1; background: #2b2b2b; color: #ffffff; }
    #allow { background: #ffffff; color: #000000; }
    """

    def __init__(self, tool_name: str, args: dict):
        super().__init__()
        self.tool_name = tool_name
        self.args = args

    def compose(self) -> ComposeResult:
        with Vertical(id="permission-box"):
            yield Label("LAILABA CLI · PERMISSION REQUEST", id="permission-title")
            yield Static(f"Tool: {self.tool_name}\n\nArguments:\n{json.dumps(self.args, indent=2, ensure_ascii=False)[:5000]}", id="permission-details")
            with Horizontal(id="permission-actions"):
                yield Button("Reject", id="reject", variant="default")
                yield Button("Approve", id="allow", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "allow")


class LailabaAgentApp(App[None]):
    TITLE = "Lailaba CLI"
    SUB_TITLE = "Your Intelligence Layer"
    CSS = """
    Screen { background: #000000; color: #ffffff; }
    Header { background: #2b2b2b; color: #ffffff; }
    Footer { background: #2b2b2b; color: #ffffff; }
    #main { height: 1fr; padding: 0 1; }
    #status { height: auto; min-height: 3; border: round #2b2b2b; padding: 0 1; margin-bottom: 1; color: #ffffff; }
    #conversation { height: 1fr; border: round #2b2b2b; background: #000000; padding: 0 1; }
    #input-row { height: 3; margin-top: 1; }
    #task-input { width: 1fr; border: round #2b2b2b; background: #000000; color: #ffffff; }
    #hint { height: 1; color: #ffffff; background: #2b2b2b; padding-left: 1; }
    """
    BINDINGS = [("ctrl+c", "interrupt_task", "Interrupt"), ("ctrl+l", "clear_log", "Clear"), ("ctrl+d", "quit", "Exit")]

    def __init__(self, agent, cfg: AppConfig, api_key: str, api_status: str):
        super().__init__()
        self.agent = agent
        self.cfg = cfg
        self.api_key = api_key
        self.api_status = api_status
        self.busy = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main"):
            yield Static("LAILABA CLI  ·  AUTONOMOUS AGENT", id="status")
            yield RichLog(id="conversation", wrap=True, markup=False, highlight=False, auto_scroll=True)
            with Horizontal(id="input-row"):
                yield Input(placeholder="Describe a task for the agent…  (try /help)", id="task-input")
            yield Static("/help  /tools  /skills  /status  /memory  /tasks  /checkpoints  /exit", id="hint")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_status()
        log = self.query_one("#conversation", RichLog)
        log.write("Lailaba CLI — autonomous agent ready.")
        log.write(f"Workspace: {self.cfg.workspace}")
        log.write("Describe an outcome to achieve. The agent can inspect, plan, and use tools; risky actions require approval.")
        self.query_one("#task-input", Input).focus()

    def refresh_status(self) -> None:
        try:
            skills = len(discover_skills(Path(self.cfg.workspace)))
        except Exception:
            skills = 0
        text = (f"Provider: {provider_label(self.cfg)}  ·  API: connected  ·  Key: {mask_key(self.api_key)}\n"
                f"Workspace: {self.cfg.workspace}  ·  Skills: {skills}  ·  State: {'WORKING' if self.busy else 'READY'}")
        self.query_one("#status", Static).update(text)

    def write_log(self, message: str) -> None:
        try:
            self.query_one("#conversation", RichLog).write(str(message))
        except Exception:
            pass

    async def confirm_action(self, tool, args) -> bool:
        return bool(await self.push_screen_wait(PermissionScreen(tool.name, args)))

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text or self.busy:
            return
        lower = text.lower()
        if lower in {"/exit", "/quit"}:
            self.exit()
            return
        if lower == "/clear":
            self.query_one("#conversation", RichLog).clear()
            return
        if lower == "/help":
            self.write_log("Commands: /help, /exit, /clear, /tools, /skills, /status, /workspace, /permissions, /memory, /tasks, /checkpoints, /new, /doctor.\nUse natural language to delegate work to the agent.")
            return
        if lower == "/tools":
            for tool in self.agent.registry.list():
                self.write_log(f"{tool.name} — {tool.description} [risk={tool.risk}{', approval required' if tool.confirmation else ''}]")
            return
        if lower in {"/skills", "/skills list"}:
            for skill in discover_skills(Path(self.cfg.workspace)):
                self.write_log(f"{skill.name} — {skill.description}")
            return
        if lower == "/status":
            self.write_log(f"Provider: {provider_label(self.cfg)}\nAPI: {self.api_status}\nWorkspace: {self.cfg.workspace}")
            return
        if lower == "/workspace":
            self.write_log(self.cfg.workspace); return
        if lower == "/permissions":
            self.write_log(json.dumps({"allow_writes": self.cfg.allow_writes, "allow_shell": self.cfg.allow_shell, "allow_network": self.cfg.allow_network, "confirm_writes": self.cfg.require_confirmation_for_writes, "confirm_shell": self.cfg.require_confirmation_for_shell, "confirm_installs": self.cfg.require_confirmation_for_installs, "confirm_deletes": self.cfg.require_confirmation_for_deletes}, indent=2)); return
        if lower == "/memory":
            self.write_log(read_memory() or f"Persistent memory is empty. File: {memory_path()}"); return
        if lower == "/tasks":
            items = list_tasks(self.cfg.workspace)
            self.write_log("No workspace tasks." if not items else "\n".join(f"[{ 'x' if t.get('done') else ' ' }] {t['id']} {t['title']}" for t in items)); return
        if lower == "/checkpoints":
            items = list_checkpoints(self.cfg.workspace)
            self.write_log("No file checkpoints." if not items else "\n".join(f"{x['id']}  {x['path']}" for x in items)); return
        if lower == "/new":
            from ..sessions import Session
            self.agent.session = Session()
            self.write_log(f"Started a new session: {self.agent.session.id}"); return
        if lower == "/doctor":
            self.write_log(f"Python environment: available\nConfig: {config_home()}\n{self.api_status}"); return
        if lower.startswith("/"):
            self.write_log(f"Unknown or unsupported TUI command: {text}. Try /help."); return
        self.write_log(f"\nYou › {text}")
        self.busy = True
        self.refresh_status()
        self.query_one("#task-input", Input).disabled = True
        self.process_task(text)

    @work(exclusive=True, group="agent", exit_on_error=False)
    async def process_task(self, task: str) -> None:
        try:
            self.agent.confirm = self.confirm_action
            answer = await self.agent.run(task)
            self.write_log(f"\nLailaba › {answer}")
        except Exception as exc:
            self.write_log(f"\n[error] {exc.__class__.__name__}: {str(exc)[:600]}")
        finally:
            self.busy = False
            self.refresh_status()
            self.query_one("#task-input", Input).disabled = False
            self.query_one("#task-input", Input).focus()

    async def on_unmount(self) -> None:
        await self.agent.close()

    def action_clear_log(self) -> None:
        self.query_one("#conversation", RichLog).clear()

    def action_interrupt_task(self) -> None:
        if self.busy:
            self.write_log("Interrupt requested. The current bounded tool call may finish before the agent stops.")
            self.agent.cancelled = True


async def run_textual(agent, cfg: AppConfig, api_key: str, api_status: str) -> int:
    app = LailabaAgentApp(agent, cfg, api_key, api_status)
    await app.run_async()
    return 0
