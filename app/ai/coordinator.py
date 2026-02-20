"""AI 에이전트팀 코디네이터 - 메시지를 적절한 에이전트에게 라우팅."""
from __future__ import annotations

import asyncio
from enum import Enum
from typing import Optional

from .agents import BaseAgent, GeminiAgent, Message, OpenAIAgent


class AgentMode(str, Enum):
    """에이전트 선택 모드."""

    AUTO = "auto"       # 키워드 기반 자동 선택
    GEMINI = "gemini"   # Gemini 단독 사용
    OPENAI = "openai"   # ChatGPT 단독 사용
    PARALLEL = "parallel"  # 두 에이전트 동시 실행 후 결과 모두 반환


# 각 에이전트가 잘 처리하는 키워드 집합
_GEMINI_KEYWORDS = {
    "고객", "스타일", "헤어", "추천", "예약", "컬러", "펌", "염색", "트렌드",
    "케어", "샴푸", "두피", "볼륨", "레이어", "뱅", "웨이브", "스트레이트",
}
_OPENAI_KEYWORDS = {
    "분석", "통계", "매출", "보고서", "데이터", "최적화", "효율", "수익",
    "비용", "전략", "마케팅", "성과", "kpi", "인사이트", "예측",
}


class AgentTeamCoordinator:
    """Gemini + ChatGPT 에이전트팀을 조율하는 코디네이터."""

    def __init__(self) -> None:
        self.gemini: BaseAgent = GeminiAgent()
        self.openai: BaseAgent = OpenAIAgent()

    # ── 에이전트 상태 조회 ────────────────────────────────────────────────────

    def status(self) -> list[dict]:
        """각 에이전트의 이름·설명·모델·가용 여부를 반환."""
        agents = [self.gemini, self.openai]
        return [
            {
                "id": a.provider,
                "name": a.name,
                "description": a.description,
                "model": a.model,
                "available": a.is_available(),
            }
            for a in agents
        ]

    # ── 자동 라우팅 ───────────────────────────────────────────────────────────

    def _auto_route(self, message: str) -> str:
        """키워드 점수 기반으로 최적 에이전트를 선택."""
        msg_lower = message.lower()
        gemini_score = sum(1 for kw in _GEMINI_KEYWORDS if kw in msg_lower)
        openai_score = sum(1 for kw in _OPENAI_KEYWORDS if kw in msg_lower)

        gemini_ok = self.gemini.is_available()
        openai_ok = self.openai.is_available()

        if gemini_ok and not openai_ok:
            return "gemini"
        if openai_ok and not gemini_ok:
            return "openai"
        # 둘 다 가용하면 점수로 결정; 동점이면 Gemini 우선
        return "openai" if openai_score > gemini_score else "gemini"

    # ── 메인 채팅 인터페이스 ──────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        mode: AgentMode = AgentMode.AUTO,
        history: Optional[list[Message]] = None,
    ) -> dict:
        """메시지를 선택된 모드로 처리하고 결과를 반환."""
        if mode == AgentMode.GEMINI:
            return {
                "mode": "gemini",
                "gemini": await self.gemini.chat(message, history),
                "openai": None,
            }

        if mode == AgentMode.OPENAI:
            return {
                "mode": "openai",
                "gemini": None,
                "openai": await self.openai.chat(message, history),
            }

        if mode == AgentMode.PARALLEL:
            gemini_task = asyncio.create_task(self.gemini.chat(message, history))
            openai_task = asyncio.create_task(self.openai.chat(message, history))
            results = await asyncio.gather(gemini_task, openai_task, return_exceptions=True)

            def _result(r: object) -> str:
                return str(r) if isinstance(r, Exception) else r  # type: ignore[return-value]

            return {
                "mode": "parallel",
                "gemini": _result(results[0]),
                "openai": _result(results[1]),
            }

        # AUTO 모드
        selected = self._auto_route(message)
        if selected == "gemini":
            return {
                "mode": "auto→gemini",
                "gemini": await self.gemini.chat(message, history),
                "openai": None,
            }
        return {
            "mode": "auto→openai",
            "gemini": None,
            "openai": await self.openai.chat(message, history),
        }


# 애플리케이션 전역 코디네이터 인스턴스
coordinator = AgentTeamCoordinator()
