# Lailaba CLI

Lailaba CLI v0.6.0 is a Python 3.11+ autonomous terminal agent with a Textual-based full-screen terminal UI and support for Lailaba AI plus third-party OpenAI-compatible APIs. It adopts common agent-workflow patterns—tool execution, reusable skills, persistent memory, context references, task tracking, and reversible file edits—under Lailaba AI branding and its monochrome `#000000`, `#2b2b2b`, `#ffffff` design. It is an independent implementation inspired by Hermes Agent, not a byte-for-byte clone of its source code.

## Features
                                                                 Lailaba CLI is an independently implemented agent inspired by the broad workflow patterns of modern terminal agents. It is not a clone of Hermes Agent and does not yet provide every Hermes integration.                                                           
- Interactive terminal session and multistep tool loop using structured Chat Completions tool calls.
- Provider onboarding defaults to Lailaba AI. During setup, users can keep the current provider/key or configure a third-party OpenAI-compatible API by validating the HTTPS base URL, API key, and a model ID returned by `/models`. Lailaba AI keeps automatic model discovery; third-party providers use the configured model name. No `--model` command-line option is exposed.
- Workspace-scoped filesystem and Git tools, terminal execution with timeouts/output limits, public HTTP browsing with redirect and SSRF checks, and arithmetic/time utilities.
- Skill discovery from `~/.config/lailaba-cli/skills/` and project-local `.lailaba/skills/`.
- JSON config, private session history, session search/resume, persistent user-curated memory, workspace context files, masked auth status, hidden API-key prompt, persistent workspace tasks, file checkpoints, and rollback support.
- Read-only parallel subagent delegation (up to three independent research/inspection subtasks) with a restricted tool allowlist.
- MCP stdio server configuration and tool discovery; all MCP tool calls require explicit approval.
- Persistent recurring jobs with an interval scheduler process; jobs retain their workspace and task description.
- Full-screen Textual agent UI on interactive terminals, including task progress, tool activity, a permission approval modal, status panel, and slash commands; basic line-oriented fallback for non-TTY sessions. Monochrome `#000000`, `#2b2b2b`, `#ffffff` theme.
- Unit tests use mocked HTTP responses and temporary directories; no real API key is required.

## Installation (one installer; no `start.sh`)

Supported target: Linux, macOS, WSL, EC2 Linux, and Termux with Python 3.11+. From the extracted project directory:

```bash
chmod +x install.sh
./install.sh
```

`install.sh` creates a private virtual environment under `~/.local/share/lailaba-cli/venv`, installs the package (including Textual) and dependencies, adds the `lailaba-cli` command under `~/.local/bin`, adds that directory to common shell profiles when needed, and starts the provider/API-key setup wizard. It does not use `sudo`, modify system Python, or require a separate launcher. On Debian/Ubuntu, if virtual-environment creation fails, install the OS package that provides `venv` (often `python3-venv`) and rerun the installer. In Termux, install Python with `pkg install python` first.

To install without prompting for the API key during the install step:

```bash
LAILABA_SKIP_SETUP=1 ./install.sh
lailaba-cli setup key
```

If `lailaba-cli: command not found` appears immediately after install, open a new terminal or run `export PATH="$HOME/.local/bin:$PATH"` in the current shell.

## First-run setup and API key

```bash
lailaba-cli setup key       # configure/change provider and API key
lailaba-cli setup provider  # switch provider or update credentials
lailaba-cli provider show   # show active provider settings
lailaba-cli auth status     # show masked key status
lailaba-cli auth login      # legacy alias to change the key
lailaba-cli auth logout     # remove the stored key after confirmation
lailaba-cli doctor          # check local installation and API connectivity
```

The default provider is Lailaba AI at `https://100.57.251.241.nip.io/api/v1`. During setup, choose whether to continue with Lailaba AI or use a third-party OpenAI-compatible provider. For third-party providers, enter a base URL; the installer probes `/models` without sending a key and accepts authentication-required responses as evidence that the endpoint is reachable. Then enter an API key; the key is checked through authenticated `GET /models`, and the user must choose a model ID returned by that endpoint. Remote providers require HTTPS; plain HTTP is accepted only for localhost. Chat uses `POST /chat/completions` with Bearer authentication and structured tool definitions. Provider compatibility and tool-calling support depend on the selected service.

