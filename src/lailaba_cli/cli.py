from __future__ import annotations
import argparse, asyncio, getpass, json, os, sys, time, shlex
from pathlib import Path
from . import __version__
from .config import load_config, save_config, config_home, ensure_dirs, AppConfig, DEFAULT_API_BASE_URL
from .provider import api_for_config, provider_label, validate_base_url, probe_base_url, model_ids
from .credentials import get_api_key, save_api_key, delete_api_key, mask_key
from .api_client import LailabaAPI, APIError
from .agent import Agent
from .ui.terminal_ui import async_confirm, hidden_api_key, banner
from .skills import discover_skills, load_skill, validate_skill, install_skill
from .sessions import recent_sessions, search_sessions, Session
from .memory import read_memory, write_memory, add_memory, memory_path
from .scheduler import add_job, list_jobs, remove_job, due_jobs, record_job

HELP_TEXT="""Interactive commands:
  /help             Show help
  /exit, /quit      Exit
  /clear            Clear the screen
  /tools            List available tools
  /skills [list]    List available skills
  /skills show NAME Show skill instructions
  /status           Show connection and workspace status
  /workspace        Show workspace path
  /permissions      Show configured permission policy
  /history          List recent sessions
  /search TEXT      Search saved session history
  /resume ID        Resume a saved session
  /new              Start a fresh conversation
  /memory           Show persistent memory
  /memory add TEXT  Add a memory note
  /memory clear     Clear persistent memory
  /tasks            Show the persistent workspace task list
  /checkpoints      List automatic file checkpoints
  /rollback [ID]   Restore the latest or a selected checkpoint
  @file:path        Include a file in a request (example: @file:src/main.py)
  @folder:path      Include a folder listing in a request
  @git-diff         Include the current Git diff in a request
  /config           Show non-secret configuration
  /plan             Ask the agent to plan a task before execution
  /doctor           Run local and API diagnostics
"""

def build_parser():
    p=argparse.ArgumentParser(prog="lailaba-cli",description="Lailaba AI autonomous terminal agent")
    p.add_argument("--version",action="version",version=f"lailaba-cli {__version__}")
    p.add_argument("--workspace",type=Path,help="Workspace root (default: current directory)")
    p.add_argument("--no-color",action="store_true",help="Disable color output")
    p.add_argument("--debug",action="store_true",help="Enable verbose local diagnostics (secrets are redacted)")
    sub=p.add_subparsers(dest="command")
    setup=sub.add_parser("setup",help="Configure Lailaba CLI")
    setup_sub=setup.add_subparsers(dest="setup_command")
    setup_sub.add_parser("key",help="Set or change the provider and API key")
    setup_sub.add_parser("provider",help="Configure Lailaba AI or an OpenAI-compatible provider")
    provider_cmd=sub.add_parser("provider",help="Show or configure the active API provider").add_subparsers(dest="provider_command")
    provider_cmd.add_parser("show",help="Show active provider settings")
    provider_cmd.add_parser("setup",help="Configure the API provider and credentials")
    auth=sub.add_parser("auth",help="Manage authentication").add_subparsers(dest="auth_command")
    auth.add_parser("status",help="Show masked API key status")
    auth.add_parser("logout",help="Delete the stored API key")
    auth.add_parser("login",help="Change the stored API key")
    skills=sub.add_parser("skills",help="Manage skills").add_subparsers(dest="skills_command")
    skills.add_parser("list",help="List discovered skills")
    show=skills.add_parser("show",help="Show a skill's instructions"); show.add_argument("name")
    val=skills.add_parser("validate",help="Validate a local skill directory"); val.add_argument("path")
    ins=skills.add_parser("install",help="Install a trusted local skill directory"); ins.add_argument("path")
    dis=skills.add_parser("disable",help="Disable a skill"); dis.add_argument("name")
    en=skills.add_parser("enable",help="Enable a skill"); en.add_argument("name")
    sub.add_parser("doctor",help="Check installation, credentials, API connectivity, and workspace")
    sub.add_parser("info",help="Show agent capabilities and local paths")
    run=sub.add_parser("run",help="Run an autonomous task and exit"); run.add_argument("task",nargs="+",help="Task instructions for the agent")
    sub.add_parser("tools",help="List available agent tools")
    sub.add_parser("permissions",help="Show the current safety and permission policy")
    sub.add_parser("tasks",help="List persistent tasks for the current workspace")
    sub.add_parser("checkpoints",help="List file checkpoints for the current workspace")
    memory=sub.add_parser("memory",help="Manage persistent agent memory").add_subparsers(dest="memory_command")
    memory.add_parser("show",help="Show persistent memory")
    memadd=memory.add_parser("add",help="Add a persistent memory note"); memadd.add_argument("text",nargs="+")
    memory.add_parser("clear",help="Clear persistent memory after confirmation")
    sessions=sub.add_parser("sessions",help="Inspect saved agent sessions").add_subparsers(dest="sessions_command")
    mcp=sub.add_parser("mcp",help="Manage explicitly configured MCP servers").add_subparsers(dest="mcp_command")
    mcp.add_parser("list",help="List configured MCP servers")
    madd=mcp.add_parser("add",help="Configure an MCP stdio server")
    madd.add_argument("name"); madd.add_argument("--command",dest="server_command",required=True); madd.add_argument("--args-json",default="[]",help="JSON array of command arguments")
    mremove=mcp.add_parser("remove",help="Remove an MCP server configuration"); mremove.add_argument("name")
    mtest=mcp.add_parser("test",help="Connect to an MCP server and list its tools"); mtest.add_argument("name")
    schedule=sub.add_parser("schedule",help="Manage recurring autonomous tasks").add_subparsers(dest="schedule_command")
    schedule.add_parser("list",help="List scheduled jobs")
    sadd=schedule.add_parser("add",help="Add a recurring task")
    sadd.add_argument("--every-minutes",type=int,required=True); sadd.add_argument("--task",required=True)
    sremove=schedule.add_parser("remove",help="Remove a scheduled task"); sremove.add_argument("id")
    schedule.add_parser("run-due",help="Run currently due jobs once")
    daemon=schedule.add_parser("daemon",help="Keep checking and executing scheduled tasks"); daemon.add_argument("--poll-seconds",type=int,default=30)
    sessions.add_parser("list",help="List recent sessions")
    sesssearch=sessions.add_parser("search",help="Search saved sessions"); sesssearch.add_argument("query",nargs="+")
    return p

