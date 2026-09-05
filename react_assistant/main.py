from __future__ import annotations

import argparse
import re
import sys

from dataclasses import dataclass

from react_assistant.agent.agent import AssistantAgent
from react_assistant.agent.prompts import PromptBuilder
from react_assistant.agent.react_loop import ReActRunResult
from react_assistant.cli import Console, Spinner
from react_assistant.config import AppConfig
from react_assistant.llm.client import OpenAICompatibleClient
from react_assistant.logs.logger import ActionLogger
from react_assistant.memory.memory import ConversationMemory
from react_assistant.tools.calculator import CalculatorTool
from react_assistant.tools.datetime_tool import DateTimeTool
from react_assistant.tools.files import ListDirTool, ReadFileTool, WriteFileTool
from react_assistant.tools.registry import ToolRegistry
from react_assistant.tools.shell import PythonExecTool, ShellTool
from react_assistant.tools.weather import WeatherTool
from react_assistant.tools.web_fetch import WebFetchTool
from react_assistant.utils.helpers import truncate_text


@dataclass(slots=True)
class RuntimeContext:
    config: AppConfig
    console: Console
    logger: ActionLogger
    memory: ConversationMemory
    tools: ToolRegistry
    agent: AssistantAgent


HELP_TEXT = """\
ReAct Assistant — interactive commands

  /help     show this help
  /tools    list registered tools
  /memory   show recent conversation memory
  /status   show runtime configuration
  /clear    clear conversation history
  /exit     quit the assistant

Tip: anything else is sent straight to the agent. Chain tools, e.g.
ask 'weather in Paris then compute 18*49' and it will call multiple tools."""


def build_runtime(cli_overrides: dict | None = None) -> RuntimeContext:
    config = AppConfig.load(overrides=cli_overrides)
    console = Console()
    logger = ActionLogger(config.log_dir)
    memory = ConversationMemory(config.history_path, max_records=config.max_history_records)
    tools = ToolRegistry()
    # Core reasoning tools.
    tools.register(CalculatorTool())
    tools.register(DateTimeTool())
    tools.register(WeatherTool())
    # Multi-ability tools (all stdlib-only, sandboxed to workspace).
    tools.register(WebFetchTool())
    tools.register(ReadFileTool(root=config.workspace_root))
    tools.register(WriteFileTool(root=config.workspace_root))
    tools.register(ListDirTool(root=config.workspace_root))
    tools.register(ShellTool(root=config.workspace_root))
    tools.register(PythonExecTool())
    prompt_builder = PromptBuilder(config.system_prompt_path)
    llm_client = OpenAICompatibleClient(
        api_key=config.api_key,
        base_url=config.api_base_url,
        model=config.model,
        use_mock=config.use_mock_llm,
        timeout_seconds=config.llm_timeout_seconds,
        max_retries=config.llm_max_retries,
        temperature=config.llm_temperature,
    )
    agent = AssistantAgent(
        llm_client=llm_client,
        memory=memory,
        tools=tools,
        prompt_builder=prompt_builder,
        logger=logger,
        max_iterations=config.max_iterations,
        tool_timeout_seconds=config.tool_timeout_seconds,
        max_scratchpad_chars=config.max_scratchpad_chars,
    )
    return RuntimeContext(
        config=config,
        console=console,
        logger=logger,
        memory=memory,
        tools=tools,
        agent=agent,
    )


def print_banner(runtime: RuntimeContext) -> None:
    c = runtime.console
    mode = "mock" if runtime.agent.llm_client.use_mock else "live"
    c.rule("ReAct Assistant v0.2 (multi-ability)")
    c.key_value(
        [
            ("Model", runtime.config.model),
            ("Base URL", runtime.config.api_base_url),
            ("Tools", f"{len(runtime.tools.names())}: " + ", ".join(runtime.tools.names())),
            ("Workspace", str(runtime.config.workspace_root)),
            ("Memory", str(runtime.config.history_path)),
            ("Logs", str(runtime.config.log_dir)),
            ("Mode", c.yellow(mode) if mode == "mock" else c.green(mode)),
        ]
    )
    c.rule()
    c.print(c.gray("Type ") + c.bold("/help") +
            c.gray(" for commands, ") + c.bold("/exit") + c.gray(" to quit."))
    c.print()


