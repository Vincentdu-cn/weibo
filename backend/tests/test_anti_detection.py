"""Tests for AntiDetectionEngine, CookiePool, and DelayManager.

TDD: written before implementation. Covers cookie rotation, exclude_uids,
use_count limits, delay ranges, UA rotation, and reset_counts.
"""

import asyncio
import random
from unittest.mock import AsyncMock, patch

import pytest

from app.services.anti_detection import (
    AntiDetectionEngine,
    CookiePool,
    DelayManager,
)


# ---------------------------------------------------------------------------
# CookiePool
# ---------------------------------------------------------------------------


class TestCookiePool:
    def test_monitor_cookie_rotation_after_max_uses(self):
        """First 10 calls return uid1; 11th rotates to uid2."""
        pool = CookiePool()
        pool.add_cookie("uid1", "cookie_str_1", tier="monitor")
        pool.add_cookie("uid2", "cookie_str_2", tier="monitor")

        for i in range(CookiePool.MAX_USES_PER_COOKIE):
            c = pool.get_monitor_cookie()
            assert c == "cookie_str_1", f"call {i + 1} should return cookie_str_1"

        # uid1 now exhausted (use_count == MAX), rotate to uid2
        c = pool.get_monitor_cookie()
        assert c == "cookie_str_2"

    def test_monitor_cookie_resets_when_all_exhausted(self):
        """Single monitor cookie: after 10 uses, reset and continue."""
        pool = CookiePool()
        pool.add_cookie("uid1", "cookie_str_1", tier="monitor")

        for _ in range(CookiePool.MAX_USES_PER_COOKIE):
            assert pool.get_monitor_cookie() == "cookie_str_1"

        # 11th call: only cookie exhausted -> reset -> return same cookie
        assert pool.get_monitor_cookie() == "cookie_str_1"
        assert pool._cookies["uid1"]["use_count"] == 1

    def test_get_action_cookie_excludes_uids(self):
        """get_action_cookie must never return an excluded uid's cookie."""
        pool = CookiePool()
        pool.add_cookie("uid1", "cookie_str_1", tier="action")
        pool.add_cookie("uid2", "cookie_str_2", tier="action")
        pool.add_cookie("uid3", "cookie_str_3", tier="action")

        for _ in range(20):
            c = pool.get_action_cookie(exclude_uids=["uid1"])
            assert c != "cookie_str_1"
            assert c in {"cookie_str_2", "cookie_str_3"}

    def test_get_action_cookie_raises_when_exhausted(self):
        """After 10 mark_used calls, get_action_cookie should raise."""
        pool = CookiePool()
        pool.add_cookie("uid1", "cookie_str_1", tier="action")
        for _ in range(CookiePool.MAX_USES_PER_COOKIE):
            pool.mark_used("uid1")

        with pytest.raises(Exception):
            pool.get_action_cookie()

    def test_get_action_cookie_no_monitor_cookies_used(self):
        """Action tier request must not return monitor-tier cookies."""
        pool = CookiePool()
        pool.add_cookie("m1", "mon_cookie", tier="monitor")
        pool.add_cookie("a1", "act_cookie", tier="action")
        assert pool.get_action_cookie() == "act_cookie"

    def test_get_available_count(self):
        pool = CookiePool()
        pool.add_cookie("uid1", "c1", tier="action")
        pool.add_cookie("uid2", "c2", tier="action")
        pool.add_cookie("uid3", "c3", tier="monitor")

        assert pool.get_available_count() == 3
        assert pool.get_available_count(tier="action") == 2
        assert pool.get_available_count(tier="monitor") == 1

        for _ in range(CookiePool.MAX_USES_PER_COOKIE):
            pool.mark_used("uid1")
        assert pool.get_available_count() == 2
        assert pool.get_available_count(tier="action") == 1

    def test_reset_counts(self):
        pool = CookiePool()
        pool.add_cookie("uid1", "c1", tier="action")
        for _ in range(5):
            pool.mark_used("uid1")
        assert pool._cookies["uid1"]["use_count"] == 5

        pool.reset_counts()
        assert pool._cookies["uid1"]["use_count"] == 0

    def test_reset_counts_all_cookies(self):
        pool = CookiePool()
        pool.add_cookie("uid1", "c1", tier="action")
        pool.add_cookie("uid2", "c2", tier="monitor")
        pool.mark_used("uid1")
        pool.mark_used("uid2")
        pool.mark_used("uid2")

        pool.reset_counts()
        assert all(info["use_count"] == 0 for info in pool._cookies.values())

    def test_check_health_returns_true_placeholder(self):
        pool = CookiePool()
        pool.add_cookie("uid1", "c1")
        assert pool.check_health("uid1") is True

    def test_mark_used_increments(self):
        pool = CookiePool()
        pool.add_cookie("uid1", "c1", tier="action")
        pool.mark_used("uid1")
        pool.mark_used("uid1")
        assert pool._cookies["uid1"]["use_count"] == 2

    def test_max_uses_constant(self):
        assert CookiePool.MAX_USES_PER_COOKIE == 8


