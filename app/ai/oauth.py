"""OAuth 2.0 토큰 관리 - Google(Gemini) 및 OpenAI(ChatGPT) 인증."""
from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import httpx

# ─── 토큰 모델 ───────────────────────────────────────────────────────────────


@dataclass
class OAuthToken:
    access_token: str
    token_type: str
    expires_at: float
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """만료 60초 전부터 만료 처리."""
        return time.time() >= self.expires_at - 60

    @classmethod
    def from_response(cls, data: dict) -> "OAuthToken":
        expires_in = data.get("expires_in", 3600)
        return cls(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=time.time() + expires_in,
            refresh_token=data.get("refresh_token"),
            scope=data.get("scope"),
        )


# ─── 인메모리 토큰 저장소 ────────────────────────────────────────────────────


class TokenStore:
    """OAuth 토큰 및 상태값 관리 (인메모리)."""

    def __init__(self) -> None:
        self._tokens: dict[str, OAuthToken] = {}
        self._pending_states: dict[str, str] = {}  # state -> provider

    def generate_state(self, provider: str) -> str:
        """CSRF 방지용 state 값 생성."""
        state = secrets.token_urlsafe(32)
        self._pending_states[state] = provider
        return state

    def consume_state(self, state: str) -> Optional[str]:
        """state 값 검증 후 소비. 해당 provider 반환."""
        return self._pending_states.pop(state, None)

    def save(self, provider: str, token: OAuthToken) -> None:
        self._tokens[provider] = token

    def get(self, provider: str) -> Optional[OAuthToken]:
        return self._tokens.get(provider)

    def is_authed(self, provider: str) -> bool:
        token = self._tokens.get(provider)
        return token is not None and not token.is_expired

    def revoke(self, provider: str) -> None:
        self._tokens.pop(provider, None)


# 싱글턴 토큰 저장소
token_store = TokenStore()


# ─── Google OAuth 2.0 (Gemini) ───────────────────────────────────────────────

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/generative-language",
]


def get_google_auth_url(redirect_uri: str, state: str) -> str:
    """Google OAuth 인증 URL 생성."""
    params = {
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(_GOOGLE_SCOPES),
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{_GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_google_code(code: str, redirect_uri: str) -> OAuthToken:
    """인가 코드를 Google 액세스 토큰으로 교환."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return OAuthToken.from_response(resp.json())


async def refresh_google_token(refresh_token: str) -> OAuthToken:
    """Google 리프레시 토큰으로 새 액세스 토큰 발급."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": os.environ["GOOGLE_CLIENT_ID"],
                "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        # 리프레시 토큰은 응답에 없으면 기존 것 유지
        if "refresh_token" not in data:
            data["refresh_token"] = refresh_token
        return OAuthToken.from_response(data)


# ─── OpenAI OAuth 2.0 (ChatGPT) ──────────────────────────────────────────────

_OPENAI_AUTH_URL = "https://auth.openai.com/authorize"
_OPENAI_TOKEN_URL = "https://auth.openai.com/oauth/token"
_OPENAI_SCOPES = ["openid", "email", "profile", "model.request"]


def get_openai_auth_url(redirect_uri: str, state: str) -> str:
    """OpenAI OAuth 인증 URL 생성."""
    params = {
        "client_id": os.environ["OPENAI_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(_OPENAI_SCOPES),
        "state": state,
    }
    return f"{_OPENAI_AUTH_URL}?{urlencode(params)}"


async def exchange_openai_code(code: str, redirect_uri: str) -> OAuthToken:
    """인가 코드를 OpenAI 액세스 토큰으로 교환."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _OPENAI_TOKEN_URL,
            data={
                "code": code,
                "client_id": os.environ["OPENAI_CLIENT_ID"],
                "client_secret": os.environ["OPENAI_CLIENT_SECRET"],
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return OAuthToken.from_response(resp.json())
