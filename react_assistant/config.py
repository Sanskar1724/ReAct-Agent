from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_HISTORY_PATH = PACKAGE_ROOT / "memory" / "history.json"
DEFAULT_LOG_DIR = PACKAGE_ROOT / "logs"
DEFAULT_SYSTEM_PROMPT_PATH = PACKAGE_ROOT / "templates" / "system_prompt.txt"
DEFAULT_WORKSPACE_ROOT = PROJECT_ROOT


def _safe_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = int(str(raw).strip())
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, value))


def _safe_float(name: str, default: float, minimum: float, maximum: float) -> float:
    raw = os.getenv(name, "")
    if raw is None or str(raw).strip() == "":
        return default
    try:
        value = float(str(raw).strip())
    except (ValueError, TypeError):
        return default
    return max(minimum, min(maximum, value))


@dataclass(slots=True)
class AppConfig:
    api_key: str | None
    api_base_url: str
    model: str
    max_iterations: int
    history_path: Path
    log_dir: Path
    system_prompt_path: Path
    tool_timeout_seconds: int
    use_mock_llm: bool
    llm_timeout_seconds: int
    llm_max_retries: int
    llm_temperature: float
    workspace_root: Path
    max_history_records: int
    max_scratchpad_chars: int

    @classmethod
    def load(cls, overrides: dict | None = None) -> "AppConfig":
        if load_dotenv is not None:
            # Do NOT override real env vars with .env values.
            load_dotenv(PROJECT_ROOT / ".env", override=False)

        if overrides:
            for key, value in overrides.items():
                if value is not None:
                    os.environ[str(key)] = str(value)

        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        # Treat placeholder values as missing so we fall back to mock mode.
        if api_key and api_key.strip().lower() in {"", "your_api_key_here", "none", "null"}:
            api_key = None
        api_base_url = (
            os.getenv("BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
        model = os.getenv("MODEL") or os.getenv(
            "OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        max_iterations = _safe_int("REACT_MAX_ITERATIONS", 8, 1, 20)
        tool_timeout_seconds = _safe_int("TOOL_TIMEOUT_SECONDS", 15, 1, 120)
        llm_timeout_seconds = _safe_int("LLM_TIMEOUT_SECONDS", 60, 5, 300)
        llm_max_retries = _safe_int("LLM_MAX_RETRIES", 2, 0, 5)
        llm_temperature = _safe_float("LLM_TEMPERATURE", 0.2, 0.0, 2.0)
        max_history_records = _safe_int("MAX_HISTORY_RECORDS", 200, 10, 5000)
        max_scratchpad_chars = _safe_int("MAX_SCRATCHPAD_CHARS", 12000, 2000, 60000)
        use_mock_llm = os.getenv("LLM_USE_MOCK", "").lower() in {
            "1", "true", "yes", "on"} or not api_key

        workspace_raw = os.getenv("WORKSPACE_ROOT", "").strip()
        workspace_root = Path(workspace_raw).resolve() if workspace_raw else DEFAULT_WORKSPACE_ROOT.resolve()

        return cls(
            api_key=api_key,
            api_base_url=api_base_url,
            model=model,
            max_iterations=max_iterations,
            history_path=DEFAULT_HISTORY_PATH,
            log_dir=DEFAULT_LOG_DIR,
            system_prompt_path=DEFAULT_SYSTEM_PROMPT_PATH,
            tool_timeout_seconds=tool_timeout_seconds,
            use_mock_llm=use_mock_llm,
            llm_timeout_seconds=llm_timeout_seconds,
            llm_max_retries=llm_max_retries,
            llm_temperature=llm_temperature,
            workspace_root=workspace_root,
            max_history_records=max_history_records,
            max_scratchpad_chars=max_scratchpad_chars,
        )
