from pathlib import Path

from comp9414_pkm_bot.kb import KnowledgeBaseWriter
from comp9414_pkm_bot.models import SynthesizedArticle


def test_kb_writer_saves_markdown(tmp_path: Path) -> None:
    writer = KnowledgeBaseWriter(tmp_path / "knowledge-base", git_commit_enabled=False)
    article = SynthesizedArticle(
        title="A Star Heuristic Choice",
        topic="search",
        question_summary="Compare admissible and consistent heuristics.",
        parsed_question="Explain the difference between admissible and consistent heuristics.",
        user_solution="Admissible means never overestimate.",
        polished_solution="Consistent heuristics satisfy the triangle inequality and imply admissibility.",
        key_concepts=["admissible heuristic", "consistent heuristic"],
        common_mistakes=["assuming all admissible heuristics are consistent"],
        review_prompts=["Why does consistency matter for graph search?"],
        tags=["search", "astar"],
        source_refs=["telegram:image"],
    )

    saved = writer.save_article(article)

    assert saved.file_path.exists()
    content = saved.file_path.read_text(encoding="utf-8")
    assert "# A Star Heuristic Choice" in content
    assert "## Polished Solution" in content
    assert "consistent heuristics" in content
