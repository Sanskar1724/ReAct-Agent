from __future__ import annotations

import argparse
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
from react_assistant.tools.registry import ToolRegistry
from react_assistant.tools.weather import WeatherTool


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

Tip: anything else is sent straight to the agent."""


def build_runtime() -> RuntimeContext:
    config = AppConfig.load()
    console = Console()
    logger = ActionLogger(config.log_dir)
    memory = ConversationMemory(config.history_path)
    tools = ToolRegistry()
    tools.register(CalculatorTool())
    tools.register(WeatherTool())
    tools.register(DateTimeTool())
    prompt_builder = PromptBuilder(config.system_prompt_path)
    llm_client = OpenAICompatibleClient(
        api_key=config.api_key,
        base_url=config.api_base_url,
        model=config.model,
        use_mock=config.use_mock_llm,
    )
    agent = AssistantAgent(
        llm_client=llm_client,
        memory=memory,
        tools=tools,
        prompt_builder=prompt_builder,
        logger=logger,
        max_iterations=config.max_iterations,
        tool_timeout_seconds=config.tool_timeout_seconds,
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
    c.rule("ReAct Assistant")
    c.key_value(
        [
            ("Model", runtime.config.model),
            ("Base URL", runtime.config.api_base_url),
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
    prompt_text = prompt_text.strip()
    if not prompt_text:
        return

    try:
        with Spinner("Thinking…", console=c) as spinner:
            result = runtime.agent.ask(prompt_text)
            step_actions = [s.parsed.action for s in result.steps if s.parsed.action]
            if step_actions:
                label = "Used " + ", ".join(dict.fromkeys(step_actions))
                spinner.update(label)
    except Exception as exc:
        c.error(f"Agent failed: {exc}")
        return

    _print_result(c, runtime, result)


def _format_usage(usage: dict[str, int] | None) -> str:
    if not usage:
        return "n/a"
    total = usage.get("total_tokens")
    if total is None:
        return "n/a"
    return f"{total} tok"


def _print_result(c: Console, runtime: RuntimeContext, result: ReActRunResult) -> None:
    used_tools = [s.parsed.action for s in result.steps if s.parsed.action]
    has_trace = any(s.parsed.thought or s.parsed.action for s in result.steps)

    if has_trace:
        c.rule("Reasoning")
        for i, step in enumerate(result.steps, start=1):
            c.print(c.bold(c.gray(f"Iteration {i}")))
            if step.parsed.thought:
                c.print(f"  {c.bold(c.cyan('Thought'))}    {c.dim(step.parsed.thought)}")
            if step.parsed.action:
                c.print(
                    f"  {c.bold(c.magenta('Action'))}    {c.bold(step.parsed.action)}"
                    + c.gray(f" ({step.parsed.action_input or ''})")
                )
            if step.observation is not None:
                c.print(f"  {c.bold(c.yellow('Observation'))} {c.dim(step.observation)}")
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
    c.print(c.gray("  " + "  ·  ".join(meta_bits)))
    c.print()


def _clean_answer(text: str) -> str:
    """Strip any leftover ReAct scaffolding the model may have leaked into
    the final answer so the output never repeats the raw reasoning."""
    cleaned_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(
            ("thought:", "action:", "action input:", "observation:", "final answer:")
        ):
            continue
        cleaned_lines.append(line)
    result = "\n".join(cleaned_lines).strip()
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
        c.print(runtime.memory.summary())
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
                ("Tools", ", ".join(runtime.tools.names())),
                ("Memory turns", str(len(runtime.memory.as_messages()))),
            ]
        )
        c.rule()
        return True
    c.warn(f"Unknown command: {text}")
    return True


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
    args = parser.parse_args()

    if args.no_color:
        import os

        os.environ["NO_COLOR"] = "1"

    runtime = build_runtime()
    if args.no_color:
        runtime.console.use_color = False

    if not args.no_banner:
        print_banner(runtime)

    if args.prompt:
        run_prompt(runtime, args.prompt)
        return

    if args.once:
        user_input = input("You › ") if sys.stdin.isatty() else sys.stdin.read().strip()
        run_prompt(runtime, user_input)
        return

    if not sys.stdin.isatty():
        for line in sys.stdin:
            text = line.strip()
            if not text:
                continue
            if text.startswith("/"):
                if text.strip() in {"/", "/?"}:
                    _show_command_hint(runtime)
                    continue
                if not handle_command(runtime, text):
                    break
                continue
            run_prompt(runtime, text)
        return

    while True:
        try:
            user_input = input("You › ").strip()
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
