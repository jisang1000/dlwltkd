"""AI 에이전트 구현 - Google Gemini 및 OpenAI ChatGPT."""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from .oauth import OAuthToken, refresh_google_token, token_store

# 대화 히스토리 메시지 타입
Message = dict[str, str]  # {"role": "user"|"assistant", "content": "..."}


# ─── 에이전트 베이스 ──────────────────────────────────────────────────────────


class BaseAgent(ABC):
    """모든 AI 에이전트의 공통 인터페이스."""

    name: str
    provider: str
    description: str
    model: str

    @abstractmethod
    async def chat(self, message: str, history: Optional[list[Message]] = None) -> str:
        """메시지를 전송하고 응답을 받는다."""

    def is_available(self) -> bool:
        """OAuth 토큰 또는 API 키가 준비되어 있는지 확인."""
        return token_store.is_authed(self.provider) or bool(
            os.environ.get(self._env_api_key)
        )

    @property
    @abstractmethod
    def _env_api_key(self) -> str:
        """폴백용 환경변수 API 키 이름."""

    async def _get_bearer(self) -> str:
        """OAuth 액세스 토큰 또는 API 키로 Authorization 헤더 값 반환."""
        token = token_store.get(self.provider)
        if token is not None:
            if token.is_expired:
                token = await self._try_refresh(token)
            if token is not None and not token.is_expired:
                return f"Bearer {token.access_token}"

        api_key = os.environ.get(self._env_api_key)
        if api_key:
            return f"Bearer {api_key}"

        raise RuntimeError(
            f"{self.name}: OAuth 인증 또는 {self._env_api_key} 환경변수가 필요합니다."
        )

    async def _try_refresh(self, token: OAuthToken) -> Optional[OAuthToken]:
        if not token.refresh_token:
            return None
        try:
            if self.provider == "google":
                new_token = await refresh_google_token(token.refresh_token)
                token_store.save("google", new_token)
                return new_token
        except Exception:
            pass
        return None


# ─── Google Gemini 에이전트 ──────────────────────────────────────────────────

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_SYSTEM_PROMPT = (
    "당신은 헤어샵 전문 AI 어시스턴트 'Gemini'입니다. "
    "고객 응대, 헤어 스타일 추천, 예약 상담, 트렌드 정보를 한국어로 친절하게 안내하세요."
)


class GeminiAgent(BaseAgent):
    """Google Gemini API를 사용하는 에이전트."""

    name = "Gemini"
    provider = "google"
    description = "Google Gemini - 한국어 고객 응대·스타일 추천 특화"
    model = "gemini-1.5-pro"

    @property
    def _env_api_key(self) -> str:
        return "GOOGLE_API_KEY"

    async def chat(self, message: str, history: Optional[list[Message]] = None) -> str:
        bearer = await self._get_bearer()

        contents = []
        for h in history or []:
            role = "user" if h["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": h["content"]}]})
        contents.append({"role": "user", "parts": [{"text": message}]})

        body = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": _GEMINI_SYSTEM_PROMPT}]},
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
        }

        # API 키 방식은 쿼리 파라미터, OAuth는 Authorization 헤더
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        is_api_key = bearer == f"Bearer {google_api_key}" and not token_store.is_authed("google")

        if is_api_key:
            url = f"{_GEMINI_API_BASE}/models/{self.model}:generateContent?key={google_api_key}"
            headers: dict[str, str] = {}
        else:
            url = f"{_GEMINI_API_BASE}/models/{self.model}:generateContent"
            headers = {"Authorization": bearer}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Gemini 응답 파싱 실패: {data}") from exc


# ─── OpenAI ChatGPT 에이전트 ─────────────────────────────────────────────────

_OPENAI_API_BASE = "https://api.openai.com/v1"
_OPENAI_SYSTEM_PROMPT = (
    "당신은 헤어샵 비즈니스 분석 전문 AI 'ChatGPT'입니다. "
    "매출 분석, 예약 최적화, 고객 인사이트, 운영 효율화 방안을 제공하세요."
)


class OpenAIAgent(BaseAgent):
    """OpenAI ChatGPT API를 사용하는 에이전트."""

    name = "ChatGPT"
    provider = "openai"
    description = "OpenAI ChatGPT - 비즈니스 분석·매출 최적화 특화"
    model = "gpt-4o"

    @property
    def _env_api_key(self) -> str:
        return "OPENAI_API_KEY"

    async def chat(self, message: str, history: Optional[list[Message]] = None) -> str:
        bearer = await self._get_bearer()

        messages: list[dict] = [{"role": "system", "content": _OPENAI_SYSTEM_PROMPT}]
        for h in history or []:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_OPENAI_API_BASE}/chat/completions",
                json={"model": self.model, "messages": messages, "temperature": 0.7},
                headers={"Authorization": bearer},
            )
            resp.raise_for_status()

        return resp.json()["choices"][0]["message"]["content"]