def _yes(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


async def setup_flow(change=False):
    cfg = load_config()
    current_key = get_api_key(cfg.provider)
    if current_key:
        print(f"Current provider: {provider_label(cfg)} | API key: {mask_key(current_key)}")
        if _yes("Continue with the existing provider and API key?", default=True):
            ok, msg = await api_for_config(cfg, current_key).verify()
            print(msg)
            if ok:
                print("Lailaba CLI is ready.")
                return 0
            print("The current configuration could not be verified.")
            if not _yes("Reconfigure the provider or API key now?", default=False):
                return 1
    use_lailaba = _yes("Continue with the Lailaba AI provider?", default=True)
    if use_lailaba:
        base_url = DEFAULT_API_BASE_URL
        provider = "lailaba"
        model_name = ""
        label = "Lailaba AI"
    else:
        provider = "openai-compatible"
        label = "third-party OpenAI-compatible provider"
        while True:
            raw_url = input("Third-party API base URL (for example, https://api.example.com/v1): ").strip()
            try:
                base_url = validate_base_url(raw_url)
                print(await probe_base_url(base_url))
                break
            except ValueError as exc:
                print(f"Invalid API URL: {exc}")

    new_key = ""
    api = None
    available_models: list[dict] = []
    for attempt in range(3):
        try:
            new_key = hidden_api_key("Enter API key: ")
        except RuntimeError as exc:
            print(str(exc)); return 2
        if not new_key:
            print("No API key entered; nothing saved.")
            return 2
        api = LailabaAPI(base_url, new_key, provider_name=label)
        try:
            available_models = await api.models()
            ids = model_ids(available_models)
            if not ids:
                print("The provider returned no usable model IDs from its /models endpoint.")
                print("Use a provider that supports the OpenAI-compatible /models and /chat/completions endpoints.")
                return 1
            print(f"API key verified; {len(ids)} model(s) available.")
            break
        except APIError as exc:
            print(f"API key or endpoint validation failed: {exc}")
            if attempt < 2 and _yes("Try another API key?", default=True):
                continue
            return 1
    else:
        return 1

    if provider == "openai-compatible":
        ids = model_ids(available_models)
        print("Available models: " + ", ".join(ids[:30]))
        while True:
            model_name = input("Model name to use: ").strip()
            if model_name in ids:
                break
            print("That model name was not returned by the provider's /models endpoint. Enter one of the listed IDs.")
        # The model is checked against the authenticated /models response before saving.
        api = LailabaAPI(base_url, new_key, model=model_name, provider_name=label)

    new_cfg = cfg
    new_cfg.provider = provider
    new_cfg.api_base_url = base_url
    new_cfg.model_name = model_name
    try:
        storage = save_api_key(new_key, overwrite=bool(current_key), provider=provider)
        save_config(new_cfg)
    except Exception as exc:
        print(f"Could not save provider configuration: {exc}")
        return 2
    print(f"Provider configured: {label}.")
    print(f"API key saved securely using {storage}.")
    print("Lailaba CLI is ready.")
    return 0

def print_skills(cfg):
    skills=discover_skills(Path(cfg.workspace))
    if not skills: print("No valid skills found."); return
    for s in skills: print(f"- {s.name}: {s.description} [{s.path}]")

async def interactive(args,cfg):
    key=get_api_key(cfg.provider)
    if not key:
        print("Welcome to Lailaba CLI\nYour AI agent in the terminal.\n\nLailaba CLI is not configured yet.")
        return await setup_flow()
    api=api_for_config(cfg,key)
    ok,msg=await api.verify()
    if not ok:
        print(f"Connection check failed: {msg}\nUse `lailaba-cli setup key` to retry."); return 1
    from .tools import build_registry
    registry=build_registry(cfg)
    agent=Agent(api,cfg,confirm=async_confirm,log=print)
    if sys.stdin.isatty() and sys.stdout.isatty() and not args.no_color:
        try:
            from .ui.textual_app import run_textual
            return await run_textual(agent, cfg, key, msg)
        except ImportError:
            print("Textual UI is unavailable; using the basic terminal interface.")
    banner(cfg.workspace,len(discover_skills(Path(cfg.workspace))),len(registry.list()),args.no_color,provider_label(cfg))
    while True:
        try: line=input("You> ").strip()
        except (EOFError,KeyboardInterrupt): print("\nGoodbye."); break
        if not line: continue
        cmd=line.lower()
        if cmd in {"/exit","/quit"}: break
        if cmd=="/help": print(HELP_TEXT); continue
        if cmd=="/clear": os.system("cls" if os.name=="nt" else "clear"); continue
        if cmd=="/tools":
            for t in agent.registry.list(): print(f"- {t.name}: {t.description} [risk={t.risk}{', confirmation' if t.confirmation else ''}]")
            continue
        if cmd=="/skills" or cmd=="/skills list": print_skills(cfg); continue
        if cmd.startswith("/skills show "):
            try:
                info,body=load_skill(line.split(None,2)[2],Path(cfg.workspace)); print(f"# {info.name}\n{info.description}\n\n{body}")
            except Exception as exc: print(f"Could not load skill: {exc}")
            continue
        if cmd=="/workspace": print(cfg.workspace); continue
        if cmd=="/status": print(f"Provider: {provider_label(cfg)}\nAPI key: {mask_key(key)}\n{msg}\nWorkspace: {cfg.workspace}"); continue
        if cmd=="/permissions": print(json.dumps({"allow_writes":cfg.allow_writes,"allow_shell":cfg.allow_shell,"allow_network":cfg.allow_network,"confirm_writes":cfg.require_confirmation_for_writes,"confirm_shell":cfg.require_confirmation_for_shell,"confirm_installs":cfg.require_confirmation_for_installs,"confirm_deletes":cfg.require_confirmation_for_deletes,"workspace_roots":[str(p) for p in cfg.roots]},indent=2)); continue
        if cmd=="/config":
            print(json.dumps({k:v for k,v in cfg.model_dump().items() if k not in {"api_key","credentials"}},indent=2)); continue
        if cmd=="/doctor":
            print(f"Python: {sys.version.split()[0]}\nPlatform: {sys.platform}\nWorkspace exists: {Path(cfg.workspace).is_dir()}\nConfig directory: {config_home()}\nAPI: {msg}")
            continue
        if cmd.startswith("/plan "):
            line = "Create a step-by-step plan for this task. Do not execute tools or modify anything yet: " + line[len("/plan "):]
        if cmd=="/history":
            sessions = recent_sessions()
            if not sessions: print("No saved sessions yet.")
            for s in sessions: print(f"- {s['id']} ({s['path']})")
            continue
        if line.startswith("/search "):
            query=line.split(None,1)[1].strip()
            results=search_sessions(query)
            if not results: print("No matching saved sessions.")
            for item in results: print(f"- {item['id']}: {item['excerpt']}")
            continue
        if line.startswith("/resume "):
            session_id=line.split(None,1)[1].strip()
            try:
                agent.session=Session.load(session_id)
                print(f"Resumed session {session_id} ({len(agent.session.messages)} messages).")
            except Exception as exc: print(f"Could not resume session: {exc}")
            continue
        if cmd=="/new":
            agent.session=Session()
            print(f"Started a new conversation ({agent.session.id}).")
            continue
        if cmd=="/memory":
            content=read_memory()
            print(content if content else f"Persistent memory is empty. File: {memory_path()}")
            continue
        if line.startswith("/memory add "):
            note=line[len("/memory add "):].strip()
            try: print(f"Memory note saved to {add_memory(note)}")
            except Exception as exc: print(f"Could not save memory: {exc}")
            continue
        if cmd=="/memory clear":
            answer=input("Clear all persistent memory notes? [y/N] ").strip().lower()
            if answer in {"y","yes"}:
                try: write_memory(""); print("Persistent memory cleared.")
                except Exception as exc: print(f"Could not clear memory: {exc}")
            else: print("Memory unchanged.")
            continue
        if cmd=="/tasks":
            from .tasks import list_tasks
            tasks=list_tasks(cfg.workspace)
            if not tasks: print("No workspace tasks yet.")
            for task in tasks: print(f"[{ 'x' if task.get('done') else ' ' }] {task['id']}  {task['title']}")
            continue
        if cmd=="/checkpoints":
            from .checkpoints import list_checkpoints
            items=list_checkpoints(cfg.workspace)
            if not items: print("No checkpoints yet. File checkpoints are created before agent writes/edits.")
            for item in items: print(f"- {item['id']}  {item['path']}")
            continue
        if cmd=="/rollback" or cmd.startswith("/rollback "):
            from .checkpoints import rollback_checkpoint
            checkpoint_id=line.split(None,1)[1].strip() if len(line.split(None,1))>1 else None
            try:
                print("This will restore a file to its saved checkpoint.")
                answer=input("Continue? [y/N] ").strip().lower()
                if answer in {"y","yes"}:
                    result=rollback_checkpoint(checkpoint_id,cfg.workspace,cfg.roots)
                    print(f"Checkpoint {result['id']} applied to {result['path']}.")
                else: print("Rollback cancelled.")
            except Exception as exc: print(f"Rollback failed: {exc}")
            continue
        print("Lailaba>",end=" ",flush=True)
        try:
            answer=await agent.run(line)
            print(answer)
        except KeyboardInterrupt:
            print("\nTask interrupted. Any active subprocess is cleaned up by the tool executor.")
        except Exception as exc:
            print(f"\n[error] {exc.__class__.__name__}: {str(exc)[:500]}")
    await agent.close()
    return 0

def _show_permissions(cfg):
    print(json.dumps({"allow_writes":cfg.allow_writes,"allow_shell":cfg.allow_shell,"allow_network":cfg.allow_network,"confirm_writes":cfg.require_confirmation_for_writes,"confirm_shell":cfg.require_confirmation_for_shell,"confirm_installs":cfg.require_confirmation_for_installs,"confirm_deletes":cfg.require_confirmation_for_deletes,"workspace_roots":[str(p) for p in cfg.roots]},indent=2))

async def _run_task(args, cfg):
    key=get_api_key(cfg.provider)
    if not key:
        print("Lailaba AI API key is not configured. Run: lailaba-cli setup key",file=sys.stderr)
        return 2
    api=api_for_config(cfg,key)
    ok,msg=await api.verify()
    if not ok:
        print(f"Lailaba API connection failed: {msg}",file=sys.stderr); return 1
    agent=Agent(api,cfg,confirm=async_confirm,log=print)
    try:
        result=await agent.run(" ".join(args.task))
        print(result)
        return 0
    except KeyboardInterrupt:
        print("\nTask interrupted.",file=sys.stderr); return 130
    except Exception as exc:
        print(f"Agent task failed: {exc.__class__.__name__}: {str(exc)[:500]}",file=sys.stderr); return 1
    finally:
        await agent.close()

async def _execute_scheduled_job(job):
    cfg=load_config()
    key=get_api_key(cfg.provider)
    if not key:
        print("Scheduled job skipped: configure an API key with `lailaba-cli setup key`.",file=sys.stderr); record_job(job["id"],False); return False
    workspace=Path(job.get("workspace",cfg.workspace)).expanduser().resolve()
    if not workspace.is_dir():
        print(f"Scheduled job {job['id']} skipped: workspace does not exist: {workspace}",file=sys.stderr); record_job(job["id"],False); return False
    cfg.workspace=str(workspace); cfg.workspace_roots=[str(workspace)]
    agent=Agent(api_for_config(cfg,key),cfg,confirm=async_confirm,log=print)
    try:
        print(f"[schedule] Running {job['id']}: {job['task']}")
        result=await agent.run(job["task"]); print(result); record_job(job["id"],True); return True
    except Exception as exc:
        print(f"[schedule:error] {job['id']}: {exc.__class__.__name__}: {str(exc)[:300]}",file=sys.stderr); record_job(job["id"],False); return False
    finally: await agent.close()

async def _schedule_dispatch(args,cfg):
    if args.schedule_command in (None,"list"):
        jobs=list_jobs()
        if not jobs: print("No scheduled jobs configured.")
        for j in jobs: print(f"- {j['id']} every {j['every_minutes']}m | next={time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(j['next_run_at']))} | {j['last_status']} | {j['task']}")
        return 0
    if args.schedule_command=="add":
        try:
            item=add_job(args.task,args.every_minutes,cfg.workspace)
            print(f"Scheduled job {item['id']} created. It will first run in {item['every_minutes']} minute(s). Start the worker with `lailaba-cli schedule daemon`."); return 0
        except Exception as exc: print(f"Could not create scheduled job: {exc}",file=sys.stderr); return 2
    if args.schedule_command=="remove":
        if remove_job(args.id): print(f"Removed scheduled job {args.id}."); return 0
        print(f"No scheduled job found with ID {args.id}.",file=sys.stderr); return 1
    if args.schedule_command in ("run-due","daemon"):
        if args.schedule_command=="daemon" and not 1<=args.poll_seconds<=3600: print("--poll-seconds must be between 1 and 3600",file=sys.stderr); return 2
        async def tick():
            jobs=due_jobs()
            for job in jobs: await _execute_scheduled_job(job)
        if args.schedule_command=="run-due": await tick(); return 0
        print("Lailaba scheduler running. Press Ctrl+C to stop.")
        try:
            while True: await tick(); await asyncio.sleep(args.poll_seconds)
        except KeyboardInterrupt: print("\nScheduler stopped."); return 0
    return 2

async def _list_tools(cfg):
    from .tools import build_registry
    from .mcp import MCPManager
    registry=build_registry(cfg); manager=MCPManager(cfg.mcp_servers)
    try:
        await manager.load_into(registry,log=lambda msg: print(msg))
        for tool in registry.list(): print(f"- {tool.name}: {tool.description} [risk={tool.risk}{', confirmation' if tool.confirmation else ''}]")
        return 0
    finally: await manager.close()

async def _mcp_test(name,cfg):
    from .mcp import MCPServer
    item=next((x for x in cfg.mcp_servers if x.get("name")==name),None)
    if not item: print(f"MCP server {name!r} is not configured.",file=sys.stderr); return 1
    server=MCPServer(item["name"],item["command"],item.get("args",[]))
    try:
        await server.start(); print(f"Connected to {name}; {len(server.tools)} tool(s) available.")
        for tool in server.tools: print(f"- {tool.get('name')}: {str(tool.get('description',''))[:200]}")
        return 0
    except Exception as exc: print(f"MCP connection failed: {exc.__class__.__name__}: {str(exc)[:500]}",file=sys.stderr); return 1
    finally: await server.close()

def main(argv=None):
    parser=build_parser(); args=parser.parse_args(argv)
    try: cfg=load_config()
    except Exception as exc: print(str(exc),file=sys.stderr); return 2
    if args.workspace:
        workspace=args.workspace.expanduser().resolve(); workspace.mkdir(parents=True,exist_ok=True)
        cfg.workspace=str(workspace); cfg.workspace_roots=[str(workspace)]; save_config(cfg)
    elif not cfg.workspace_roots and not (config_home()/"config.json").exists():
        cfg.workspace=str(Path.cwd().resolve())

    if args.command=="setup":
        return asyncio.run(setup_flow(change=True)) if args.setup_command in {"key", "provider"} else asyncio.run(setup_flow())
    if args.command=="provider":
        if args.provider_command == "setup": return asyncio.run(setup_flow(change=True))
        if args.provider_command in (None, "show"):
            print(f"Provider: {provider_label(cfg)}")
            print(f"API base URL: {cfg.api_base_url if cfg.provider != 'lailaba' else DEFAULT_API_BASE_URL}")
            print(f"Model: {cfg.model_name or 'automatic discovery'}")
            print(f"API key: {mask_key(get_api_key(cfg.provider))}")
            return 0
    if args.command=="auth":
        if args.auth_command=="status": print(f"API key: {mask_key(get_api_key(cfg.provider))}"); return 0
        if args.auth_command=="logout":
            if not get_api_key(cfg.provider): print("No stored API key."); return 0
            ans=input("Delete the stored API key? [y/N] ").strip().lower()
            if ans in {"y","yes"}: delete_api_key(); print("Stored API key deleted.")
            else: print("Key unchanged.")
            return 0
        if args.auth_command=="login": return asyncio.run(setup_flow(change=True))
        parser.parse_args(["auth","--help"]); return 0
    if args.command=="skills":
        if args.skills_command in (None,"list"): print_skills(cfg); return 0
        if args.skills_command=="show":
            try: info,body=load_skill(args.name,Path(cfg.workspace)); print(f"{info.name}: {info.description}\n\n{body}"); return 0
            except Exception as exc: print(str(exc)); return 1
        if args.skills_command=="validate":
            try: print(json.dumps(validate_skill(args.path),indent=2)); return 0
            except Exception as exc: print(f"Invalid skill: {exc}"); return 1
        if args.skills_command=="install":
            try: print(f"Installed to {install_skill(args.path)}"); return 0
            except Exception as exc: print(f"Could not install skill: {exc}"); return 1
        if args.skills_command=="disable":
            if args.name not in cfg.disabled_skills: cfg.disabled_skills.append(args.name)
            save_config(cfg); print(f"Skill {args.name} disabled for automatic selection."); return 0
        if args.skills_command=="enable":
            cfg.disabled_skills=[x for x in cfg.disabled_skills if x!=args.name]
            save_config(cfg); print(f"Skill {args.name} enabled for automatic selection."); return 0
    if args.command=="doctor":
        print(f"Lailaba CLI {__version__}\nPython: {sys.version.split()[0]}\nPlatform: {sys.platform}\nWorkspace: {cfg.workspace}\nWorkspace exists: {Path(cfg.workspace).is_dir()}\nConfig: {config_home()}\nProvider: {provider_label(cfg)}\nAPI base URL: {cfg.api_base_url if cfg.provider != 'lailaba' else DEFAULT_API_BASE_URL}\nModel: {cfg.model_name or 'automatic discovery'}\nAPI key: {mask_key(get_api_key(cfg.provider))}")
        if not get_api_key(cfg.provider): print("API status: not configured (run `lailaba-cli setup key`)"); return 1
        ok,msg=asyncio.run(api_for_config(cfg,get_api_key(cfg.provider)).verify())
        print(f"API status: {msg}"); return 0 if ok else 1
    if args.command=="info":
        print(f"Lailaba CLI {__version__} — autonomous tool-using agent\nProvider: {provider_label(cfg)}\nAPI base URL: {cfg.api_base_url if cfg.provider != 'lailaba' else DEFAULT_API_BASE_URL}\nModel: {cfg.model_name or 'automatic discovery'}\nWorkspace: {cfg.workspace}\nConfig directory: {config_home()}\nCapabilities: autonomous tool execution, workspace file operations, terminal/Git tools, skills, persistent memory, session history, task tracking, checkpoints/rollback, explicit context references, read-only parallel subagents, configured MCP tools, recurring scheduled jobs.\nSafety: workspace-aware path checks, approval prompts for risky operations, bounded execution.")
        return 0
    if args.command=="tools": return asyncio.run(_list_tools(cfg))
    if args.command=="permissions": _show_permissions(cfg); return 0
    if args.command=="tasks":
        from .tasks import list_tasks
        items=list_tasks(cfg.workspace)
        if not items: print("No workspace tasks yet.")
        for task in items: print(f"[{ 'x' if task.get('done') else ' ' }] {task['id']}  {task['title']}")
        return 0
    if args.command=="checkpoints":
        from .checkpoints import list_checkpoints
        items=list_checkpoints(cfg.workspace)
        if not items: print("No checkpoints yet.")
        for item in items: print(f"- {item['id']}  {item['path']}")
        return 0
    if args.command=="memory":
        subcmd=args.memory_command or "show"
        if subcmd=="show":
            content=read_memory(); print(content if content else f"Persistent memory is empty. File: {memory_path()}"); return 0
        if subcmd=="add":
            try: print(f"Memory note saved to {add_memory(' '.join(args.text))}"); return 0
            except Exception as exc: print(f"Could not save memory: {exc}"); return 1
        if subcmd=="clear":
            if input("Clear all persistent memory notes? [y/N] ").strip().lower() in {"y","yes"}: write_memory(""); print("Persistent memory cleared.")
            else: print("Memory unchanged.")
            return 0
    if args.command=="sessions":
        subcmd=args.sessions_command or "list"
        if subcmd=="list":
            items=recent_sessions()
            if not items: print("No saved sessions yet.")
            for item in items: print(f"- {item['id']} ({item['path']})")
            return 0
        if subcmd=="search":
            items=search_sessions(' '.join(args.query))
            if not items: print("No matching saved sessions.")
            for item in items: print(f"- {item['id']}: {item['excerpt']}")
            return 0
    if args.command=="mcp":
        if args.mcp_command in (None,"list"):
            if not cfg.mcp_servers: print("No MCP servers configured. Add one with `lailaba-cli mcp add NAME --command COMMAND --args-json '[...]'`.")
            for item in cfg.mcp_servers: print(f"- {item.get('name')}: {item.get('command')} {item.get('args',[])}")
            return 0
        if args.mcp_command=="add":
            try:
                import re
                if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}",args.name): raise ValueError("Name may contain only letters, numbers, underscore, and hyphen (max 40 characters).")
                argv=json.loads(args.args_json)
                if not isinstance(argv,list) or not all(isinstance(x,str) for x in argv): raise ValueError("--args-json must be a JSON array of strings.")
                cfg.mcp_servers=[x for x in cfg.mcp_servers if x.get('name')!=args.name]
                cfg.mcp_servers.append({"name":args.name,"command":args.server_command,"args":argv}); save_config(cfg)
                print(f"MCP server {args.name!r} configured. Commands are executed as written; only add servers you trust. Test with `lailaba-cli mcp test {args.name}`."); return 0
            except Exception as exc: print(f"Could not configure MCP server: {exc}",file=sys.stderr); return 2
        if args.mcp_command=="remove":
            old=len(cfg.mcp_servers); cfg.mcp_servers=[x for x in cfg.mcp_servers if x.get('name')!=args.name]
            if len(cfg.mcp_servers)==old: print(f"No MCP server named {args.name!r}.",file=sys.stderr); return 1
            save_config(cfg); print(f"Removed MCP server {args.name!r} from configuration."); return 0
        if args.mcp_command=="test": return asyncio.run(_mcp_test(args.name,cfg))
    if args.command=="schedule": return asyncio.run(_schedule_dispatch(args,cfg))
    if args.command=="run": return asyncio.run(_run_task(args,cfg))
    return asyncio.run(interactive(args,cfg))

if __name__=="__main__": raise SystemExit(main())
