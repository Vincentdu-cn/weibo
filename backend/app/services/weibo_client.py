"""Async HTTP client for Weibo with cookie-based auth, XSRF handling, and retry."""

import re
from typing import Any

import httpx

# Maximum retry attempts on transient errors
_MAX_RETRIES = 3

# Regex to extract XSRF-TOKEN value from a cookie header string
_XSRF_RE = re.compile(r"XSRF-TOKEN=([^;]+)")


class WeiboHttpClient:
    """Async HTTP client wrapping httpx.AsyncClient for Weibo AJAX endpoints."""

    def __init__(self, base_url: str = "https://weibo.com") -> None:
        self.base_url = base_url
        self._client = httpx.AsyncClient()

    # ------------------------------------------------------------------
    # Header construction
    # ------------------------------------------------------------------

    def _build_headers(self, cookie: str) -> dict[str, str]:
        """Build request headers including XSRF-TOKEN extracted from *cookie*.

        Parameters
        ----------
        cookie
            Raw cookie header string, e.g. ``"SUB=abc; XSRF-TOKEN=xyz; SUBP=def"``.

        Returns
        -------
        dict
            Headers dict ready for httpx requests.
        """
        match = _XSRF_RE.search(cookie)
        xsrf_token = match.group(1) if match else ""

        return {
            "x-xsrf-token": xsrf_token,
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "referer": "https://weibo.com",
            "x-requested-with": "XMLHttpRequest",
            "cookie": cookie,
            "sec-ch-ua": (
                '"Not_A Brand";v="8", "Chromium";v="120", '
                '"Google Chrome";v="120"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    async def _get(
        self, path: str, params: dict[str, Any], cookie: str
    ) -> dict[str, Any]:
        """Perform an async GET request with retry logic.

        Retries up to ``_MAX_RETRIES`` times on ``httpx.HTTPError``
        (which includes timeouts and connection errors).
        """
        headers = self._build_headers(cookie)
        url = self.base_url + path
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.get(
                    url, params=params, headers=headers
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                # Retry on next iteration
                continue

        # Exhausted retries
        assert last_exc is not None  # for type checker
        raise last_exc

    async def _post(
        self, path: str, data: dict[str, Any], cookie: str
    ) -> dict[str, Any]:
        """Perform an async POST request with retry logic.

        Retries up to ``_MAX_RETRIES`` times on ``httpx.HTTPError``.
        """
        headers = self._build_headers(cookie)
        url = self.base_url + path
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.post(
                    url, data=data, headers=headers
                )
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                continue

        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
