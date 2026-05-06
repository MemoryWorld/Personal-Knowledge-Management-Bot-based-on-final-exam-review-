from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import DraftSession


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS drafts (
                    draft_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    topic TEXT,
                    question_text TEXT NOT NULL DEFAULT '',
                    question_summary TEXT NOT NULL DEFAULT '',
                    user_solution_text TEXT NOT NULL DEFAULT '',
                    image_paths TEXT NOT NULL DEFAULT '[]',
                    source_message_ids TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_drafts_chat_status
                ON drafts(chat_id, status);

                CREATE TABLE IF NOT EXISTS processed_updates (
                    update_id INTEGER PRIMARY KEY,
                    processed_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_articles (
                    draft_id INTEGER PRIMARY KEY,
                    markdown TEXT NOT NULL,
                    target_path TEXT NOT NULL,
                    error TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def has_processed_update(self, update_id: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_updates WHERE update_id = ?",
                (update_id,),
            ).fetchone()
        return row is not None

    def mark_update_processed(self, update_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO processed_updates(update_id, processed_at) VALUES(?, ?)",
                (update_id, utc_now()),
            )

    def get_active_draft(self, chat_id: int) -> DraftSession | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM drafts
                WHERE chat_id = ? AND status = 'active'
                ORDER BY draft_id DESC
                LIMIT 1
                """,
                (chat_id,),
            ).fetchone()
        return self._row_to_draft(row) if row else None

    def create_draft(self, chat_id: int, source_message_id: int | None = None) -> DraftSession:
        now = utc_now()
        source_ids = [source_message_id] if source_message_id is not None else []
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO drafts(
                    chat_id, topic, question_text, question_summary, user_solution_text,
                    image_paths, source_message_ids, status, created_at, updated_at
                ) VALUES (?, NULL, '', '', '', '[]', ?, 'active', ?, ?)
                """,
                (chat_id, json.dumps(source_ids), now, now),
            )
            draft_id = cursor.lastrowid
            row = conn.execute("SELECT * FROM drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        assert row is not None
        return self._row_to_draft(row)

    def get_or_create_active_draft(self, chat_id: int, source_message_id: int | None = None) -> DraftSession:
        draft = self.get_active_draft(chat_id)
        if draft is not None:
            if source_message_id is not None:
                self.append_source_message(draft.draft_id, source_message_id)
                draft = self.get_draft(draft.draft_id)
                assert draft is not None
            return draft
        return self.create_draft(chat_id=chat_id, source_message_id=source_message_id)

    def get_draft(self, draft_id: int) -> DraftSession | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        return self._row_to_draft(row) if row else None

    def append_source_message(self, draft_id: int, message_id: int) -> None:
        draft = self.get_draft(draft_id)
        if draft is None:
            return
        message_ids = list(draft.source_message_ids)
        if message_id not in message_ids:
            message_ids.append(message_id)
        self._update_fields(draft_id, source_message_ids=json.dumps(message_ids))

    def add_image(self, draft_id: int, image_path: str) -> None:
        draft = self.get_draft(draft_id)
        if draft is None:
            return
        image_paths = list(draft.image_paths)
        image_paths.append(image_path)
        self._update_fields(draft_id, image_paths=json.dumps(image_paths))

    def merge_question_content(
        self,
        draft_id: int,
        question_text: str,
        question_summary: str,
        topic: str | None,
    ) -> None:
        draft = self.get_draft(draft_id)
        if draft is None:
            return
        merged_question = draft.question_text.strip()
        if merged_question:
            merged_question = f"{merged_question}\n\n{question_text.strip()}".strip()
        else:
            merged_question = question_text.strip()
        summary = question_summary.strip() or draft.question_summary
        self._update_fields(
            draft_id,
            question_text=merged_question,
            question_summary=summary,
            topic=topic or draft.topic,
        )

    def append_user_solution(self, draft_id: int, text: str) -> None:
        draft = self.get_draft(draft_id)
        if draft is None:
            return
        merged = draft.user_solution_text.strip()
        if merged:
            merged = f"{merged}\n\n{text.strip()}".strip()
        else:
            merged = text.strip()
        self._update_fields(draft_id, user_solution_text=merged)

    def set_topic(self, draft_id: int, topic: str) -> None:
        self._update_fields(draft_id, topic=topic.strip())

    def mark_draft_saved(self, draft_id: int) -> None:
        self._update_fields(draft_id, status="saved")

    def discard_active_draft(self, chat_id: int) -> bool:
        draft = self.get_active_draft(chat_id)
        if draft is None:
            return False
        self._update_fields(draft.draft_id, status="discarded")
        return True

    def save_pending_article(self, draft_id: int, markdown: str, target_path: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO pending_articles(draft_id, markdown, target_path, error, created_at)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(draft_id) DO UPDATE SET
                    markdown = excluded.markdown,
                    target_path = excluded.target_path,
                    error = excluded.error,
                    created_at = excluded.created_at
                """,
                (draft_id, markdown, target_path, error, utc_now()),
            )

    def _update_fields(self, draft_id: int, **fields: object) -> None:
        if not fields:
            return
        fields["updated_at"] = utc_now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        values = list(fields.values()) + [draft_id]
        with self._connect() as conn:
            conn.execute(
                f"UPDATE drafts SET {assignments} WHERE draft_id = ?",
                values,
            )

    def _row_to_draft(self, row: sqlite3.Row) -> DraftSession:
        return DraftSession(
            chat_id=row["chat_id"],
            draft_id=row["draft_id"],
            topic=row["topic"],
            question_text=row["question_text"],
            question_summary=row["question_summary"],
            user_solution_text=row["user_solution_text"],
            image_paths=json.loads(row["image_paths"]),
            source_message_ids=json.loads(row["source_message_ids"]),
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
