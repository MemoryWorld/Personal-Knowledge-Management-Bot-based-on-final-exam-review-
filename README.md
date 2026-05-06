# COMP9414 PKM Bot

A Telegram bot MVP for revising `UNSW COMP9414` with image-first question intake.

You send:
- a question screenshot or PNG
- your own solution text

The bot:
- extracts the question from the image
- classifies the topic
- keeps an active draft per chat
- generates a structured Markdown article
- saves it into a local Git-backed knowledge base

## Features

- Telegram bot flow with `/status`, `/save`, `/discard`, `/topic`
- Multi-step draft workflow for `image + text`
- SQLite persistence for drafts and processed Telegram updates
- Async worker queue so Telegram handlers stay thin
- OpenAI vision + text pipeline
- Knowledge base writer with Git commits
- Basic per-chat rate limiting
- Voice and link handlers kept as extension points

## Project Layout

- `src/comp9414_pkm_bot/bot.py`: Telegram handlers and app wiring
- `src/comp9414_pkm_bot/pipeline.py`: queue jobs and orchestration
- `src/comp9414_pkm_bot/storage.py`: SQLite persistence
- `src/comp9414_pkm_bot/ai.py`: OpenAI extraction, classification, synthesis
- `src/comp9414_pkm_bot/kb.py`: Markdown writing and Git commit flow
- `tests/`: unit tests for storage and knowledge base writing

## Quick Start

```bash
cd /Users/hongyu_chen/comp9414-pkm-bot
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
```

Set the environment variables in `.env`, then run:

```bash
source .env
comp9414-pkm-bot
```

## Telegram Workflow

1. Send a question image.
2. Send your solution text in one or more follow-up messages.
3. Optional: run `/topic bayes-nets` to override the AI topic.
4. Run `/status` to inspect the current draft.
5. Run `/save` to generate the final article and write it to `knowledge-base/`.

## Knowledge Base Output

Articles are grouped by topic, for example:

```text
knowledge-base/
  search/
  logic/
  bayes-nets/
  mdp/
```

Each article contains:
- parsed question
- your raw solution
- polished solution
- key concepts
- common mistakes
- review prompts

## Current MVP Boundary

- Fully supported: images, text, draft persistence, article generation
- Skeleton only: voice transcription and link extraction
- No vector search or web UI yet
