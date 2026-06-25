"""Tests for WeiboQrLogin service and QR login API routes.

All HTTP calls are mocked by patching ``httpx.AsyncClient.get`` at the class
level, so every instance of AsyncClient (including the one inside
``WeiboQrLogin``) has its ``get`` method intercepted.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services.qr_login import WeiboQrLogin


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_sessions():
    """Clear the class-level _sessions dict before and after each test."""
    WeiboQrLogin._sessions.clear()
    yield
    WeiboQrLogin._sessions.clear()


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client (imports app lazily so patches can apply)."""
    from app.main import app

    return TestClient(app)


# ─── Mock-response helpers ────────────────────────────────────────────────────


def _jsonp(payload: dict, callback: str = "st02_1") -> MagicMock:
    """Mock HTTP response whose ``.text`` is JSONP-wrapped *payload*."""
    resp = MagicMock()
    resp.text = f"{callback}({json.dumps(payload)})"
    resp.status_code = 200
    return resp


def _cookie_response(cookies: dict[str, str]) -> MagicMock:
    """Mock HTTP response with Set-Cookie headers for *cookies*."""
    resp = MagicMock()
    resp.headers = httpx.Headers(
        [
            ("set-cookie", f"{name}={value}; Path=/; Domain=.sina.com.cn")
            for name, value in cookies.items()
        ]
    )
    resp.status_code = 302
    return resp


def _json_response(data: dict) -> MagicMock:
    """Mock HTTP response whose ``.json()`` returns *data*."""
    resp = MagicMock()
    resp.json.return_value = data
    resp.status_code = 200
    return resp


# ─── Service tests ────────────────────────────────────────────────────────────


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_get_qr_image_returns_url_and_session(mock_get: AsyncMock):
    """get_qr_image parses JSONP and returns qr_image_url + session_id."""
    mock_get.return_value = _jsonp({
        "retcode": 500110002,
        "data": {
            "image": "https://login.sina.com.cn/sso/qrcode_image?url=https%3A%2F%2Fexample.com%2Fqr.png",
            "qrid": "test-qrid-12345",
        },
    })

    qr = WeiboQrLogin()
    result = await qr.get_qr_image()

    assert result["qr_image_url"] == (
        "https://login.sina.com.cn/sso/qrcode_image?url=https%3A%2F%2Fexample.com%2Fqr.png"
    )
    assert result["session_id"] == "test-qrid-12345"
    # Session should be stored internally
    assert "test-qrid-12345" in WeiboQrLogin._sessions
    assert WeiboQrLogin._sessions["test-qrid-12345"]["status"] == "qr_awaiting"


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_get_qr_image_stores_session_state(mock_get: AsyncMock):
    """get_qr_image stores {qrid, status, cookie:None} in _sessions."""
    mock_get.return_value = _jsonp({
        "retcode": 500110002,
        "data": {"image": "https://example.com/qr.png", "qrid": "abc-001"},
    })

    qr = WeiboQrLogin()
    await qr.get_qr_image()

    session = WeiboQrLogin._sessions["abc-001"]
    assert session["qrid"] == "abc-001"
    assert session["status"] == "qr_awaiting"
    assert session["cookie"] is None


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_awaiting(mock_get: AsyncMock):
    """retcode 50114014 → status qr_awaiting."""
    mock_get.return_value = _jsonp({"retcode": 50114014}, callback="st02_2")

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result == {"status": "qr_awaiting"}


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_scanned(mock_get: AsyncMock):
    """retcode 50114015 → status qr_scanned."""
    mock_get.return_value = _jsonp({"retcode": 50114015}, callback="st02_2")

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result == {"status": "qr_scanned"}


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_success(mock_get: AsyncMock):
    """retcode 0 → status qr_confirmed with cookie and weibo_uid.

    Three HTTP calls happen on the success path:
      1. qrcode_login  → JSONP with retcode 0 + redirect URL
      2. redirect URL  → Set-Cookie headers (extract_cookies)
      3. profile info  → JSON with user id + screen_name
    """
    redirect_url = "https://api.weibo.com/oauth2/redirect?code=abc123"

    # Pre-populate session so _update_session has something to update
    WeiboQrLogin._sessions["test-qrid"] = {
        "qrid": "test-qrid",
        "status": "qr_awaiting",
        "cookie": None,
    }

    mock_get.side_effect = [
        # 1. Status check response
        _jsonp({"retcode": 0, "redirect": redirect_url}, callback="st02_2"),
        # 2. Redirect response with cookies
        _cookie_response({
            "SUB": "sub_value_123",
            "SUBP": "subp_value_456",
            "XSRF-TOKEN": "xsrf_token_789",
            "SSOLoginState": "1700000000",
        }),
        # 3. Profile info response
        _json_response({
            "data": {"user": {"id": 9876543210, "screen_name": "test_user"}},
        }),
    ]

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result["status"] == "qr_confirmed"
    assert "SUB=sub_value_123" in result["cookie"]
    assert "SUBP=subp_value_456" in result["cookie"]
    assert "XSRF-TOKEN=xsrf_token_789" in result["cookie"]
    assert "SSOLoginState=1700000000" in result["cookie"]
    assert result["weibo_uid"] == "9876543210"
    assert result["nickname"] == "test_user"

    # Session should be updated
    assert WeiboQrLogin._sessions["test-qrid"]["status"] == "qr_confirmed"
    assert WeiboQrLogin._sessions["test-qrid"]["cookie"] is not None

    # Verify exactly 3 HTTP calls were made
    assert mock_get.call_count == 3


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_extract_cookies_returns_target_cookies(mock_get: AsyncMock):
    """extract_cookies parses Set-Cookie headers and returns only target cookies."""
    mock_get.return_value = _cookie_response({
        "SUB": "sub_val",
        "SUBP": "subp_val",
        "XSRF-TOKEN": "token_val",
        "SSOLoginState": "1234567890",
        # Non-target cookie that should be excluded
        "ALF": "should_be_ignored",
    })

    qr = WeiboQrLogin()
    result = await qr.extract_cookies("https://api.weibo.com/redirect")

    assert result["SUB"] == "sub_val"
    assert result["SUBP"] == "subp_val"
    assert result["XSRF-TOKEN"] == "token_val"
    assert result["SSOLoginState"] == "1234567890"
    assert "ALF" not in result


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_get_user_info_extracts_uid_and_nickname(mock_get: AsyncMock):
    """_get_user_info parses /ajax/profile/info response."""
    mock_get.return_value = _json_response({
        "data": {"user": {"id": 111222333, "screen_name": "nick_test"}},
    })

    qr = WeiboQrLogin()
    result = await qr._get_user_info("SUB=abc; SUBP=def")

    assert result["weibo_uid"] == "111222333"
    assert result["nickname"] == "nick_test"


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_updates_session_on_awaiting(mock_get: AsyncMock):
    """check_login_status updates the stored session status."""
    WeiboQrLogin._sessions["q1"] = {
        "qrid": "q1",
        "status": "qr_awaiting",
        "cookie": None,
    }
    mock_get.return_value = _jsonp({"retcode": 50114015}, callback="st02_2")

    qr = WeiboQrLogin()
    await qr.check_login_status("q1")

    assert WeiboQrLogin._sessions["q1"]["status"] == "qr_scanned"


