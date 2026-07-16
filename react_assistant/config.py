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

    @classmethod
    def load(cls) -> "AppConfig":
        if load_dotenv is not None:
            load_dotenv(PROJECT_ROOT / ".env", override=True)

        api_key = (
            os.getenv("OPENROUTER_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or os.getenv("LLM_API_KEY")
        )
        api_base_url = (
            os.getenv("BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://openrouter.ai/api/v1"
        )
        model = os.getenv("MODEL") or os.getenv(
            "OPENROUTER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        max_iterations = int(os.getenv("REACT_MAX_ITERATIONS", "6"))
        tool_timeout_seconds = int(os.getenv("TOOL_TIMEOUT_SECONDS", "10"))
        use_mock_llm = os.getenv("LLM_USE_MOCK", "").lower() in {
            "1", "true", "yes", "on"} or not api_key

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
        )
