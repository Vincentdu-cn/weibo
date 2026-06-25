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
    # Discovered from the official JS source at
    # https://i.sso.sina.com.cn/js/qrcode_login_v2.js
    QR_IMAGE_URL = "https://login.sina.com.cn/sso/qrcode/image"
    QR_CHECK_URL = "https://login.sina.com.cn/sso/qrcode/check"
    LOGIN_URL = "https://login.sina.com.cn/sso/login.php"
    PROFILE_INFO_URL = "https://weibo.com/ajax/profile/info"

    # Cookies we care about after a successful login
    _TARGET_COOKIES = frozenset({"SUB", "SUBP", "XSRF-TOKEN", "SSOLoginState"})

    # Class-level session storage: qrid -> {qrid, status, cookie}
    _sessions: dict[str, dict[str, Any]] = {}

    # ── Lifecycle ────────────────────────────────────────────────────────
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://weibo.com/",
            },
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ── Public API ───────────────────────────────────────────────────────
    async def get_qr_image(self) -> dict[str, str]:
        """Request a fresh QR code image and session ID.

        Returns:
            ``{"qr_url": str, "session_id": str}``
        """
        params = {
            "entry": "sso",
            "size": "180",
            "callback": "st02_1",
        }
        resp = await self._client.get(self.QR_IMAGE_URL, params=params)
        data = self._parse_jsonp(resp.text)
        image_url = data["data"]["image"]
        qrid = data["data"]["qrid"]

        self._sessions[qrid] = {
            "qrid": qrid,
            "status": "waiting",
            "cookie": None,
        }
        return {"qr_url": image_url, "session_id": qrid}

    async def check_login_status(self, qrid: str) -> dict[str, Any]:
        """Poll the login status for *qrid*.

        Returns:
            ``{"status": "waiting" | "scanned" | "expired"}``
            On success also includes ``cookie``, ``weibo_uid`` and ``nickname``.
        """
        params = {
            "entry": "sso",
            "qrid": qrid,
            "callback": "st02_2",
        }
        resp = await self._client.get(self.QR_CHECK_URL, params=params)
        data = self._parse_jsonp(resp.text)
        retcode = str(data.get("retcode", ""))

        # 50114001 — QR not yet scanned (未使用)
        if retcode == "50114001":
            self._update_session(qrid, "waiting")
            return {"status": "waiting"}

        # 50114002 — QR scanned but not yet confirmed (已扫码)
        if retcode == "50114002":
            self._update_session(qrid, "scanned")
            return {"status": "scanned"}

        # 20000000 — login confirmed (已确认)
        if retcode == "20000000":
            alt = data.get("data", {}).get("alt", "")
            cookies = await self.extract_cookies(alt)
            cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
            user_info = await self._get_user_info(cookie_str)
            self._update_session(qrid, "success", cookie_str)
            return {
                "status": "success",
                "cookie": cookie_str,
                "weibo_uid": user_info.get("weibo_uid"),
                "nickname": user_info.get("nickname"),
            }

        # 50114003 — QR timed out
        if retcode == "50114003":
            self._update_session(qrid, "expired")
            return {"status": "expired"}

        # 50114004 — QR already used
        if retcode == "50114004":
            self._update_session(qrid, "expired")
            return {"status": "expired"}

        # Unknown retcode — default to waiting so the frontend keeps polling
        self._update_session(qrid, "waiting")
        return {"status": "waiting"}

    async def extract_cookies(self, alt: str) -> dict[str, str]:
        """Follow the login URL built from *alt* and harvest cookies.

        The login URL triggers a cross-domain redirect chain that sets
        SUB, SUBP, XSRF-TOKEN and SSOLoginState cookies on weibo.com.

        Returns:
            Dict mapping cookie name to value for the target cookies.
        """
        login_url = (
            f"{self.LOGIN_URL}"
            f"?entry=sso&returntype=CROSSDOMAIN_BY_LOCATION"
            f"&alt={alt}&url=https://weibo.com"
        )
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://weibo.com/",
            },
        ) as redirect_client:
            resp = await redirect_client.get(login_url)
            cookies: dict[str, str] = {}
            for name in self._TARGET_COOKIES:
                value = redirect_client.cookies.get(name)
                if value:
                    cookies[name] = value
            if not cookies:
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
        if not cookie:
            return {"weibo_uid": "", "nickname": ""}
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://weibo.com/",
                "Cookie": cookie,
            },
        ) as info_client:
            resp = await info_client.get(self.PROFILE_INFO_URL)
            if resp.status_code != 200:
                return {"weibo_uid": "", "nickname": ""}
            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                return {"weibo_uid": "", "nickname": ""}
            user = data.get("data", {}).get("user", {})
            return {
                "weibo_uid": str(user.get("id", "")),
                "nickname": user.get("screen_name", ""),
            }

    @staticmethod
    def _parse_jsonp(text: str) -> dict[str, Any]:
        """Strip the JSONP callback wrapper and parse the JSON payload.

        If the response is not JSONP (no parentheses), try parsing as plain JSON.
        """
        start_idx = text.find("(")
        if start_idx == -1:
            # Not JSONP — parse as plain JSON
            return json.loads(text)
        end_idx = text.rfind(")")
        if end_idx == -1 or end_idx <= start_idx:
            # Malformed — try plain JSON as a fallback
            return json.loads(text)
        return json.loads(text[start_idx + 1 : end_idx])

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
