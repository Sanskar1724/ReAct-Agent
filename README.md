# ReAct Assistant

A terminal-first Python assistant that demonstrates a **ReAct (Reason + Act)** agent loop, safe tool execution, JSON-backed conversation memory, and structured logging. It talks to any **OpenAI-compatible** API (OpenRouter, NVIDIA NIM, OpenAI, …) and falls back to a built-in **mock mode** when no API key is configured.

> Zero heavy dependencies. The CLI is styled with the standard library only — no `rich`/`click` required.

---

## ✨ Features

- **ReAct loop** — iterative *Thought → Action → Observation → Final Answer* reasoning with a configurable iteration cap.
- **Tool calling** — a registry of safe, timeout-guarded tools (`calculator`, `datetime`, `weather` placeholder).
- **Conversation memory** — persisted to JSON, summarized and fed back into prompts.
- **Professional CLI** — colored, non-blocking spinner, ruled panels, a `Thinking` trace per iteration, and a clean `Final Answer` block.
- **Structured logging** — human-readable log + JSONL event stream.
- **Mock mode** — runs end-to-end with no network or API key.

---

## 🚀 Quick Start

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
#   then edit .env and set OPENROUTER_API_KEY / BASE_URL / MODEL

# 4. Run the assistant
python -m react_assistant
```

Run a single prompt without the interactive loop:

```powershell
python -m react_assistant --prompt "What is 18 * 49?"
python -m react_assistant --once          # read one prompt from stdin
python -m react_assistant --no-banner    # suppress the startup banner
python -m react_assistant --no-color     # force plain (uncolored) output
```

Example `.env`:

```env
OPENROUTER_API_KEY=your_api_key_here
BASE_URL=https://openrouter.ai/api/v1
MODEL=meta/llama-3.3-70b-instruct
LLM_USE_MOCK=0
```

The assistant runs in **live** mode when `OPENROUTER_API_KEY` is set and `LLM_USE_MOCK` is `0`/unset; otherwise it uses **mock** mode.

---

## 🧭 CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show the help text |
| `/tools` | List registered tools |
| `/memory` | Show recent conversation memory |
| `/status` | Show runtime config (model, mode, timeouts, tool list, turns) |
| `/clear` | Clear conversation history |
| `/` or `/?` | Show the command menu inline |
| `/exit` (`exit`, `quit`) | Quit the assistant |

When the agent uses tools, output looks like:

```
──────────────────────── Reasoning ────────────────────────
Iteration 1
  Thought     I need to compute 18 * 49.
  Action      calculator (18 * 49)
  Observation 882
───────────────────────────────────────────────────────────
─────────────────────── Final Answer ──────────────────────
882
───────────────────────────────────────────────────────────
  model llama-3.3-70b-instruct · iterations 1 · tools calculator · usage 318 tok
```

---

## 🗂️ Project Structure

```
Single-Agent/
├── .env.example            # template for credentials (copy to .env)
├── .gitignore
├── .gitattributes
├── LICENSE                 # MIT
├── README.md
├── requirements.txt        # python-dotenv
├── DOCUMENTATION.md        # deep-dive reference
└── react_assistant/
    ├── __init__.py         # package marker, __version__
    ├── __main__.py         # entry point for `python -m react_assistant`
    ├── main.py             # CLI, runtime wiring, commands
    ├── config.py           # AppConfig: typed settings from .env
    ├── cli/                # dependency-free terminal styling
    │   ├── console.py      # Console: colors, rules, panels, key/value
    │   └── spinner.py      # Spinner: non-blocking terminal spinner
    ├── llm/
    │   ├── client.py       # OpenAICompatibleClient (live + mock)
    │   └── models.py       # ChatMessage, LLMResponse, LLMUsage
    ├── agent/
    │   ├── agent.py        # AssistantAgent: orchestration
    │   ├── parser.py       # ReActParser: extracts Thought/Action/...
    │   ├── prompts.py      # PromptBuilder: assembles messages
    │   └── react_loop.py   # ReActLoop: the core cycle
    ├── memory/
    │   └── memory.py       # ConversationMemory: JSON history
    ├── tools/
    │   ├── registry.py     # ToolRegistry + RunnableTool protocol
    │   ├── calculator.py   # safe arithmetic via ast
    │   ├── datetime_tool.py# current UTC time
    │   └── weather.py      # placeholder weather tool
    ├── logs/
    │   └── logger.py       # ActionLogger: text + JSONL
    ├── templates/
    │   └── system_prompt.txt
    └── utils/
        └── helpers.py      # JSON/text IO, timestamps, dir helpers
```

For a full module-by-module reference, architecture diagrams, the ReAct loop
walkthrough, and extension guides, see **[DOCUMENTATION.md](DOCUMENTATION.md)**.

---

## ⚙️ Configuration

All settings are read from `.env` (see `.env.example`). Supported variables:

| Variable | Meaning | Default |
|----------|---------|---------|
| `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`, `LLM_API_KEY`) | API key | none |
| `BASE_URL` (or `OPENROUTER_BASE_URL`, `OPENAI_BASE_URL`) | Endpoint base URL | `https://openrouter.ai/api/v1` |
| `MODEL` (or `OPENROUTER_MODEL`, `OPENAI_MODEL`) | Model name | `gpt-4o-mini` |
| `LLM_USE_MOCK` | `1`/`true`/`yes`/`on` forces mock mode | off if key present |
| `REACT_MAX_ITERATIONS` | Max ReAct loop iterations | `6` |
| `TOOL_TIMEOUT_SECONDS` | Tool execution timeout (enforced) | `10` |

---

## 📤 Output Locations

- **Console** — live prompts and answers.
- `react_assistant/logs/assistant.log` — human-readable activity log.
- `react_assistant/logs/actions.jsonl` — structured event log (one JSON/line).
- `react_assistant/memory/history.json` — conversation history (git-ignored).

---

## 🔌 Extending

**Add a tool**

```python
# react_assistant/tools/my_tool.py
class MyTool:
    name = "my_tool"
    description = "Does something useful."
    aliases = {"my", "tool"}

    def run(self, input_text: str = "") -> str:
        return "result"

# register in react_assistant/main.py -> build_runtime()
from react_assistant.tools.my_tool import MyTool
tools.register(MyTool())
```

**Switch provider/model** — edit `.env` (`BASE_URL`, `MODEL`, key). Any OpenAI-compatible API works.

**Customize behavior** — edit `react_assistant/templates/system_prompt.txt` to change agent instructions without touching code.

---

## 🤝 Contributing

1. Fork and create a feature branch.
2. Keep dependencies minimal; prefer the standard library.
3. Run the assistant in mock mode (`LLM_USE_MOCK=1`) for quick local testing.
4. Open a pull request with a clear description.

---

## 📄 License

Released under the [MIT License](LICENSE).
