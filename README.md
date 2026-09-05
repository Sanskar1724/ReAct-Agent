# ReAct Assistant v0.2 — multi-ability agent

A terminal-first Python assistant that runs a **ReAct (Reason + Act)** loop: iterative *Thought → Action → Observation → Final Answer* reasoning with safe, timeout-guarded tools, JSON-backed memory, and structured logging. It talks to any **OpenAI-compatible** API (OpenRouter, NVIDIA NIM, OpenAI, …) and falls back to **mock mode** when no API key is configured.

> Zero heavy dependencies. Only `python-dotenv` — CLI styling, HTTP, and tooling are standard library.

---

## ✨ Features

- **ReAct loop** — multi-step *Thought → Action → Observation* chains with loop detection, scratchpad caps, and graceful step-limit answers (no more crashes on max iterations).
- **9 tools, one per turn, chained across turns** — math, live weather, web fetch, workspace files, shell, and Python execution.
- **Conversation memory** — persisted to JSON (capped, atomic writes, corruption-safe), summarized into prompts, searchable.
- **Professional CLI** — Windows-safe colors, non-blocking spinner, `Reasoning` trace, clean `Final Answer` block, accumulated token usage.
- **Structured logging** — rotating human-readable log + JSONL event stream (secrets redacted).
- **Mock mode** — runs end-to-end with no network or API key (`--mock`).

---

## 🛠️ Tools

| Tool | Aliases | What it does | Example input |
|------|---------|--------------|---------------|
| `calculator` | `calc`, `math` | Safe arithmetic via `ast` (limits on size/exponent) | `18 * 49` |
| `datetime` | `time`, `now` | Current UTC time (ISO-8601) | *(empty)* |
| `weather` | `forecast` | **Live** weather via Open-Meteo, no key needed | `Paris` / `Delhi, India` |
| `web_fetch` | `fetch`, `web`, `url` | Fetch URL → stripped text (truncated, SSRF-blocked) | `https://example.com` |
| `read_file` | `read`, `cat` | Read workspace text file (~6000 chars) | `README.md` |
| `write_file` | `write`, `save` | Write workspace file (1st line = path) | `notes/todo.txt\nBuy milk` |
| `list_dir` | `ls`, `list`, `dir` | List workspace directory | `.` / `notes` |
| `shell` | `run`, `exec`, `cmd` | Shell command in workspace (15s, destructive cmds blocked) | `python --version` |
| `python_exec` | `python`, `py`, `code` | Run Python snippet (10s, stdout captured) | `print(2+2)` |

File/shell tools are sandboxed to `WORKSPACE_ROOT` (default: project root) — paths escaping it are rejected.

---

## 🚀 Quick Start

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
Copy-Item .env.example .env
#   then edit .env and set OPENROUTER_API_KEY / BASE_URL / MODEL

# 4. Run the assistant
python -m react_assistant
```

Single prompts and overrides:

```powershell
python -m react_assistant --prompt "What is 18 * 49?"
python -m react_assistant --mock --prompt "hi"   # force mock, no network
python -m react_assistant --once                 # read one prompt from stdin
python -m react_assistant --model "gpt-4o-mini" --max-iterations 10 --prompt "..."
python -m react_assistant --no-banner            # suppress the startup banner
python -m react_assistant --no-color             # force plain (uncolored) output
```

Example `.env`:

```env
OPENROUTER_API_KEY=your_api_key_here
BASE_URL=https://openrouter.ai/api/v1
MODEL=meta/llama-3.3-70b-instruct
LLM_USE_MOCK=0
REACT_MAX_ITERATIONS=8
TOOL_TIMEOUT_SECONDS=15
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=2
LLM_TEMPERATURE=0.2
WORKSPACE_ROOT=
MAX_HISTORY_RECORDS=200
MAX_SCRATCHPAD_CHARS=12000
```

Live mode when a real key is set and `LLM_USE_MOCK` is `0`/unset; otherwise mock mode.

---

## 🧭 CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show the help text |
| `/tools` | List registered tools |
| `/memory` | Show recent conversation memory |
| `/status` | Show runtime config (model, mode, timeouts, retries, tools, workspace, turns) |
| `/clear` | Clear conversation history |
| `/` or `/?` | Show the command menu inline |
| `/exit` (`exit`, `quit`) | Quit the assistant |

Multi-step example — the agent chains tools across turns:

```
----------------------- Reasoning ------------------------
Iteration 1
  Thought    I need live weather first, then I can summarize and save it.
  Action     weather (Paris)
  Observation Weather in Paris, France: partly cloudy, 14C ...
Iteration 2
  Thought    Now I'll save that summary to a file.
  Action     write_file (notes/paris_weather.txt ...)
  Observation Wrote 32 chars to notes/paris_weather.txt.
------------------------------------------------------------
---------------------- Final Answer ------------------------
Paris is partly cloudy at 14C, saved to notes/paris_weather.txt.
------------------------------------------------------------
  model tencent/hy3:free  |  iterations 2  |  tools weather, write_file  |  usage 280 tok (p250/c30)