Credentials prefer an available OS keyring; otherwise the application writes `credentials.json` with mode `0600` inside a mode-`0700` config directory. The API key is not stored in `config.json`. `LAILABA_API_KEY` takes precedence for Lailaba AI; `LAILABA_THIRD_PARTY_API_KEY` or `OPENAI_API_KEY` can supply the key for an OpenAI-compatible provider. Provider-specific environment variables take precedence over the stored key for that provider. Avoid putting secrets directly into shell commands because they can remain in shell history.

## Run the agent

```bash
cd ./my-project
lailaba-cli
```

This starts the autonomous agent in the current workspace. It is not limited to a question-and-answer chat: describe a task, and it can inspect files, plan work, use registered tools, run bounded terminal commands, make approved edits, and report verified results. Risky writes and shell operations ask for confirmation by default.

For a one-off task that exits after the agent finishes:

```bash
lailaba-cli --workspace ./my-project run "Inspect this project, run its tests, and report actionable issues"
```

Useful commands:

```text
lailaba-cli                         Start the agent in the current directory
lailaba-cli setup key               Set or change the API key
lailaba-cli doctor                  Diagnose installation and API connectivity
lailaba-cli info                    Show agent info and implemented capabilities
lailaba-cli run "task instructions" Run one autonomous task
lailaba-cli tools                   List registered tools
lailaba-cli skills list             List skills
lailaba-cli skills show NAME        Inspect a skill
lailaba-cli memory show              View persistent memory
lailaba-cli memory add "note"        Save a memory note
lailaba-cli sessions list            List saved sessions
lailaba-cli sessions search "text"   Search saved session history
lailaba-cli tasks                    List workspace tasks
lailaba-cli checkpoints              List file checkpoints
lailaba-cli mcp list                 List configured MCP servers
lailaba-cli schedule list            List recurring autonomous jobs
lailaba-cli permissions              Show safety policy
lailaba-cli --help                   Show all commands
```

Inside the agent, use `/help`, `/tools`, `/skills`, `/status`, `/workspace`, `/permissions`, `/history`, `/search TEXT`, `/resume ID`, `/new`, `/memory`, `/memory add TEXT`, `/memory clear`, `/tasks`, `/checkpoints`, `/rollback [ID]`, `/config`, and `/doctor`. Context references include `@file:path`, `@folder:path`, and `@git-diff`.

Global options: `--help`, `--version`, `--workspace PATH`, `--no-color`, and `--debug` (reserved; it currently does not change logging verbosity).

## Implemented tools

Filesystem: `list_directory`, `read_file`, `write_file`, `edit_file`, `create_directory`, `search_files`, `find_text`, `inspect_file_metadata`.

Terminal/environment: `terminal_execute`, `terminal_get_working_directory`, `terminal_list_environment`, `terminal_check_command`, `run_tests`, `get_current_time`, `calculate`, `inspect_environment`.

Web: `web_search`, `web_open`, `web_extract`, `web_follow_link`, `web_fetch`. Public page fetch uses HTTP(S), a bounded response size, timeouts, redirect revalidation, and rejects local/private/reserved IP destinations by default. Search uses DuckDuckGo's public HTML endpoint without an extra API key; its markup can change and this is not equivalent to a dedicated search API. Browser automation for JavaScript-heavy sites is not included.

Git: `git_status`, `git_diff`, `git_log`, `git_branch`.

The registry validates JSON argument shapes, records execution duration, catches failures, enforces timeouts, and returns actual tool results. Tool-call support depends on the API/model accepting OpenAI-style `tools` and `tool_calls`. If unsupported, the API error is surfaced; the CLI does not pretend that text suggestions are tool calls.


## MCP integrations

MCP servers are **not installed or enabled automatically**. Configure only servers you trust; an MCP server is an external program and may access data or perform actions according to its own implementation. The command and arguments are stored in your local config. Do not place API secrets in command-line arguments.

