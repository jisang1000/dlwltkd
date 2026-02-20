"""FastAPI 라우터 - AI 에이전트팀 OAuth 인증 및 채팅 엔드포인트."""
from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from .coordinator import AgentMode, coordinator
from .oauth import (
    exchange_google_code,
    exchange_openai_code,
    get_google_auth_url,
    get_openai_auth_url,
    token_store,
)

router = APIRouter(prefix="/ai", tags=["AI 에이전트팀"])


# ─── 내부 헬퍼 ────────────────────────────────────────────────────────────────


def _base_url(request: Request) -> str:
    """요청에서 스키마+호스트만 추출 (trailing slash 제거)."""
    return str(request.base_url).rstrip("/")


# ─── OAuth 인증 라우트 ────────────────────────────────────────────────────────


@router.get(
    "/auth/google",
    summary="Google(Gemini) OAuth 로그인 시작",
    description=(
        "Google OAuth 2.0 인증 페이지로 리다이렉트합니다. "
        "환경변수 `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`이 필요합니다."
    ),
)
async def google_login(request: Request) -> RedirectResponse:
    if not os.environ.get("GOOGLE_CLIENT_ID"):
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_CLIENT_ID 환경변수가 설정되지 않았습니다.",
        )
    state = token_store.generate_state("google")
    redirect_uri = f"{_base_url(request)}/ai/auth/google/callback"
    return RedirectResponse(get_google_auth_url(redirect_uri, state))


@router.get(
    "/auth/google/callback",
    summary="Google OAuth 콜백 처리",
)
async def google_callback(
    request: Request,
    code: str = Query(..., description="Google 인가 코드"),
    state: str = Query(..., description="CSRF 방지 state 값"),
) -> dict:
    provider = token_store.consume_state(state)
    if provider != "google":
        raise HTTPException(status_code=400, detail="유효하지 않은 state 값입니다.")
    redirect_uri = f"{_base_url(request)}/ai/auth/google/callback"
    try:
        token = await exchange_google_code(code, redirect_uri)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google 토큰 교환 실패: {exc}") from exc
    token_store.save("google", token)
    return {
        "status": "ok",
        "provider": "google",
        "message": "Google(Gemini) OAuth 인증 완료",
        "expires_in_sec": max(0, int(token.expires_at - __import__("time").time())),
    }


@router.get(
    "/auth/openai",
    summary="OpenAI(ChatGPT) OAuth 로그인 시작",
    description=(
        "OpenAI OAuth 2.0 인증 페이지로 리다이렉트합니다. "
        "환경변수 `OPENAI_CLIENT_ID` / `OPENAI_CLIENT_SECRET`이 필요합니다."
    ),
)
async def openai_login(request: Request) -> RedirectResponse:
    if not os.environ.get("OPENAI_CLIENT_ID"):
        raise HTTPException(
            status_code=503,
            detail="OPENAI_CLIENT_ID 환경변수가 설정되지 않았습니다.",
        )
    state = token_store.generate_state("openai")
    redirect_uri = f"{_base_url(request)}/ai/auth/openai/callback"
    return RedirectResponse(get_openai_auth_url(redirect_uri, state))


@router.get(
    "/auth/openai/callback",
    summary="OpenAI OAuth 콜백 처리",
)
async def openai_callback(
    request: Request,
    code: str = Query(..., description="OpenAI 인가 코드"),
    state: str = Query(..., description="CSRF 방지 state 값"),
) -> dict:
    provider = token_store.consume_state(state)
    if provider != "openai":
        raise HTTPException(status_code=400, detail="유효하지 않은 state 값입니다.")
    redirect_uri = f"{_base_url(request)}/ai/auth/openai/callback"
    try:
        token = await exchange_openai_code(code, redirect_uri)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OpenAI 토큰 교환 실패: {exc}") from exc
    token_store.save("openai", token)
    return {
        "status": "ok",
        "provider": "openai",
        "message": "OpenAI(ChatGPT) OAuth 인증 완료",
        "expires_in_sec": max(0, int(token.expires_at - __import__("time").time())),
    }


@router.get(
    "/auth/status",
    summary="인증 상태 확인",
    description="Google과 OpenAI OAuth 토큰의 유효 여부를 반환합니다.",
)
async def auth_status() -> dict:
    return {
        "google": {
            "authenticated": token_store.is_authed("google"),
            "fallback_api_key": bool(os.environ.get("GOOGLE_API_KEY")),
        },
        "openai": {
            "authenticated": token_store.is_authed("openai"),
            "fallback_api_key": bool(os.environ.get("OPENAI_API_KEY")),
        },
    }


@router.delete(
    "/auth/{provider}",
    summary="특정 프로바이더 인증 취소",
)
async def revoke_auth(provider: str) -> dict:
    if provider not in ("google", "openai"):
        raise HTTPException(
            status_code=400,
            detail="provider는 'google' 또는 'openai'여야 합니다.",
        )
    token_store.revoke(provider)
    return {"status": "ok", "message": f"{provider} 인증이 취소되었습니다."}


# ─── 에이전트 라우트 ──────────────────────────────────────────────────────────


@router.get(
    "/agents",
    summary="에이전트 목록 및 상태 조회",
)
async def list_agents() -> dict:
    return {"agents": coordinator.status()}


# ── 요청/응답 스키마 ──────────────────────────────────────────────────────────


class HistoryMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$", description="'user' 또는 'assistant'")
    content: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="사용자 메시지")
    mode: AgentMode = Field(
        default=AgentMode.AUTO,
        description=(
            "에이전트 선택 모드: "
            "auto(자동), gemini(Gemini 단독), openai(ChatGPT 단독), parallel(동시 실행)"
        ),
    )
    history: Optional[list[HistoryMessage]] = Field(
        default=None,
        description="이전 대화 히스토리 (최대 20개 권장)",
    )


class ChatResponse(BaseModel):
    mode: str = Field(..., description="실제 사용된 에이전트 모드")
    gemini: Optional[str] = Field(None, description="Gemini 응답 (사용된 경우)")
    openai: Optional[str] = Field(None, description="ChatGPT 응답 (사용된 경우)")


# ── 채팅 엔드포인트 ────────────────────────────────────────────────────────────


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="AI 에이전트팀에 메시지 전송",
    description=(
        "선택한 모드에 따라 Gemini, ChatGPT, 또는 두 에이전트 모두에게 메시지를 전송합니다.\n\n"
        "- **auto**: 키워드 분석으로 최적 에이전트 자동 선택\n"
        "- **gemini**: Google Gemini 단독 (한국어·스타일 추천 특화)\n"
        "- **openai**: ChatGPT 단독 (비즈니스 분석 특화)\n"
        "- **parallel**: 두 에이전트 동시 실행 후 결과 모두 반환"
    ),
)
async def chat(payload: ChatRequest) -> ChatResponse:
    history = (
        [{"role": m.role, "content": m.content} for m in payload.history]
        if payload.history
        else None
    )
    try:
        result = await coordinator.chat(
            message=payload.message,
            mode=payload.mode,
            history=history,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"에이전트 오류: {exc}") from exc
    return ChatResponse(**result)
