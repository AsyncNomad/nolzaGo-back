import asyncio
from typing import Iterable

import google.generativeai as genai

from app.core.config import get_settings


class GeminiSummarizer:
    def __init__(self, api_key: str | None):
        self.api_key = api_key
        self.enabled = bool(api_key)
        if self.enabled:
            genai.configure(api_key=api_key)

    def _build_prompt(self, messages: Iterable[str], question: str | None = None) -> str:
        header = (
            "아래 단체 채팅 메시지를 한국어로 3줄 요약해줘. "
            "핵심 결정/시간/장소와 새로 합류한 사용자가 알아야 할 맥락만 담아줘."
        )
        if question:
            header += f" 또한 사용자의 질문에 답해줘: {question}"
        joined = "\n".join(messages)
        return f"{header}\n\n{joined}"

    def _summarize_sync(self, messages: list[str], question: str | None = None) -> str:
        model = genai.GenerativeModel("gemini-pro")
        prompt = self._build_prompt(messages, question)
        result = model.generate_content(prompt)
        return result.text.strip()

    async def summarize(self, messages: list[str], question: str | None = None) -> str:
        if not self.enabled or not messages:
            return "채팅 요약 준비 중입니다."
        try:
            return await asyncio.to_thread(self._summarize_sync, messages[:40], question)
        except Exception:
            # Gracefully degrade if API fails or quota exceeded
            return "요약을 불러오지 못했습니다. 잠시 후 다시 시도해주세요."


def get_gemini_summarizer() -> GeminiSummarizer:
    settings = get_settings()
    return GeminiSummarizer(settings.gemini_api_key)
