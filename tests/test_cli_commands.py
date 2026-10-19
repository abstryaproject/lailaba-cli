from lailaba_cli.cli import build_parser


def test_setup_key_command_is_available_without_model_options():
    args = build_parser().parse_args(["setup", "key"])
    assert args.command == "setup"
    assert args.setup_command == "key"
    assert not hasattr(args, "model")


def test_agent_task_and_doctor_commands_are_available():
    parser = build_parser()
    run_args = parser.parse_args(["run", "inspect", "the", "project"])
    assert run_args.command == "run"
    assert run_args.task == ["inspect", "the", "project"]
    assert parser.parse_args(["doctor"]).command == "doctor"
    assert parser.parse_args(["tools"]).command == "tools"
    assert parser.parse_args(["sessions", "search", "bug", "report"]).query == ["bug", "report"]


def test_no_provider_or_model_selector_is_exposed():
    parser = build_parser()
    try:
        parser.parse_args(["--model", "some-model"])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("--model must not be accepted")


def test_mcp_and_schedule_commands_are_available():
    parser = build_parser()
    mcp = parser.parse_args(["mcp", "add", "files", "--command", "python", "--args-json", "[]"])
    assert mcp.command == "mcp" and mcp.mcp_command == "add"
    sched = parser.parse_args(["schedule", "add", "--every-minutes", "30", "--task", "check tests"])
    assert sched.command == "schedule" and sched.every_minutes == 30


def test_provider_setup_commands_are_available():
    parser = build_parser()
    assert parser.parse_args(["setup", "provider"]).setup_command == "provider"
    assert parser.parse_args(["provider", "show"]).provider_command == "show"
    assert parser.parse_args(["provider", "setup"]).provider_command == "setup"
