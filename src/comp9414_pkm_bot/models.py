from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class DraftSession:
    chat_id: int
    draft_id: int
    topic: str | None
    question_text: str
    question_summary: str
    user_solution_text: str
    image_paths: list[str] = field(default_factory=list)
    source_message_ids: list[int] = field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ExtractedQuestion:
    question_text: str
    question_summary: str
    topic: str
    key_concepts: list[str]
    source_refs: list[str]


@dataclass
class SynthesizedArticle:
    title: str
    topic: str
    question_summary: str
    parsed_question: str
    user_solution: str
    polished_solution: str
    key_concepts: list[str]
    common_mistakes: list[str]
    review_prompts: list[str]
    tags: list[str]
    source_refs: list[str]


@dataclass
class SavedArticle:
    file_path: Path
    git_commit_sha: str | None
    created_at: datetime
