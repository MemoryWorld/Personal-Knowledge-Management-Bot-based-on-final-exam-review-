from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_model: str
    openai_vision_model: str
    openai_reasoning_model: str
    data_dir: Path
    knowledge_base_dir: Path
    git_commit_enabled: bool
    per_chat_rate_limit: int
    per_chat_rate_window_seconds: int
    openai_max_retries: int

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")

        data_dir = Path(os.getenv("BOT_DATA_DIR", "./data")).expanduser().resolve()
        kb_dir = Path(os.getenv("KNOWLEDGE_BASE_DIR", "./knowledge-base")).expanduser().resolve()

        return cls(
            telegram_bot_token=token,
            openai_api_key=api_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            openai_vision_model=os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini"),
            openai_reasoning_model=os.getenv("OPENAI_REASONING_MODEL", "gpt-4.1"),
            data_dir=data_dir,
            knowledge_base_dir=kb_dir,
            git_commit_enabled=_bool_env("GIT_COMMIT_ENABLED", True),
            per_chat_rate_limit=int(os.getenv("PER_CHAT_RATE_LIMIT", "6")),
            per_chat_rate_window_seconds=int(os.getenv("PER_CHAT_RATE_WINDOW_SECONDS", "60")),
            openai_max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
        )