def run_prompt(runtime: RuntimeContext, prompt_text: str) -> None:
    c = runtime.console
    prompt_text = (prompt_text or "").strip()
    if not prompt_text:
        return

    try:
        with Spinner("Thinking...", console=c) as spinner:
            result = runtime.agent.ask(prompt_text)
            step_actions = [s.parsed.action for s in result.steps if s.parsed.action]
            if step_actions:
                label = "Used " + ", ".join(dict.fromkeys(step_actions))
                spinner.update(label)
    except (ValueError, RuntimeError) as exc:
        c.error(f"Agent failed: {exc}")
        return
    except (KeyboardInterrupt, EOFError):
        c.print(c.gray("\nCancelled."))
        return

    _print_result(c, runtime, result)


def _format_usage(usage: dict[str, int] | None) -> str:
    if not usage:
        return "n/a"
    total = usage.get("total_tokens")
    if total is None:
        prompt_t = usage.get("prompt_tokens", 0)
        completion_t = usage.get("completion_tokens", 0)
        if prompt_t or completion_t:
            return f"{prompt_t + completion_t} tok (p{prompt_t}/c{completion_t})"
        return "n/a"
    prompt_t = usage.get("prompt_tokens")
    completion_t = usage.get("completion_tokens")
    if prompt_t is not None and completion_t is not None:
        return f"{total} tok (p{prompt_t}/c{completion_t})"
    return f"{total} tok"


def _print_result(c: Console, runtime: RuntimeContext, result: ReActRunResult) -> None:
    used_tools = [s.parsed.action for s in result.steps if s.parsed.action]
    has_trace = any(s.parsed.thought or s.parsed.action for s in result.steps)

    if has_trace:
        c.rule("Reasoning")
        for i, step in enumerate(result.steps, start=1):
            c.print(c.bold(c.gray(f"Iteration {i}")))
            if step.parsed.thought:
                c.print(f"  {c.bold(c.cyan('Thought'))}    {c.dim(truncate_text(step.parsed.thought, 600))}")
            if step.parsed.action:
                c.print(
                    f"  {c.bold(c.magenta('Action'))}    {c.bold(step.parsed.action)}"
                    + c.gray(f" ({truncate_text(step.parsed.action_input or '', 300)})")
                )
            if step.observation is not None:
                c.print(f"  {c.bold(c.yellow('Observation'))} {c.dim(truncate_text(step.observation, 600))}")
            if i < len(result.steps):
                c.print()
        c.rule()

    c.rule("Final Answer")
    c.print(_clean_answer(result.final_answer))
    c.rule()

    meta_bits = [
        f"model {c.cyan(runtime.config.model)}",
        f"iterations {len(result.steps)}",
        f"tools {', '.join(dict.fromkeys(used_tools)) if used_tools else 'none'}",
        f"usage {_format_usage(result.usage)}",
    ]
    if result.truncated:
        meta_bits.append(c.yellow("truncated (step limit)"))
    c.print(c.gray("  " + "  |  ".join(meta_bits)))
    c.print()


_FINAL_ANSWER_RE = re.compile(r"final\s*answer\s*:", re.IGNORECASE)
_SCAFFOLD_RE = re.compile(r"^(thought|action|action\s*input|observation)\s*:", re.IGNORECASE)


def _clean_answer(text: str) -> str:
    """Return the user-facing answer without ReAct scaffolding.

    If the model leaked 'Final Answer:' keep only what follows the LAST
    occurrence. Otherwise drop only strict scaffolding prefix lines, and
    only when other content remains (so a legit 'Action: packed lunch'
    answer is never deleted).
    """
    text = (text or "").strip()
    if not text:
        return text
    matches = list(_FINAL_ANSWER_RE.finditer(text))
    if matches:
        tail = text[matches[-1].end():].strip()
        if tail:
            return tail
        return text.strip()
    lines = text.splitlines()
    if len(lines) <= 1:
        return text
    filtered = [ln for ln in lines if not _SCAFFOLD_RE.match(ln.strip())]
    result = "\n".join(filtered).strip()
    return result or text.strip()


def _show_command_hint(runtime: RuntimeContext) -> None:
    c = runtime.console
    c.rule("Commands")
    rows = [
        ("/help", "show this help"),
        ("/tools", "list registered tools"),
        ("/memory", "show recent conversation memory"),
        ("/status", "show runtime configuration"),
        ("/clear", "clear conversation history"),
        ("/exit", "quit the assistant"),
    ]
    for name, desc in rows:
        c.print(f"  {c.bold(c.cyan(name))}  {c.dim(desc)}")
    c.rule()
    c.print(c.gray("Tip: type a command and press Enter, or just chat."))


