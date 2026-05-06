from pathlib import Path

from comp9414_pkm_bot.storage import Storage


def test_storage_persists_active_draft(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "bot.db")
    draft = storage.get_or_create_active_draft(chat_id=42, source_message_id=1)
    storage.merge_question_content(draft.draft_id, "What is A*?", "Search question", "search")
    storage.append_user_solution(draft.draft_id, "Use admissible heuristic.")

    reopened = Storage(tmp_path / "bot.db")
    saved = reopened.get_active_draft(42)

    assert saved is not None
    assert saved.topic == "search"
    assert "What is A*?" in saved.question_text
    assert "admissible heuristic" in saved.user_solution_text
    assert saved.source_message_ids == [1]


def test_discard_active_draft(tmp_path: Path) -> None:
    storage = Storage(tmp_path / "bot.db")
    storage.get_or_create_active_draft(chat_id=7, source_message_id=3)

    removed = storage.discard_active_draft(7)

    assert removed is True
    assert storage.get_active_draft(7) is None