```bash
lailaba-cli mcp list
lailaba-cli mcp add filesystem --command npx --args-json '["-y","@modelcontextprotocol/server-filesystem","/absolute/path/to/allowed/folder"]'
lailaba-cli mcp test filesystem
lailaba-cli mcp remove filesystem
```

MCP tools are loaded into the agent at runtime and are namespaced as `mcp_SERVER_TOOL`. Every MCP tool invocation asks for approval. This release implements the MCP stdio transport and tools/list/tools/call flow; remote HTTP/SSE transports, OAuth flows, server marketplace discovery, and advanced resource/prompt subscriptions are not included. Confirm each server's official installation instructions and permissions before configuring it.

## Scheduled autonomous tasks

Jobs are persistent and execute at a repeating interval. The scheduler must be running for jobs to fire; it is not automatically installed as a system service.

```bash
lailaba-cli schedule add --every-minutes 60 --task "Inspect the current project and report failing tests"
lailaba-cli schedule list
lailaba-cli schedule run-due
lailaba-cli schedule daemon
lailaba-cli schedule remove JOB_ID
```

`lailaba-cli schedule daemon` checks for due jobs continuously until stopped. Scheduled tasks use the saved Lailaba AI key and workspace. Risky tool operations still require approval, so unattended operation is not a promise of unattended writes. For always-on use, run it under a process manager you understand and secure. Jobs are interval-based rather than full cron-expression scheduling.

## Subagent delegation

The main agent can delegate up to three independent inspection or research subtasks in parallel through `delegate_tasks`. Subagents use the same Lailaba AI provider and a restricted read-only tool allowlist; they cannot write files or run shell commands. They return findings to the parent agent, which remains responsible for the final response. This is a bounded implementation, not full Hermes-style recursive subagent orchestration or a configurable agent team.

## Agent workflow features

- **Persistent task list:** the model can add, list, complete, reopen, and remove workspace tasks. Use `/tasks` to inspect them.
- **File checkpoints:** before `write_file` or `edit_file` changes a file, Lailaba CLI saves a private checkpoint. Use `/checkpoints` to list checkpoints and `/rollback [ID]` to restore one; rollback asks for confirmation. Checkpoints are local snapshots, not a replacement for Git or backups.
- **Context references:** include bounded workspace context with `@file:src/app.py`, `@folder:src`, or `@git-diff`. Referenced content is treated as untrusted input.
- **Provider onboarding:** setup asks whether to continue with Lailaba AI or configure a third-party OpenAI-compatible provider. A third-party endpoint must pass URL validation, its key must authenticate against `/models`, and the selected model must appear in that provider’s model list.

## Permissions and security

- Filesystem paths are resolved and constrained to configured workspace roots; symlink targets are resolved before access.
- Writes, edits, directory creation, and shell commands ask for confirmation by default. The model cannot silently bypass the prompt.
- Common destructive/system commands, privilege escalation, and piping downloaded scripts into a shell are denied by the terminal policy.
- Terminal commands run with bounded time, output size, and cleanup on timeout. They are not an OS-level sandbox: a shell command can access other paths or network resources if the user explicitly approves it and the OS account permits it. Use a dedicated OS account/container for stronger isolation and carefully review commands.
- Web destinations are checked before requests and after redirects; TLS verification remains enabled. DNS rebinding cannot be eliminated completely at this application layer.
- Website content and skill instructions are treated as untrusted input and cannot override system policy. Skill scripts are never auto-executed. Inspect them before running.
- No environment variable values, shell history, SSH keys, or full environment are sent to the model. Tool output is bounded but may still contain sensitive project content if the user asks to read it.
- Do not run as root. Package installation and other external side effects should be performed only after review.

## Persistent memory and workspace context

Use `/memory` to inspect the user-curated memory file, `/memory add TEXT` to append a note, and `/memory clear` to clear it after confirmation. Memory is stored at `~/.config/lailaba-cli/MEMORY.md` (or the platform config directory) with restrictive file permissions. Do not put passwords, API keys, or other secrets in memory.

At the start of a task, Lailaba CLI can read short workspace guidance files named `LAILABA.md`, `AGENTS.md`, `CLAUDE.md`, and `.lailaba.md` from the workspace root. Their contents are treated as untrusted project guidance, not system policy.

