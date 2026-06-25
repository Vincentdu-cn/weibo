"""Weibo SSO QR-code login service.

Implements the three-step QR login flow:
  1. get_qr_image()        — request a QR code image + session ID (qrid)
  2. check_login_status()  — poll qrid for scan / confirm status
  3. extract_cookies()     — on success, follow redirect URL to harvest cookies

All HTTP calls go through a single ``httpx.AsyncClient`` stored on ``self._client``
so that tests can patch ``httpx.AsyncClient.get`` once and intercept every call.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class WeiboQrLogin:
    """Handle the Weibo SSO QR-code login flow."""

    # ── Endpoint constants ───────────────────────────────────────────────
    QR_IMAGE_URL = "https://login.sina.com.cn/sso/qrcode_image"
    QR_LOGIN_URL = "https://login.sina.com.cn/sso/qrcode_login"
    PROFILE_INFO_URL = "https://weibo.com/ajax/profile/info"

    # Cookies we care about after a successful login
    _TARGET_COOKIES = frozenset({"SUB", "SUBP", "XSRF-TOKEN", "SSOLoginState"})

    # Class-level session storage: qrid -> {qrid, status, cookie}
    _sessions: dict[str, dict[str, Any]] = {}

    # ── Lifecycle ────────────────────────────────────────────────────────
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(follow_redirects=False, timeout=30.0)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ── Public API ───────────────────────────────────────────────────────
    async def get_qr_image(self) -> dict[str, str]:
        """Request a fresh QR code image and session ID.

        Returns:
            ``{"qr_image_url": str, "session_id": str}``
        """
        params = {
            "entry": "weibo",
            "size": "180",
            "use_callback": "1",
            "callback": "st02_1",
        }
        resp = await self._client.get(self.QR_IMAGE_URL, params=params)
        data = self._parse_jsonp(resp.text)
        image_url = data["data"]["image"]
        qrid = data["data"]["qrid"]

        self._sessions[qrid] = {
            "qrid": qrid,
            "status": "qr_awaiting",
            "cookie": None,
        }
        return {"qr_image_url": image_url, "session_id": qrid}

    async def check_login_status(self, qrid: str) -> dict[str, Any]:
        """Poll the login status for *qrid*.

        Returns:
            ``{"status": "qr_awaiting" | "qr_scanned" | "qr_confirmed"}``
            On success also includes ``cookie``, ``weibo_uid`` and ``nickname``.
        """
        params = {
            "entry": "weibo",
            "qrid": qrid,
            "callback": "st02_2",
        }
        resp = await self._client.get(self.QR_LOGIN_URL, params=params)
        data = self._parse_jsonp(resp.text)
        retcode = str(data.get("retcode", ""))

        if retcode == "50114014":
            self._update_session(qrid, "qr_awaiting")
            return {"status": "qr_awaiting"}

        if retcode == "50114015":
            self._update_session(qrid, "qr_scanned")
            return {"status": "qr_scanned"}

        if retcode == "0":
            redirect_url = (
                data.get("redirect")
                or data.get("data", {}).get("alt", "")
            )
            cookies = await self.extract_cookies(redirect_url)
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            user_info = await self._get_user_info(cookie_str)
            self._update_session(qrid, "qr_confirmed", cookie_str)
            return {
                "status": "qr_confirmed",
                "cookie": cookie_str,
                "weibo_uid": user_info.get("weibo_uid"),
                "nickname": user_info.get("nickname"),
            }

        return {"status": "qr_unknown", "retcode": retcode}

    async def extract_cookies(self, redirect_url: str) -> dict[str, str]:
        """Follow *redirect_url* and extract login cookies from Set-Cookie headers.

        Returns:
            Dict mapping cookie name to value for the target cookies
            (SUB, SUBP, XSRF-TOKEN, SSOLoginState).
        """
        resp = await self._client.get(redirect_url)
        cookies: dict[str, str] = {}
        for raw in resp.headers.get_list("set-cookie"):
            pair = raw.split(";")[0].strip()
            if "=" not in pair:
                continue
            name, value = pair.split("=", 1)
            name = name.strip()
            if name in self._TARGET_COOKIES:
                cookies[name] = value.strip()
        return cookies

    # ── Internal helpers ────────────────────────────────────────────────
    async def _get_user_info(self, cookie: str) -> dict[str, str]:
        """Fetch the logged-in user's UID and nickname.

        Returns:
            ``{"weibo_uid": str, "nickname": str}``
        """
        headers = {"Cookie": cookie}
        resp = await self._client.get(self.PROFILE_INFO_URL, headers=headers)
        data = resp.json()
        user = data.get("data", {}).get("user", {})
        return {
            "weibo_uid": str(user.get("id", "")),
            "nickname": user.get("screen_name", ""),
        }

    @staticmethod
    def _parse_jsonp(text: str) -> dict[str, Any]:
        """Strip the JSONP callback wrapper and parse the JSON payload."""
        start = text.index("(")
        end = text.rindex(")")
        return json.loads(text[start + 1 : end])

    @classmethod
    def _update_session(
        cls, qrid: str, status: str, cookie: str | None = None
    ) -> None:
        """Update the stored session for *qrid* if it exists."""
        session = cls._sessions.get(qrid)
        if session is not None:
            session["status"] = status
            if cookie is not None:
                session["cookie"] = cookie
