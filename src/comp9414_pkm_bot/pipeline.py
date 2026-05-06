from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from telegram import Bot

from .ai import AIClient
from .kb import KnowledgeBaseWriter
from .models import DraftSession
from .rate_limit import RateLimiter
from .storage import Storage


def _contains_url(text: str) -> bool:
    for token in text.split():
        parsed = urlparse(token)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return True
    return False


@dataclass
class Job:
    kind: str
    chat_id: int
    payload: dict


class PipelineService:
    def __init__(
        self,
        *,
        storage: Storage,
        ai_client: AIClient,
        kb_writer: KnowledgeBaseWriter,
        bot: Bot,
        rate_limiter: RateLimiter,
        assets_dir: Path,
    ) -> None:
        self.storage = storage
        self.ai_client = ai_client
        self.kb_writer = kb_writer
        self.bot = bot
        self.rate_limiter = rate_limiter
        self.assets_dir = assets_dir
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.queue: asyncio.Queue[Job] = asyncio.Queue()

    async def enqueue(self, job: Job) -> None:
        if not self.rate_limiter.allow(job.chat_id):
            raise RuntimeError("Rate limit exceeded for this chat")
        await self.queue.put(job)

    async def worker_loop(self) -> None:
        while True:
            job = await self.queue.get()
            try:
                if job.kind == "photo":
                    await self._handle_photo(job.chat_id, **job.payload)
                elif job.kind == "text":
                    await self._handle_text(job.chat_id, **job.payload)
                elif job.kind == "save":
                    await self._handle_save(job.chat_id)
            except Exception as exc:  # pragma: no cover - defensive runtime path
                await self.bot.send_message(
                    chat_id=job.chat_id,
                    text=f"Processing failed: {exc}",
                )
            finally:
                self.queue.task_done()

    async def _handle_photo(self, chat_id: int, *, file_bytes: bytes, file_ext: str, message_id: int) -> None:
        draft = self.storage.get_or_create_active_draft(chat_id, source_message_id=message_id)
        image_path = self.assets_dir / f"chat-{chat_id}-draft-{draft.draft_id}-msg-{message_id}.{file_ext}"
        image_path.write_bytes(file_bytes)
        self.storage.add_image(draft.draft_id, str(image_path))

        extracted = await self.ai_client.extract_question_from_image(image_path)
        topic = extracted.topic or await self.ai_client.classify_topic(extracted.question_text)
        self.storage.merge_question_content(
            draft.draft_id,
            question_text=extracted.question_text,
            question_summary=extracted.question_summary,
            topic=topic,
        )
        await self.bot.send_message(
            chat_id=chat_id,
            text=(
                "Question image added to the current draft.\n\n"
                f"Topic: {topic}\n"
                f"Summary: {extracted.question_summary}\n\n"
                "Now send your solution text, then use /save when ready."
            ),
        )

    async def _handle_text(self, chat_id: int, *, text: str, message_id: int) -> None:
        draft = self.storage.get_or_create_active_draft(chat_id, source_message_id=message_id)
        note = text.strip()
        if _contains_url(note):
            note = (
                f"{note}\n\n"
                "[Note: link detected. Full link extraction is not implemented in this MVP.]"
            )
        self.storage.append_user_solution(draft.draft_id, note)
        await self.bot.send_message(
            chat_id=chat_id,
            text="Text added to the current draft. Use /status to inspect it or /save to generate the note.",
        )

    async def _handle_save(self, chat_id: int) -> None:
        draft = self.storage.get_active_draft(chat_id)
        if draft is None:
            await self.bot.send_message(chat_id=chat_id, text="No active draft to save.")
            return
        if not draft.question_text.strip():
            await self.bot.send_message(chat_id=chat_id, text="The current draft has no parsed question yet.")
            return
        article = await self.ai_client.synthesize_article(
            topic=draft.topic or "uncategorized",
            question_text=draft.question_text,
            question_summary=draft.question_summary or "No summary available.",
            user_solution=draft.user_solution_text,
        )
        markdown = self.kb_writer.build_markdown(article)
        target_path = self.kb_writer.target_path_for(article)
        try:
            saved = self.kb_writer.save_article(article)
            self.storage.mark_draft_saved(draft.draft_id)
            await self.bot.send_message(
                chat_id=chat_id,
                text=(
                    "Saved revision note.\n\n"
                    f"File: {saved.file_path}\n"
                    f"Git commit: {saved.git_commit_sha or 'not committed'}"
                ),
            )
        except Exception as exc:  # pragma: no cover - defensive runtime path
            self.storage.save_pending_article(
                draft_id=draft.draft_id,
                markdown=markdown,
                target_path=str(target_path),
                error=str(exc),
            )
            await self.bot.send_message(
                chat_id=chat_id,
                text="Article generation succeeded, but writing to the knowledge base failed. Content was stored as pending.",
            )

    def format_status(self, draft: DraftSession | None) -> str:
        if draft is None:
            return "No active draft. Send a question image to start one."
        return (
            f"Draft ID: {draft.draft_id}\n"
            f"Topic: {draft.topic or 'unclassified'}\n"
            f"Images: {len(draft.image_paths)}\n"
            f"Question summary: {draft.question_summary or 'none yet'}\n"
            f"Question chars: {len(draft.question_text)}\n"
            f"Solution chars: {len(draft.user_solution_text)}\n"
            f"Updated: {draft.updated_at}"
        )