# ─── API route tests ──────────────────────────────────────────────────────────


def test_api_generate_qr(client: TestClient):
    """GET /api/qr/generate returns qr_image_url and session_id."""
    expected = {
        "qr_image_url": "https://example.com/qr.png",
        "session_id": "api-test-qrid",
    }
    with patch.object(
        WeiboQrLogin, "get_qr_image", new_callable=AsyncMock
    ) as mock:
        mock.return_value = expected
        response = client.get("/api/qr/generate")

    assert response.status_code == 200
    data = response.json()
    assert data["qr_image_url"] == "https://example.com/qr.png"
    assert data["session_id"] == "api-test-qrid"


def test_api_check_status_awaiting(client: TestClient):
    """GET /api/qr/status/{session_id} returns status from service."""
    with patch.object(
        WeiboQrLogin, "check_login_status", new_callable=AsyncMock
    ) as mock:
        mock.return_value = {"status": "qr_awaiting"}
        response = client.get("/api/qr/status/some-session-id")

    assert response.status_code == 200
    assert response.json() == {"status": "qr_awaiting"}


def test_api_check_status_confirmed(client: TestClient):
    """GET /api/qr/status/{session_id} returns full data on success."""
    full_result = {
        "status": "qr_confirmed",
        "cookie": "SUB=abc; SUBP=def",
        "weibo_uid": "123456",
        "nickname": "testnick",
    }
    with patch.object(
        WeiboQrLogin, "check_login_status", new_callable=AsyncMock
    ) as mock:
        mock.return_value = full_result
        response = client.get("/api/qr/status/success-session")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "qr_confirmed"
    assert data["weibo_uid"] == "123456"
    assert data["nickname"] == "testnick"