# ---------------------------------------------------------------------------
# DelayManager
# ---------------------------------------------------------------------------


class TestDelayManager:
    async def test_action_delay_range(self):
        dm = DelayManager()
        random.seed(42)
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            for _ in range(20):
                d = await dm.action_delay()
                assert 8 <= d <= 20

    async def test_monitor_delay_range(self):
        dm = DelayManager()
        random.seed(42)
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            for _ in range(20):
                d = await dm.monitor_delay()
                assert 12 <= d <= 35

    async def test_comment_delay_range(self):
        dm = DelayManager()
        random.seed(42)
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            for _ in range(20):
                d = await dm.comment_delay()
                assert 15 <= d <= 30

    async def test_random_delay_custom_range(self):
        dm = DelayManager()
        random.seed(42)
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            for _ in range(20):
                d = await dm.random_delay(1, 3)
                assert 1 <= d <= 3

    async def test_random_delay_default_range(self):
        dm = DelayManager()
        random.seed(42)
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            for _ in range(20):
                d = await dm.random_delay()
                assert 2 <= d <= 8

    async def test_delay_calls_asyncio_sleep(self):
        dm = DelayManager()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            await dm.action_delay()
            mock_sleep.assert_awaited_once()

    async def test_delay_returns_sleep_duration(self):
        """Returned value equals the duration passed to asyncio.sleep."""
        dm = DelayManager()
        captured = {}

        async def fake_sleep(d):
            captured["duration"] = d

        with patch.object(asyncio, "sleep", side_effect=fake_sleep):
            d = await dm.action_delay()
            assert d == captured["duration"]


# ---------------------------------------------------------------------------
# AntiDetectionEngine
# ---------------------------------------------------------------------------


class TestAntiDetectionEngine:
    def test_ua_rotation_returns_multiple_distinct(self):
        engine = AntiDetectionEngine()
        random.seed(42)
        uas = {engine.get_user_agent() for _ in range(10)}
        assert len(uas) >= 2

    def test_ua_list_has_5_chrome_uas(self):
        engine = AntiDetectionEngine()
        assert len(engine.USER_AGENTS) == 5
        for ua in engine.USER_AGENTS:
            assert "Chrome" in ua

    def test_ua_list_contains_chrome_120_to_122(self):
        engine = AntiDetectionEngine()
        joined = " ".join(engine.USER_AGENTS)
        assert "Chrome/120" in joined
        assert "Chrome/121" in joined
        assert "Chrome/122" in joined

    def test_engine_has_cookie_pool_and_delay_manager(self):
        engine = AntiDetectionEngine()
        assert isinstance(engine.cookie_pool, CookiePool)
        assert isinstance(engine.delay_manager, DelayManager)

    async def test_wait_monitor_delegates(self):
        engine = AntiDetectionEngine()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            d = await engine.wait_monitor()
            assert 12 <= d <= 35

    async def test_wait_action_delegates(self):
        engine = AntiDetectionEngine()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            d = await engine.wait_action()
            assert 8 <= d <= 20

    async def test_wait_comment_delegates(self):
        engine = AntiDetectionEngine()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            d = await engine.wait_comment()
            assert 15 <= d <= 30
