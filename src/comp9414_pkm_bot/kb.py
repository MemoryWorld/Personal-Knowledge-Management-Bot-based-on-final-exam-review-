from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .models import SavedArticle, SynthesizedArticle


def slugify(value: str) -> str:
    lowered = value.lower().strip()
    chars = []
    last_dash = False
    for char in lowered:
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True
    slug = "".join(chars).strip("-")
    return slug or "untitled"


def bullet_lines(items: list[str]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)


class KnowledgeBaseWriter:
    def __init__(self, root_dir: Path, git_commit_enabled: bool) -> None:
        self.root_dir = root_dir
        self.git_commit_enabled = git_commit_enabled
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def build_markdown(self, article: SynthesizedArticle) -> str:
        return f"""# {article.title}

Course: COMP9414
Topic: {article.topic}
Tags: {", ".join(article.tags) if article.tags else article.topic}

## Question Summary

{article.question_summary}

## Parsed Question

{article.parsed_question}

## Your Solution

{article.user_solution or "_No user solution provided._"}

## Polished Solution

{article.polished_solution}

## Key Concepts

{bullet_lines(article.key_concepts)}

## Common Mistakes

{bullet_lines(article.common_mistakes)}

## Review Prompts

{bullet_lines(article.review_prompts)}

## Source

{bullet_lines(article.source_refs)}
"""

    def target_path_for(self, article: SynthesizedArticle) -> Path:
        date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        topic_dir = self.root_dir / slugify(article.topic)
        topic_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{date_prefix}-{slugify(article.topic)}-{slugify(article.title)[:60]}.md"
        return topic_dir / file_name

    def save_article(self, article: SynthesizedArticle) -> SavedArticle:
        path = self.target_path_for(article)
        markdown = self.build_markdown(article)
        path.write_text(markdown, encoding="utf-8")
        commit_sha = None
        if self.git_commit_enabled:
            commit_sha = self._git_commit(path, article.title)
        return SavedArticle(file_path=path, git_commit_sha=commit_sha, created_at=datetime.now(timezone.utc))

    def _git_commit(self, path: Path, title: str) -> str | None:
        try:
            subprocess.run(
                ["git", "add", str(path)],
                cwd=self.root_dir.parent,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"Add COMP9414 note: {title}"],
                cwd=self.root_dir.parent,
                check=True,
                capture_output=True,
                text=True,
            )
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root_dir.parent,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None