def handle_command(runtime: RuntimeContext, text: str) -> bool:
    c = runtime.console
    command = text.strip().lower()
    if command in {"/exit", "exit", "quit", "/quit"}:
        c.print(c.gray("Goodbye."))
        return False
    if command in {"/help", "help"}:
        c.print(HELP_TEXT)
        return True
    if command == "/tools":
        c.rule("Available tools")
        for description in runtime.tools.descriptions():
            name, _, desc = description.partition(": ")
            c.print(f"  {c.bold(c.cyan(name))}: {desc}")
        c.rule()
        return True
    if command == "/memory":
        c.rule("Conversation memory")
        c.print(runtime.memory.summary(max_messages=12))
        c.rule()
        return True
    if command == "/clear":
        runtime.memory.clear()
        c.success("Memory cleared.")
        return True
    if command == "/status":
        mode = "mock" if runtime.agent.llm_client.use_mock else "live"
        c.rule("Status")
        c.key_value(
            [
                ("Model", runtime.config.model),
                ("Base URL", runtime.config.api_base_url),
                ("Mode", mode),
                ("Max iterations", str(runtime.config.max_iterations)),
                ("Tool timeout", f"{runtime.config.tool_timeout_seconds}s"),
                ("LLM timeout", f"{runtime.config.llm_timeout_seconds}s"),
                ("LLM retries", str(runtime.config.llm_max_retries)),
                ("Tools", ", ".join(runtime.tools.names())),
                ("Workspace", str(runtime.config.workspace_root)),
                ("Memory turns", str(len(runtime.memory.as_messages()))),
            ]
        )
        c.rule()
        return True
    c.warn(f"Unknown command: {text}")
    return True


def _handle_piped_input(runtime: RuntimeContext, full_text: str) -> None:
    """Piped stdin: support both single multi-line prompts and /commands."""
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    if not lines:
        return
    # If every non-empty line is a command, run each. Otherwise treat the
    # whole blob as ONE prompt (preserves multi-line code / questions).
    if all(ln.startswith("/") for ln in lines):
        for text in lines:
            if text.strip() in {"/", "/?"}:
                _show_command_hint(runtime)
                continue
            if not handle_command(runtime, text):
                break
        return
    # Mixed: run command lines, join the rest as one prompt.
    commands = [ln for ln in lines if ln.startswith("/")]
    prompts = [ln for ln in lines if not ln.startswith("/")]
    for cmd in commands:
        if cmd.strip() in {"/", "/?"}:
            _show_command_hint(runtime)
            continue
        if not handle_command(runtime, cmd):
            return
    if prompts:
        # Preserve original newlines for the prompt blob.
        run_prompt(runtime, full_text.strip())


def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="ReAct Assistant — a professional terminal agent.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--prompt", help="Ask a single prompt and exit.")
    parser.add_argument(
        "--once", help="Run a single prompt (from stdin if piped) and exit.",
        action="store_true",
    )
    parser.add_argument(
        "--no-banner", help="Suppress the startup banner.", action="store_true"
    )
    parser.add_argument(
        "--no-color", help="Disable colored output.", action="store_true"
    )
    parser.add_argument("--model", help="Override MODEL from .env.")
    parser.add_argument("--max-iterations", help="Override REACT_MAX_ITERATIONS.")
    parser.add_argument(
        "--mock", help="Force mock mode (no network).", action="store_true"
    )
    args = parser.parse_args()

    if args.no_color:
        import os

        os.environ["NO_COLOR"] = "1"

    cli_overrides: dict = {}
    if args.model:
        cli_overrides["MODEL"] = args.model
    if args.max_iterations:
        cli_overrides["REACT_MAX_ITERATIONS"] = args.max_iterations
    if args.mock:
        cli_overrides["LLM_USE_MOCK"] = "1"

    runtime = build_runtime(cli_overrides or None)
    if args.no_color:
        runtime.console.use_color = False

    if not args.no_banner:
        print_banner(runtime)

    if args.prompt:
        run_prompt(runtime, args.prompt)
        return

    if args.once:
        user_input = input("You > ") if sys.stdin.isatty() else sys.stdin.read().strip()
        run_prompt(runtime, user_input)
        return

    if not sys.stdin.isatty():
        _handle_piped_input(runtime, sys.stdin.read())
        return

    while True:
        try:
            user_input = input("You > ").strip()
        except (EOFError, KeyboardInterrupt):
            runtime.console.print(runtime.console.gray("\nGoodbye."))
            break

        if not user_input:
            continue
        if user_input.startswith("/"):
            if user_input.strip() in {"/", "/?"}:
                _show_command_hint(runtime)
                continue
            if not handle_command(runtime, user_input):
                break
            continue

        run_prompt(runtime, user_input)


if __name__ == "__main__":
    run_cli()
