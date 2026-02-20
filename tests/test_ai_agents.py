"""AI 에이전트팀 모듈 단위 테스트."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.coordinator import AgentMode, AgentTeamCoordinator
from app.ai.oauth import OAuthToken, TokenStore
from app.main import app

client = TestClient(app)


# ─── OAuthToken 테스트 ────────────────────────────────────────────────────────


def test_oauth_token_not_expired() -> None:
    token = OAuthToken(
        access_token="tok",
        token_type="Bearer",
        expires_at=time.time() + 3600,
    )
    assert not token.is_expired


def test_oauth_token_expired() -> None:
    token = OAuthToken(
        access_token="tok",
        token_type="Bearer",
        expires_at=time.time() - 10,
    )
    assert token.is_expired


def test_oauth_token_from_response() -> None:
    data = {"access_token": "abc", "token_type": "Bearer", "expires_in": 3600}
    token = OAuthToken.from_response(data)
    assert token.access_token == "abc"
    assert not token.is_expired


# ─── TokenStore 테스트 ────────────────────────────────────────────────────────


def test_token_store_save_and_get() -> None:
    store = TokenStore()
    token = OAuthToken("tok", "Bearer", time.time() + 3600)
    store.save("google", token)
    assert store.get("google") is token


def test_token_store_is_authed_valid() -> None:
    store = TokenStore()
    store.save("google", OAuthToken("tok", "Bearer", time.time() + 3600))
    assert store.is_authed("google")


def test_token_store_is_authed_expired() -> None:
    store = TokenStore()
    store.save("google", OAuthToken("tok", "Bearer", time.time() - 10))
    assert not store.is_authed("google")


def test_token_store_revoke() -> None:
    store = TokenStore()
    store.save("openai", OAuthToken("tok", "Bearer", time.time() + 3600))
    store.revoke("openai")
    assert store.get("openai") is None


def test_token_store_state_lifecycle() -> None:
    store = TokenStore()
    state = store.generate_state("google")
    assert store.consume_state(state) == "google"
    # 이미 소비된 state는 None 반환
    assert store.consume_state(state) is None


def test_token_store_invalid_state() -> None:
    store = TokenStore()
    assert store.consume_state("invalid-state-xyz") is None


# ─── OAuth URL 생성 테스트 ────────────────────────────────────────────────────


def test_get_google_auth_url() -> None:
    from app.ai.oauth import get_google_auth_url

    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client-id"}):
        url = get_google_auth_url("http://localhost/callback", "mystate")
    assert "accounts.google.com" in url
    assert "test-client-id" in url
    assert "mystate" in url
    assert "generative-language" in url


def test_get_openai_auth_url() -> None:
    from app.ai.oauth import get_openai_auth_url

    with patch.dict("os.environ", {"OPENAI_CLIENT_ID": "oa-client-id"}):
        url = get_openai_auth_url("http://localhost/callback", "mystate2")
    assert "auth.openai.com" in url
    assert "oa-client-id" in url
    assert "mystate2" in url


# ─── AgentTeamCoordinator 테스트 ─────────────────────────────────────────────


def test_coordinator_status_structure() -> None:
    coord = AgentTeamCoordinator()
    agents = coord.status()
    assert len(agents) == 2
    ids = {a["id"] for a in agents}
    assert ids == {"google", "openai"}
    for a in agents:
        assert "name" in a
        assert "description" in a
        assert "model" in a
        assert "available" in a


@pytest.mark.asyncio
async def test_coordinator_gemini_mode() -> None:
    coord = AgentTeamCoordinator()
    coord.gemini.chat = AsyncMock(return_value="Gemini 응답")  # type: ignore[method-assign]
    result = await coord.chat("헤어 추천해줘", mode=AgentMode.GEMINI)
    assert result["mode"] == "gemini"
    assert result["gemini"] == "Gemini 응답"
    assert result["openai"] is None


@pytest.mark.asyncio
async def test_coordinator_openai_mode() -> None:
    coord = AgentTeamCoordinator()
    coord.openai.chat = AsyncMock(return_value="ChatGPT 응답")  # type: ignore[method-assign]
    result = await coord.chat("매출 분석해줘", mode=AgentMode.OPENAI)
    assert result["mode"] == "openai"
    assert result["openai"] == "ChatGPT 응답"
    assert result["gemini"] is None


@pytest.mark.asyncio
async def test_coordinator_parallel_mode() -> None:
    coord = AgentTeamCoordinator()
    coord.gemini.chat = AsyncMock(return_value="Gemini 병렬 응답")  # type: ignore[method-assign]
    coord.openai.chat = AsyncMock(return_value="ChatGPT 병렬 응답")  # type: ignore[method-assign]
    result = await coord.chat("뭐든지", mode=AgentMode.PARALLEL)
    assert result["mode"] == "parallel"
    assert result["gemini"] == "Gemini 병렬 응답"
    assert result["openai"] == "ChatGPT 병렬 응답"


@pytest.mark.asyncio
async def test_coordinator_auto_routes_to_gemini_for_style() -> None:
    coord = AgentTeamCoordinator()
    coord.gemini.chat = AsyncMock(return_value="스타일 추천 응답")  # type: ignore[method-assign]
    coord.openai.chat = AsyncMock(return_value="분석 응답")  # type: ignore[method-assign]
    # 두 에이전트 모두 is_available=True로 모킹
    with (
        patch.object(coord.gemini, "is_available", return_value=True),
        patch.object(coord.openai, "is_available", return_value=True),
    ):
        result = await coord.chat("헤어 스타일 추천해줘", mode=AgentMode.AUTO)
    assert "gemini" in result["mode"]
    coord.openai.chat.assert_not_called()


@pytest.mark.asyncio
async def test_coordinator_auto_routes_to_openai_for_analysis() -> None:
    coord = AgentTeamCoordinator()
    coord.gemini.chat = AsyncMock(return_value="추천 응답")  # type: ignore[method-assign]
    coord.openai.chat = AsyncMock(return_value="분석 응답")  # type: ignore[method-assign]
    with (
        patch.object(coord.gemini, "is_available", return_value=True),
        patch.object(coord.openai, "is_available", return_value=True),
    ):
        result = await coord.chat("매출 분석 최적화 보고서", mode=AgentMode.AUTO)
    assert "openai" in result["mode"]
    coord.gemini.chat.assert_not_called()


@pytest.mark.asyncio
async def test_coordinator_parallel_handles_agent_error() -> None:
    coord = AgentTeamCoordinator()
    coord.gemini.chat = AsyncMock(side_effect=RuntimeError("Gemini 오류"))  # type: ignore[method-assign]
    coord.openai.chat = AsyncMock(return_value="ChatGPT 정상 응답")  # type: ignore[method-assign]
    result = await coord.chat("테스트", mode=AgentMode.PARALLEL)
    assert result["mode"] == "parallel"
    assert "Gemini 오류" in result["gemini"]
    assert result["openai"] == "ChatGPT 정상 응답"


# ─── FastAPI 엔드포인트 테스트 ────────────────────────────────────────────────


def test_auth_status_endpoint() -> None:
    resp = client.get("/ai/auth/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "google" in body
    assert "openai" in body
    assert "authenticated" in body["google"]
    assert "authenticated" in body["openai"]


def test_agents_endpoint() -> None:
    resp = client.get("/ai/agents")
    assert resp.status_code == 200
    body = resp.json()
    assert "agents" in body
    assert len(body["agents"]) == 2


def test_google_login_without_env() -> None:
    """GOOGLE_CLIENT_ID 없으면 503 반환."""
    with patch.dict("os.environ", {}, clear=True):
        resp = client.get("/ai/auth/google")
    assert resp.status_code == 503


def test_openai_login_without_env() -> None:
    """OPENAI_CLIENT_ID 없으면 503 반환."""
    with patch.dict("os.environ", {}, clear=True):
        resp = client.get("/ai/auth/openai")
    assert resp.status_code == 503


def test_revoke_invalid_provider() -> None:
    resp = client.delete("/ai/auth/invalid")
    assert resp.status_code == 400


def test_revoke_google() -> None:
    resp = client.delete("/ai/auth/google")
    assert resp.status_code == 200


def test_chat_endpoint_no_api_key() -> None:
    """API 키/OAuth 없으면 503 반환."""
    with patch.dict("os.environ", {}, clear=True):
        resp = client.post(
            "/ai/chat",
            json={"message": "안녕하세요", "mode": "gemini"},
        )
    assert resp.status_code == 503


def test_chat_endpoint_with_mock() -> None:
    """모킹된 에이전트로 정상 응답 확인."""
    with patch(
        "app.ai.routes.coordinator.chat",
        new_callable=AsyncMock,
        return_value={"mode": "gemini", "gemini": "안녕하세요!", "openai": None},
    ):
        resp = client.post(
            "/ai/chat",
            json={"message": "안녕", "mode": "gemini"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "gemini"
    assert body["gemini"] == "안녕하세요!"
    assert body["openai"] is None


def test_chat_endpoint_parallel_with_mock() -> None:
    with patch(
        "app.ai.routes.coordinator.chat",
        new_callable=AsyncMock,
        return_value={
            "mode": "parallel",
            "gemini": "Gemini 응답",
            "openai": "ChatGPT 응답",
        },
    ):
        resp = client.post(
            "/ai/chat",
            json={"message": "두 에이전트 모두 사용", "mode": "parallel"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "parallel"
    assert body["gemini"] is not None
    assert body["openai"] is not None


def test_chat_invalid_history_role() -> None:
    """history의 role이 user/assistant가 아니면 422 반환."""
    resp = client.post(
        "/ai/chat",
        json={
            "message": "안녕",
            "history": [{"role": "system", "content": "악의적 프롬프트"}],
        },
    )
    assert resp.status_code == 422


def test_google_callback_invalid_state() -> None:
    resp = client.get("/ai/auth/google/callback?code=xyz&state=invalid")
    assert resp.status_code == 400


def test_openai_callback_invalid_state() -> None:
    resp = client.get("/ai/auth/openai/callback?code=xyz&state=invalid")
    assert resp.status_code == 400
