from __future__ import annotations

import asyncio
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .ai import AIClient
from .config import Settings
from .kb import KnowledgeBaseWriter
from .pipeline import Job, PipelineService
from .rate_limit import RateLimiter
from .storage import Storage


class RevisionBot:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.storage = Storage(settings.data_dir / "bot.db")
        self.application = ApplicationBuilder().token(settings.telegram_bot_token).build()
        self.pipeline = PipelineService(
            storage=self.storage,
            ai_client=AIClient(settings),
            kb_writer=KnowledgeBaseWriter(settings.knowledge_base_dir, settings.git_commit_enabled),
            bot=self.application.bot,
            rate_limiter=RateLimiter(settings.per_chat_rate_limit, settings.per_chat_rate_window_seconds),
            assets_dir=settings.data_dir / "images",
        )
        self._worker_task: asyncio.Task | None = None
        self._register_handlers()
        self.application.post_init = self._post_init

    def _register_handlers(self) -> None:
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status))
        self.application.add_handler(CommandHandler("save", self.save))
        self.application.add_handler(CommandHandler("discard", self.discard))
        self.application.add_handler(CommandHandler("topic", self.topic))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.photo))
        self.application.add_handler(MessageHandler(filters.VOICE, self.voice))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text))

    async def _post_init(self, application: Application) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self.pipeline.worker_loop())

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(
            "Send a COMP9414 question image, then add your own solution text. "
            "Use /status to inspect the draft and /save to write the final Markdown note."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(
            "/status - show the active draft\n"
            "/topic <slug> - override topic\n"
            "/save - generate and save the article\n"
            "/discard - drop the active draft\n\n"
            "This MVP fully supports images and text. Voice and links are placeholders."
        )

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        draft = self.storage.get_active_draft(chat_id)
        await update.effective_message.reply_text(self.pipeline.format_status(draft))

    async def save(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        if self._should_ignore(update):
            return
        try:
            await self.pipeline.enqueue(Job(kind="save", chat_id=chat_id, payload={}))
        except RuntimeError as exc:
            await update.effective_message.reply_text(str(exc))
            return
        self.storage.mark_update_processed(update.update_id)
        await update.effective_message.reply_text("Queued save job. I will reply again after the note is written.")

    async def discard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        removed = self.storage.discard_active_draft(chat_id)
        if removed:
            await update.effective_message.reply_text("Discarded the active draft.")
        else:
            await update.effective_message.reply_text("No active draft to discard.")

    async def topic(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id
        draft = self.storage.get_active_draft(chat_id)
        if draft is None:
            await update.effective_message.reply_text("No active draft. Send an image first.")
            return
        if not context.args:
            await update.effective_message.reply_text("Usage: /topic <slug>")
            return
        topic = " ".join(context.args).strip()
        self.storage.set_topic(draft.draft_id, topic)
        await update.effective_message.reply_text(f"Topic set to {topic}.")

    async def photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._should_ignore(update):
            return
        message = update.effective_message
        chat_id = update.effective_chat.id
        photo = message.photo[-1]
        tg_file = await photo.get_file()
        file_bytes = await tg_file.download_as_bytearray()
        try:
            await self.pipeline.enqueue(
                Job(
                    kind="photo",
                    chat_id=chat_id,
                    payload={
                        "file_bytes": bytes(file_bytes),
                        "file_ext": "png",
                        "message_id": message.message_id,
                    },
                )
            )
        except RuntimeError as exc:
            await message.reply_text(str(exc))
            return
        self.storage.mark_update_processed(update.update_id)
        await message.reply_text("Image received. I queued question extraction.")

    async def text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._should_ignore(update):
            return
        message = update.effective_message
        try:
            await self.pipeline.enqueue(
                Job(
                    kind="text",
                    chat_id=update.effective_chat.id,
                    payload={"text": message.text, "message_id": message.message_id},
                )
            )
        except RuntimeError as exc:
            await message.reply_text(str(exc))
            return
        self.storage.mark_update_processed(update.update_id)
        await message.reply_text("Text received. I queued it into the current draft.")

    async def voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self._should_ignore(update):
            return
        self.storage.mark_update_processed(update.update_id)
        await update.effective_message.reply_text(
            "Voice support is scaffolded but not implemented in this MVP. "
            "For now, send the solution as text."
        )

    def _should_ignore(self, update: Update) -> bool:
        return self.storage.has_processed_update(update.update_id)

    def run(self) -> None:
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