```

---

## 🗂️ Project Structure

```
Single-Agent/
├── .env.example            # template for credentials (copy to .env)
├── .gitignore
├── .gitattributes
├── LICENSE                 # MIT
├── README.md               # this file
├── requirements.txt        # python-dotenv
├── DOCUMENTATION.md        # deep-dive reference
└── react_assistant/
    ├── __init__.py         # package marker, __version__
    ├── __main__.py         # entry point for `python -m react_assistant`
    ├── main.py             # CLI, runtime wiring, commands
    ├── config.py           # AppConfig: typed settings from .env + CLI overrides
    ├── cli/                # dependency-free terminal styling
    │   ├── console.py      # Console: Windows-safe colors, rules, panels
    │   └── spinner.py      # Spinner: non-blocking terminal spinner
    ├── llm/
    │   ├── client.py       # OpenAICompatibleClient (retries, mock, guards)
    │   └── models.py       # ChatMessage, LLMResponse, LLMUsage
    ├── agent/
    │   ├── agent.py        # AssistantAgent: orchestration
    │   ├── parser.py       # ReActParser: Thought/Action/Action Input/Final Answer
    │   ├── prompts.py      # PromptBuilder: cached template + tool list
    │   └── react_loop.py   # ReActLoop: cycle, loop detection, usage sum
    ├── memory/
    │   ├── __init__.py
    │   └── memory.py       # ConversationMemory: capped atomic JSON history
    ├── tools/
    │   ├── __init__.py
    │   ├── registry.py     # ToolRegistry (shared pool, real timeouts)
    │   ├── calculator.py   # safe arithmetic via ast
    │   ├── datetime_tool.py# current UTC time
    │   ├── weather.py      # live Open-Meteo weather
    │   ├── web_fetch.py    # URL → text
    │   ├── files.py        # read_file / write_file / list_dir (sandboxed)
    │   └── shell.py        # shell + python_exec
    ├── logs/
    │   ├── __init__.py
    │   └── logger.py       # ActionLogger: rotating text + JSONL
    ├── templates/
    │   └── system_prompt.txt  # multi-tool ReAct instructions
    └── utils/
        ├── __init__.py
        └── helpers.py      # atomic IO, truncation, timestamps
```

For a full module-by-module reference, architecture diagrams, the ReAct loop
walkthrough, and extension guides, see **[DOCUMENTATION.md](DOCUMENTATION.md)**.

---

## ⚙️ Configuration

All settings are read from `.env` (see `.env.example`), overridable via CLI (`--model`, `--max-iterations`, `--mock`):

| Variable | Meaning | Default |
|----------|---------|---------|
| `OPENROUTER_API_KEY` (or `OPENAI_API_KEY`, `LLM_API_KEY`) | API key | none (→ mock) |
| `BASE_URL` (or `OPENROUTER_BASE_URL`, `OPENAI_BASE_URL`) | Endpoint base URL | `https://openrouter.ai/api/v1` |
| `MODEL` (or `OPENROUTER_MODEL`, `OPENAI_MODEL`) | Model name | `gpt-4o-mini` |
| `LLM_USE_MOCK` | `1`/`true`/`yes`/`on` forces mock mode | off if key present |
| `REACT_MAX_ITERATIONS` | Max ReAct steps (graceful answer at limit) | `8` |
| `TOOL_TIMEOUT_SECONDS` | Tool execution timeout (enforced) | `15` |
| `LLM_TIMEOUT_SECONDS` | HTTP timeout per attempt | `60` |
| `LLM_MAX_RETRIES` | Retries on 429/5xx/network | `2` |
| `LLM_TEMPERATURE` | Sampling temperature | `0.2` |
| `WORKSPACE_ROOT` | Sandbox root for file/shell tools | project root |
| `MAX_HISTORY_RECORDS` | Cap on stored history | `200` |
| `MAX_SCRATCHPAD_CHARS` | Cap on cross-iteration reasoning | `12000` |

---

## 📤 Output Locations

- **Console** — live prompts and answers.
- `react_assistant/logs/assistant.log` — human-readable activity log (rotating).
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

Rules: unique `name`, no alias collisions (raises on conflict), input ≤ 8000 chars, output truncated at 8000 chars, honor the registry timeout.

**Switch provider/model** — edit `.env` (`BASE_URL`, `MODEL`, key) or pass `--model`. Any OpenAI-compatible API works.

**Customize behavior** — edit `react_assistant/templates/system_prompt.txt` (hot-reloaded by mtime) to change agent instructions without touching code.

---

## 🤝 Contributing

1. Fork and create a feature branch.
2. Keep dependencies minimal; prefer the standard library.
3. Run the assistant in mock mode (`--mock` or `LLM_USE_MOCK=1`) for quick local testing.
4. Open a pull request with a clear description.

---

## 📄 License

Released under the [MIT License](LICENSE).
