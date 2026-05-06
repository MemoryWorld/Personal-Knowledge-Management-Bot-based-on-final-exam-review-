from __future__ import annotations

import os
from pathlib import Path

from .bot import RevisionBot
from .config import Settings


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    _load_dotenv(Path(".env"))
    settings = Settings.from_env()
    bot = RevisionBot(settings)
    bot.run()


if __name__ == "__main__":
    main()