Use `/search TEXT` to search saved session text, `/history` to list saved sessions, `/resume ID` to continue one, and `/new` to start a fresh conversation. Session files can contain user-provided project content, so protect the config directory and remove history you no longer need.

## Skills

Built-in skills are bundled with the installed package. User skills go in `~/.config/lailaba-cli/skills/`; project skills go in `.lailaba/skills/`. Each skill is a directory with a `SKILL.md`:

```markdown
---
name: python-development
description: Helps inspect, create, debug, test, and maintain Python projects.
---

# Python Development
Read relevant source before editing. Run the available tests after changes.
```

Commands:

```bash
lailaba-cli skills list
lailaba-cli skills show python-development
lailaba-cli skills validate ./my-skill
lailaba-cli skills install ./my-skill
```

Install only trusted local skill directories. The installer copies files but does not run scripts. Automatic selection is task relevance-based. `skills disable NAME` and `skills enable NAME` control automatic skill selection. Disabled skills remain discoverable for inspection but are not loaded automatically.

## Configuration

`config.json` includes workspace roots, execution limits, policy switches, and non-secret provider settings (provider type, base URL, and configured model name). API keys are not stored there. `--workspace` persists the selected workspace and uses it as the default allowed root. Review config before relaxing policies. Session JSON files are stored in `sessions/` with restrictive permissions on Unix-like systems.

## Testing

```bash
python -m pip install -e '.[test]'
pytest -q
```

Tests are designed not to call the live API or touch a real user project. See `tests/`.

## Troubleshooting

- **Python too old:** install Python 3.11 or newer and rerun `install.sh`.
- **Dependency install fails:** check pip/network access; dependencies are pinned in the project dependency configuration.
- **Authentication fails:** run `lailaba-cli auth status`, then `lailaba-cli setup key`.
- **Connection test fails:** the key is preserved. Retry with `lailaba-cli setup key`; verify service reachability and current endpoint contract. TLS verification is not disabled.
- **No models found:** the API's `/models` response may differ from the expected `data`/`models` list shape.
- **Tool calling rejected:** confirm the API and selected model support OpenAI-style Chat Completions function calling.
- **Web search empty:** DuckDuckGo markup may have changed or network access may be blocked. Direct public page fetching remains separate from full search.

## Uninstallation

Remove `~/.local/bin/lailaba-cli` and `~/.local/share/lailaba-cli/` to uninstall the program. Optionally remove `~/.config/lailaba-cli/` to delete credentials, memory, skills, checkpoints, and session history; back up anything needed first. Deleting the config directory removes credentials and session history; back up sessions first if needed.

## Roadmap toward a broader agent runtime

The current implementation includes local tools, user-approved shell execution, workspace-aware skills/context, persistent memory, saved sessions, task tracking, file checkpoints/rollback, public web fetching, a Textual TUI, provider routing for OpenAI-compatible APIs, bounded read-only subagents, stdio MCP, and interval-based scheduling. It is still not complete Hermes Agent feature parity: browser automation, messaging gateways, voice/image generation, remote MCP transports, advanced MCP resource/prompt features, cron expressions, background process management, and recursive subagent teams remain future work.

## Limitations

This release uses the common `/models` and `/chat/completions` protocol but the supplied API endpoint's exact live contract and model tool-calling support have not been independently verified. Streaming, browser automation, process polling, interactive subprocess input, deletion tools, and external search-provider integrations are not implemented. The API client intentionally does not automatically retry requests because tool calls must not be accidentally duplicated. The `--debug` option currently has no additional effect.

### Android / Termux notes

Do not install the project directly from Android shared storage such as `~/storage/downloads` or `/sdcard`. Shared storage may not support the symlink and executable behavior required by Python virtual environments. Copy or extract the project into Termux's private home directory first, then install it there. The installer does not copy the project from shared storage automatically.

In Termux, install Python if needed with `pkg update && pkg install python`, then extract/copy the project into `$HOME/lailaba-cli` and run `cd ~/lailaba-cli && bash install.sh`. The installer uses an isolated virtual environment and does not require `sudo` or modify system-wide Python packages. If package downloads fail, check network access and rerun `bash install.sh`
