# COMP9414 Revision Bot

Telegram bot for turning `UNSW COMP9414` exam screenshots into structured revision notes.

You send a PNG plus your own solution text. The bot extracts the question, classifies the topic, and writes a polished Markdown article into a Git-backed knowledge base.

## Why this project matters

- Real multi-modal intake: screenshots today, voice and links as planned extensions
- Agent-style orchestration: extract, classify, synthesize, then persist
- Production habits: SQLite session state, idempotent updates, queueing, retries, rate limiting
- Git as a knowledge base: every note becomes a versioned Markdown file

## Demo Flow

1. Send a question screenshot.
2. Add your own solution in follow-up text messages.
3. Optionally override the topic with `/topic search`.
4. Run `/status` to inspect the active draft.
5. Run `/save` to generate the final article.

## What the bot produces

- Question summary
- Parsed question text
- Your raw solution
- Polished solution
- Key concepts
- Common mistakes
- Review prompts
- Tags and source refs

## Architecture

```text
Telegram -> queue -> AI extraction/classification -> draft state -> Markdown writer -> Git commit
```

Core modules:

- `src/comp9414_pkm_bot/bot.py`: Telegram commands and message handlers
- `src/comp9414_pkm_bot/pipeline.py`: job queue and orchestration
- `src/comp9414_pkm_bot/ai.py`: OpenAI vision and text calls
- `src/comp9414_pkm_bot/storage.py`: SQLite persistence for drafts and idempotency
- `src/comp9414_pkm_bot/kb.py`: Markdown generation and Git commit flow

## Screenshots

Put captured images in `docs/screenshots/` and reference them here.

Recommended screenshots:

1. `01-start-and-status.png`: bot welcome message plus `/status` output with an empty draft
2. `02-image-ingest.png`: sending a COMP9414 PNG and the extraction acknowledgement
3. `03-solution-notes.png`: adding your own solution text into the same draft
4. `04-save-result.png`: `/save` output and the generated Markdown file path
5. `05-git-history.png`: Git log showing the note commit

Suggested captions:

- "Send a screenshot, then continue the same draft with text."
- "The bot keeps the current exam question in persistent storage."
- "Saved notes are written as versioned Markdown articles."

## Tech Stack

- Python
- `python-telegram-bot`
- OpenAI API
- SQLite
- Git
- `pytest`

## Local Setup

```bash
cd /Users/hongyu_chen/comp9414-pkm-bot
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env
```

Set `TELEGRAM_BOT_TOKEN` and `OPENAI_API_KEY` in `.env`, then run:

```bash
comp9414-pkm-bot
```

## Knowledge Base Layout

```text
knowledge-base/
  search/
  logic/
  bayes-nets/
  mdp/
```

Each topic directory contains one Markdown file per question, named with the date and a slug.

## Scope

- Fully working: image intake, text follow-up, draft persistence, structured article generation
- Scaffolded only: voice transcription and link extraction
- Not included: vector search, web UI, or multi-user permissions

## Safety

- No secrets are committed to the repository
- `.env` is ignored by Git
- API tokens stay local to your machine
