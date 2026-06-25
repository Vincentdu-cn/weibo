"""Tests for WeiboHttpClient — header construction, error handling, retry logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.weibo_client import WeiboHttpClient


# ---------------------------------------------------------------------------
# _build_headers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_build_headers_extracts_xsrf_token():
    """_build_headers must extract XSRF-TOKEN from cookie string."""
    client = WeiboHttpClient()
    cookie = "SUB=abc; XSRF-TOKEN=xyz123; SUBP=def"
    headers = client._build_headers(cookie)

    assert headers["x-xsrf-token"] == "xyz123"
    assert "user-agent" in headers
    assert headers["user-agent"]  # non-empty
    assert "x-requested-with" in headers
    assert headers["x-requested-with"] == "XMLHttpRequest"
    assert headers["cookie"] == cookie
    assert headers["referer"] == "https://weibo.com"
    assert "sec-ch-ua" in headers
    assert "sec-ch-ua-mobile" in headers
    assert "sec-ch-ua-platform" in headers
    await client.close()


@pytest.mark.asyncio
async def test_build_headers_no_xsrf_token():
    """_build_headers must not crash when XSRF-TOKEN is absent."""
    client = WeiboHttpClient()
    cookie = "SUB=abc; SUBP=def"
    headers = client._build_headers(cookie)

    # x-xsrf-token should be empty string or absent — either is acceptable
    xsrf = headers.get("x-xsrf-token", "")
    assert xsrf == ""
    await client.close()


@pytest.mark.asyncio
async def test_build_headers_xsrf_token_with_trailing_semicolon():
    """XSRF-TOKEN at end of cookie string (no trailing semicolon) must parse."""
    client = WeiboHttpClient()
    cookie = "SUB=abc; XSRF-TOKEN=token_at_end"
    headers = client._build_headers(cookie)
    assert headers["x-xsrf-token"] == "token_at_end"
    await client.close()


# ---------------------------------------------------------------------------
# _get — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_success_parses_json():
    """_get must return parsed JSON from a successful response."""
    client = WeiboHttpClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": 1, "data": {"msg": "hi"}}
    mock_response.raise_for_status = MagicMock()

    with patch.object(
        client._client, "get", new=AsyncMock(return_value=mock_response)
    ):
        result = await client._get("/ajax/test", {"id": "1"}, "XSRF-TOKEN=tok")

    assert result == {"ok": 1, "data": {"msg": "hi"}}
    await client.close()


@pytest.mark.asyncio
async def test_get_retries_on_http_error():
    """_get must retry up to 3 times on httpx.HTTPError."""
    client = WeiboHttpClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": 1}
    mock_response.raise_for_status = MagicMock()

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.HTTPError("transient")
        return mock_response

    with patch.object(
        client._client, "get", new=AsyncMock(side_effect=side_effect)
    ):
        result = await client._get("/ajax/test", {}, "XSRF-TOKEN=tok")

    assert call_count == 3
    assert result == {"ok": 1}
    await client.close()


@pytest.mark.asyncio
async def test_get_raises_after_max_retries():
    """_get must raise after 3 failed attempts."""
    client = WeiboHttpClient()

    with patch.object(
        client._client, "get",
        new=AsyncMock(side_effect=httpx.HTTPError("permanent")),
    ):
        with pytest.raises(httpx.HTTPError):
            await client._get("/ajax/test", {}, "XSRF-TOKEN=tok")

    await client.close()


# ---------------------------------------------------------------------------
# _post — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_success_parses_json():
    """_post must return parsed JSON from a successful response."""
    client = WeiboHttpClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": 1, "msg": "created"}
    mock_response.raise_for_status = MagicMock()

    with patch.object(
        client._client, "post", new=AsyncMock(return_value=mock_response)
    ):
        result = await client._post(
            "/ajax/comments/create", {"content": "hi"}, "XSRF-TOKEN=tok"
        )

    assert result == {"ok": 1, "msg": "created"}
    await client.close()


@pytest.mark.asyncio
async def test_post_retries_on_timeout():
    """_post must retry on httpx.TimeoutException."""
    client = WeiboHttpClient()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": 1}
    mock_response.raise_for_status = MagicMock()

    call_count = 0

    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.TimeoutException("timeout")
        return mock_response

    with patch.object(
        client._client, "post", new=AsyncMock(side_effect=side_effect)
    ):
        result = await client._post("/ajax/test", {"x": "1"}, "XSRF-TOKEN=tok")

    assert call_count == 2
    assert result == {"ok": 1}
    await client.close()
