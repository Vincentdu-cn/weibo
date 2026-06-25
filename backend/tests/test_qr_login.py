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
    """get_qr_image parses JSONP and returns qr_url + session_id."""
    mock_get.return_value = _jsonp({
        "retcode": 20000000,
        "data": {
            "image": "https://v2.qr.weibo.cn/inf/gen?qrid=abc",
            "qrid": "test-qrid-12345",
            "interval": 3000,
        },
    })

    qr = WeiboQrLogin()
    result = await qr.get_qr_image()

    assert result["qr_url"] == "https://v2.qr.weibo.cn/inf/gen?qrid=abc"
    assert result["session_id"] == "test-qrid-12345"
    # Session should be stored internally
    assert "test-qrid-12345" in WeiboQrLogin._sessions
    assert WeiboQrLogin._sessions["test-qrid-12345"]["status"] == "waiting"


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_get_qr_image_stores_session_state(mock_get: AsyncMock):
    """get_qr_image stores {qrid, status, cookie:None} in _sessions."""
    mock_get.return_value = _jsonp({
        "retcode": 20000000,
        "data": {"image": "https://example.com/qr.png", "qrid": "abc-001"},
    })

    qr = WeiboQrLogin()
    await qr.get_qr_image()

    session = WeiboQrLogin._sessions["abc-001"]
    assert session["qrid"] == "abc-001"
    assert session["status"] == "waiting"
    assert session["cookie"] is None


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_waiting(mock_get: AsyncMock):
    """retcode 50114001 → status waiting."""
    mock_get.return_value = _jsonp({"retcode": 50114001}, callback="st02_2")

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result == {"status": "waiting"}


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_scanned(mock_get: AsyncMock):
    """retcode 50114002 → status scanned."""
    mock_get.return_value = _jsonp({"retcode": 50114002}, callback="st02_2")

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result == {"status": "scanned"}


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_expired_timeout(mock_get: AsyncMock):
    """retcode 50114003 → status expired (timeout)."""
    mock_get.return_value = _jsonp({"retcode": 50114003}, callback="st02_2")

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result == {"status": "expired"}


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_expired_used(mock_get: AsyncMock):
    """retcode 50114004 → status expired (already used)."""
    mock_get.return_value = _jsonp({"retcode": 50114004}, callback="st02_2")

    qr = WeiboQrLogin()
    result = await qr.check_login_status("test-qrid")

    assert result == {"status": "expired"}


@patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock)
async def test_check_login_status_success(mock_get: AsyncMock):
    """retcode 20000000 → status success with cookie and weibo_uid.

    Three HTTP calls happen on the success path:
      1. qrcode/check  → JSONP with retcode 20000000 + alt
      2. login.php URL  → Set-Cookie headers (extract_cookies)
      3. profile info   → JSON with user id + screen_name
    """
    alt_value = "alt_value_abc123"

    # Pre-populate session so _update_session has something to update
    WeiboQrLogin._sessions["test-qrid"] = {
        "qrid": "test-qrid",
        "status": "waiting",
        "cookie": None,
    }

    mock_get.side_effect = [
        # 1. Status check response
        _jsonp(
            {"retcode": 20000000, "data": {"alt": alt_value}},
            callback="st02_2",
        ),
        # 2. Login redirect response with cookies
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

    assert result["status"] == "success"
    assert "SUB=sub_value_123" in result["cookie"]
    assert "SUBP=subp_value_456" in result["cookie"]
    assert "XSRF-TOKEN=xsrf_token_789" in result["cookie"]
    assert "SSOLoginState=1700000000" in result["cookie"]
    assert result["weibo_uid"] == "9876543210"
    assert result["nickname"] == "test_user"

    # Session should be updated
    assert WeiboQrLogin._sessions["test-qrid"]["status"] == "success"
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
    result = await qr.extract_cookies("some-alt-value")

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
async def test_check_login_status_updates_session_on_scanned(mock_get: AsyncMock):
    """check_login_status updates the stored session status."""
    WeiboQrLogin._sessions["q1"] = {
        "qrid": "q1",
        "status": "waiting",
        "cookie": None,
    }
    mock_get.return_value = _jsonp({"retcode": 50114002}, callback="st02_2")

    qr = WeiboQrLogin()
    await qr.check_login_status("q1")

    assert WeiboQrLogin._sessions["q1"]["status"] == "scanned"


# ─── API route tests ──────────────────────────────────────────────────────────


def test_api_generate_qr(client: TestClient):
    """GET /api/qr/generate returns qr_url and session_id."""
    expected = {
        "qr_url": "https://example.com/qr.png",
        "session_id": "api-test-qrid",
    }
    with patch.object(
        WeiboQrLogin, "get_qr_image", new_callable=AsyncMock
    ) as mock:
        mock.return_value = expected
        response = client.get("/api/qr/generate")

    assert response.status_code == 200
    data = response.json()
    assert data["qr_url"] == "https://example.com/qr.png"
    assert data["session_id"] == "api-test-qrid"


def test_api_check_status_waiting(client: TestClient):
    """GET /api/qr/status/{session_id} returns status from service."""
    with patch.object(
        WeiboQrLogin, "check_login_status", new_callable=AsyncMock
    ) as mock:
        mock.return_value = {"status": "waiting"}
        response = client.get("/api/qr/status/some-session-id")

    assert response.status_code == 200
    assert response.json() == {"status": "waiting"}


def test_api_check_status_success(client: TestClient):
    """GET /api/qr/status/{session_id} returns status + account on success."""
    full_result = {
        "status": "success",
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
    assert data["status"] == "success"
    assert "account" in data
    assert data["account"]["weibo_uid"] == "123456"
    assert data["account"]["nickname"] == "testnick"
    assert data["account"]["status"] == "active"


def test_api_list_accounts(client: TestClient):
    """GET /api/accounts returns a list of account DTOs."""
    response = client.get("/api/accounts")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_delete_account_not_found(client: TestClient):
    """DELETE /api/accounts/{id} returns 404 for non-existent account."""
    response = client.delete("/api/accounts/999999")

    assert response.status_code == 404
