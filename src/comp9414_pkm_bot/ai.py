from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

from openai import AsyncOpenAI

from .config import Settings
from .models import ExtractedQuestion, SynthesizedArticle


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract_question_from_image(self, image_path: Path) -> ExtractedQuestion:
        image_bytes = image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        prompt = (
            "You are helping a student revise UNSW COMP9414. "
            "Read the image and return JSON with keys: "
            "question_text, question_summary, topic, key_concepts, source_refs. "
            "Use concise topic names like search, logic, bayes-nets, mdp, learning, csp. "
            "If the image is partial or blurry, say so in question_summary."
        )
        response = await self._chat_json(
            model=self.settings.openai_vision_model,
            messages=[
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the COMP9414 revision question."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                },
            ],
        )
        return ExtractedQuestion(
            question_text=response["question_text"].strip(),
            question_summary=response["question_summary"].strip(),
            topic=response["topic"].strip(),
            key_concepts=[str(item).strip() for item in response.get("key_concepts", []) if str(item).strip()],
            source_refs=[str(item).strip() for item in response.get("source_refs", []) if str(item).strip()],
        )

    async def classify_topic(self, question_text: str) -> str:
        response = await self._chat_json(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify this UNSW COMP9414 question into one topic. "
                        "Return JSON with key 'topic' only. "
                        "Use one short slug like search, logic, bayes-nets, mdp, learning, csp."
                    ),
                },
                {"role": "user", "content": question_text},
            ],
        )
        return str(response["topic"]).strip()

    async def synthesize_article(
        self,
        *,
        topic: str,
        question_text: str,
        question_summary: str,
        user_solution: str,
    ) -> SynthesizedArticle:
        polished_task = self._chat_json(
            model=self.settings.openai_reasoning_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are polishing study notes for UNSW COMP9414. "
                        "Return JSON with keys: title, polished_solution, key_concepts, tags."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic}\n\n"
                        f"Question summary:\n{question_summary}\n\n"
                        f"Question text:\n{question_text}\n\n"
                        f"Student solution:\n{user_solution}"
                    ),
                },
            ],
        )
        review_task = self._chat_json(
            model=self.settings.openai_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate revision aids for a COMP9414 question. "
                        "Return JSON with keys: common_mistakes, review_prompts, source_refs."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic}\n\n"
                        f"Question summary:\n{question_summary}\n\n"
                        f"Question text:\n{question_text}\n\n"
                        f"Student solution:\n{user_solution}"
                    ),
                },
            ],
        )
        polished, review = await asyncio.gather(polished_task, review_task)
        return SynthesizedArticle(
            title=str(polished["title"]).strip(),
            topic=topic,
            question_summary=question_summary,
            parsed_question=question_text,
            user_solution=user_solution.strip(),
            polished_solution=str(polished["polished_solution"]).strip(),
            key_concepts=[str(item).strip() for item in polished.get("key_concepts", []) if str(item).strip()],
            common_mistakes=[str(item).strip() for item in review.get("common_mistakes", []) if str(item).strip()],
            review_prompts=[str(item).strip() for item in review.get("review_prompts", []) if str(item).strip()],
            tags=[str(item).strip() for item in polished.get("tags", []) if str(item).strip()],
            source_refs=[str(item).strip() for item in review.get("source_refs", []) if str(item).strip()],
        )

    async def _chat_json(self, *, model: str, messages: list[dict]) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.openai_max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    response_format={"type": "json_object"},
                    messages=messages,
                )
                content = response.choices[0].message.content or "{}"
                return json.loads(content)
            except Exception as exc:  # pragma: no cover - exercised through retries
                last_error = exc
                if attempt == self.settings.openai_max_retries:
                    break
                await asyncio.sleep(min(2**attempt, 8))
        assert last_error is not None
        raise last_error
