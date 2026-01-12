import asyncio
import logging
from typing import Iterable

import google.generativeai as genai

from app.core.config import get_settings

# 로거 설정
logger = logging.getLogger(__name__)

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
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        prompt = self._build_prompt(messages, question)
        result = model.generate_content(prompt)
        return result.text.strip()

    async def summarize(self, messages: list[str], question: str | None = None) -> str:
        if not messages:
            return "아직 대화가 없어요."
        try:
            if not self.enabled:
                raise RuntimeError("Gemini disabled")
            
            # 최신 대화 40개를 요약 (뒤에서부터 슬라이싱)
            return await asyncio.to_thread(self._summarize_sync, messages[-40:], question)
            
        except Exception as e:
            # 에러 로그 출력 (이제 404가 사라지고 정상 작동할 것입니다)
            logger.error(f"Gemini API Error: {e}")
            
            # 로컬 폴백: 최신 메시지 6개 보여주기
            tail = messages[-6:]
            lines = "\n".join([f"- {m}" for m in tail]) if tail else "요약할 메시지가 부족합니다."
            return f"AI 요약이 준비되지 않아 최근 메시지를 그대로 보여드려요:\n{lines}"


def get_gemini_summarizer() -> GeminiSummarizer:
    settings = get_settings()
    return GeminiSummarizer(settings.gemini_api_key)
