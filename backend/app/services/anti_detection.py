"""Anti-detection engine for Weibo monitoring.

Provides a tiered CookiePool (monitor / action), a DelayManager with randomized
async delays, and an AntiDetectionEngine that combines both plus UA rotation.

Design notes
------------
- Cookies are TIERED: ``monitor`` tier for read-only polling (auto-rotates and
  auto-resets after ``MAX_USES_PER_COOKIE`` uses), ``action`` tier for write
  operations (raises when exhausted — caller must ``reset_counts`` explicitly
  or wait for fresh cookies).
- Single IP, no proxy pool. Anti-detection relies on strict rate limiting,
  random delays with jitter, and UA rotation.
- Reference: dataabc/weiboSpider multi-layer delay system.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Optional


class CookiePool:
    """Tiered cookie pool with per-cookie rate limiting and rotation.

    Each cookie is tracked as::

        {
            "cookie_str": str,
            "use_count": int,
            "tier": "monitor" | "action",
            "last_used": float | None,
        }

    Monitor cookies rotate automatically after ``MAX_USES_PER_COOKIE`` requests
    and reset their counts once all monitor cookies are exhausted. Action
    cookies do **not** auto-reset; ``get_action_cookie`` raises when all
    eligible action cookies are exhausted.
    """

    MAX_USES_PER_COOKIE: int = 8

    def __init__(self) -> None:
        self._cookies: dict[str, dict] = {}
        # Insertion-ordered list of monitor-tier uids for round-robin rotation.
        self._monitor_order: list[str] = []
        self._monitor_index: int = 0

    # -- mutation -----------------------------------------------------------

    def add_cookie(self, uid: str, cookie_str: str, tier: str = "action") -> None:
        """Add (or update) a cookie in the pool.

        Parameters
        ----------
        uid:
            Stable identifier for the cookie (e.g. weibo uid).
        cookie_str:
            The raw ``Cookie`` header value.
        tier:
            ``"monitor"`` for read-only polling cookies, ``"action"`` for
            write-operation cookies. Defaults to ``"action"``.
        """
        if uid in self._cookies:
            info = self._cookies[uid]
            old_tier = info["tier"]
            info["cookie_str"] = cookie_str
            info["tier"] = tier
            # Keep monitor ordering consistent on tier changes.
            if old_tier != "monitor" and tier == "monitor":
                self._monitor_order.append(uid)
            elif old_tier == "monitor" and tier != "monitor":
                self._drop_monitor(uid)
            return

        self._cookies[uid] = {
            "cookie_str": cookie_str,
            "use_count": 0,
            "tier": tier,
            "last_used": None,
        }
        if tier == "monitor":
            self._monitor_order.append(uid)

    def mark_used(self, uid: str) -> None:
        """Increment ``use_count`` for ``uid`` (used by action-tier callers)."""
        if uid not in self._cookies:
            raise KeyError(f"Unknown cookie uid: {uid!r}")
        self._cookies[uid]["use_count"] += 1
        self._cookies[uid]["last_used"] = time.time()

    def reset_counts(self) -> None:
        """Reset ``use_count`` to 0 for every cookie in the pool."""
        for info in self._cookies.values():
            info["use_count"] = 0
        self._monitor_index = 0

    # -- queries ------------------------------------------------------------

    def get_monitor_cookie(self) -> str:
        """Return a monitor-tier cookie string, rotating after max uses.

        Uses round-robin: the current monitor cookie is reused until its
        ``use_count`` reaches ``MAX_USES_PER_COOKIE``, then we advance to the
        next monitor cookie. When **all** monitor cookies are exhausted, every
        monitor cookie's count is reset to 0 and rotation restarts from the
        first cookie.
        """
        if not self._monitor_order:
            raise RuntimeError("No monitor-tier cookies available in the pool")

        n = len(self._monitor_order)
        attempts = 0
        while attempts < n:
            uid = self._monitor_order[self._monitor_index]
            if self._cookies[uid]["use_count"] < self.MAX_USES_PER_COOKIE:
                self._cookies[uid]["use_count"] += 1
                self._cookies[uid]["last_used"] = time.time()
                return self._cookies[uid]["cookie_str"]
            # Current cookie exhausted -> advance round-robin pointer.
            self._monitor_index = (self._monitor_index + 1) % n
            attempts += 1

        # All monitor cookies exhausted: reset and serve the first one.
        for uid in self._monitor_order:
            self._cookies[uid]["use_count"] = 0
        self._monitor_index = 0
        uid = self._monitor_order[0]
        self._cookies[uid]["use_count"] += 1
        self._cookies[uid]["last_used"] = time.time()
        return self._cookies[uid]["cookie_str"]

    def get_action_cookie(self, exclude_uids: Optional[list[str]] = None) -> str:
        """Return an action-tier cookie string not in ``exclude_uids``.

        Only cookies with ``use_count < MAX_USES_PER_COOKIE`` are eligible.
        Among eligible candidates, the least-used cookie is chosen (even load
        distribution), with insertion order as a tiebreaker.

        Raises
        ------
        RuntimeError
            If no eligible action-tier cookie is available.
        """
        exclude = set(exclude_uids or [])
        candidates = [
            uid
            for uid, info in self._cookies.items()
            if info["tier"] == "action"
            and uid not in exclude
            and info["use_count"] < self.MAX_USES_PER_COOKIE
        ]
        if not candidates:
            raise RuntimeError("No eligible action-tier cookies available")
        candidates.sort(key=lambda u: (self._cookies[u]["use_count"], u))
        return self._cookies[candidates[0]]["cookie_str"]

    def check_health(self, uid: str) -> bool:
        """Placeholder health check — always returns True.

        The real implementation (which probes whether a cookie is still logged
        in) lands in a later task.
        """
        return True

    def get_available_count(self, tier: Optional[str] = None) -> int:
        """Count cookies with remaining capacity, optionally filtered by tier."""
        count = 0
        for info in self._cookies.values():
            if info["use_count"] >= self.MAX_USES_PER_COOKIE:
                continue
            if tier is not None and info["tier"] != tier:
                continue
            count += 1
        return count

    # -- internals ----------------------------------------------------------

    def _drop_monitor(self, uid: str) -> None:
        """Remove ``uid`` from the monitor round-robin, fixing the index."""
        if uid not in self._monitor_order:
            return
        idx = self._monitor_order.index(uid)
        self._monitor_order.pop(idx)
        if self._monitor_order:
            if idx < self._monitor_index:
                self._monitor_index -= 1
            self._monitor_index %= len(self._monitor_order)
        else:
            self._monitor_index = 0


class DelayManager:
    """Randomized async delay manager.

    All methods are coroutines that actually ``await asyncio.sleep``; the
    returned float is the duration that was slept (useful for logging and
    assertions). Tests mock ``asyncio.sleep`` to avoid real waiting.
    """

    async def random_delay(self, min_s: float = 2, max_s: float = 8) -> float:
        """Sleep for ``random.uniform(min_s, max_s)`` seconds and return it."""
        delay = random.uniform(min_s, max_s)
        await asyncio.sleep(delay)
        return delay

    async def action_delay(self) -> float:
        """Delay after a write action (like/comment): 8-20 seconds."""
        return await self.random_delay(8, 20)

    async def monitor_delay(self) -> float:
        """Delay between monitoring polls: 12-35 seconds."""
        return await self.random_delay(12, 35)

    async def comment_delay(self) -> float:
        """Delay between comment posts: 15-30 seconds."""
        return await self.random_delay(15, 30)

    async def cookie_switch_delay(self) -> float:
        """Delay when switching cookies: 3-8 seconds."""
        return await self.random_delay(3, 8)


class AntiDetectionEngine:
    """Combines :class:`CookiePool` and :class:`DelayManager` with UA rotation.

    Holds 5 realistic Chrome (120-122) user-agent strings spanning Windows,
    macOS and Linux, and exposes convenience ``wait_*`` coroutines.
    """

    USER_AGENTS: list[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

    def __init__(self) -> None:
        self.cookie_pool: CookiePool = CookiePool()
        self.delay_manager: DelayManager = DelayManager()

    def get_user_agent(self) -> str:
        """Return a random Chrome user-agent string."""
        return random.choice(self.USER_AGENTS)

    async def wait_monitor(self) -> float:
        """Wait a monitor-poll delay (12-35s) and return the duration."""
        return await self.delay_manager.monitor_delay()

    async def wait_action(self) -> float:
        """Wait an action delay (8-20s) and return the duration."""
        return await self.delay_manager.action_delay()

    async def wait_comment(self) -> float:
        """Wait a comment delay (15-30s) and return the duration."""
        return await self.delay_manager.comment_delay()

    async def wait_cookie_switch(self) -> float:
        """Wait a cookie-switch delay (3-8s) and return the duration."""
        return await self.delay_manager.cookie_switch_delay()
