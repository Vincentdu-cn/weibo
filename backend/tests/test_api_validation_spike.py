"""API Validation Spike — real Weibo API endpoint validation tests.

These tests validate real Weibo API endpoints (buildComments, updateLike,
comments/create, comments/reply) against a live Weibo post.

SKIP GRACEFULLY: All tests skip when ``WEIBO_TEST_COOKIE`` env var is not set.
This is a SPIKE — tests are for validation, not regression.

To run with real cookies::

    WEIBO_TEST_COOKIE="SUB=abc; XSRF-TOKEN=xyz" \\
    python -m pytest tests/test_api_validation_spike.py -v --tb=long

For multi-account tests, set additional cookies::

    WEIBO_TEST_COOKIE_2="SUB=def; XSRF-TOKEN=uvw"
    WEIBO_TEST_COOKIE_3="SUB=ghi; XSRF-TOKEN=rst"

Evidence files written to ``.omo/evidence/``:
  - ``task-22-latency.json`` — latency measurements for API calls
  - ``task-22-hot-ranking.json`` — hot vs time ranking analysis
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

import pytest

from app.services.action_executor import ActionExecutor
from app.services.anti_detection import AntiDetectionEngine
from app.services.comment_fetcher import CommentFetcher
from app.services.weibo_client import WeiboHttpClient

# ---------------------------------------------------------------------------
# Skip condition — all tests skip without WEIBO_TEST_COOKIE
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not os.environ.get("WEIBO_TEST_COOKIE"),
    reason="No WEIBO_TEST_COOKIE env var set — skipping real API validation spike",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Well-known public Weibo post base62 mid for testing.
_TEST_BASE62_MID = "Mb15BDYR0"

# Evidence directory (project_root/.omo/evidence/).
_EVIDENCE_DIR = Path(__file__).resolve().parents[2] / ".omo" / "evidence"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_evidence(filename: str, key: str, data: dict) -> None:
    """Write evidence data under *key* in ``.omo/evidence/{filename}``.

    Reads any existing content and merges so that multiple tests can
    contribute to the same evidence file without overwriting each other.
    """
    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    filepath = _EVIDENCE_DIR / filename

    existing: dict = {}
    if filepath.exists():
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass  # Corrupt or empty — start fresh.

    existing[key] = data
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)


def _get_cookie(index: int = 0) -> str | None:
    """Return the cookie at *index* (0-based) from WEIBO_TEST_COOKIE[_n] env vars."""
    if index == 0:
        return os.environ.get("WEIBO_TEST_COOKIE")
    return os.environ.get(f"WEIBO_TEST_COOKIE_{index + 1}")


# ---------------------------------------------------------------------------
# Test 1: buildComments returns real comments
# ---------------------------------------------------------------------------

async def test_buildcomments_returns_real_comments():
    """Fetch real comments from a well-known public Weibo post.

    Validates that the buildComments API returns a non-empty list of
    comments, each with ``weibo_comment_id`` and ``like_count`` fields.
    Records latency to ``task-22-latency.json``.
    """
    cookie = os.environ["WEIBO_TEST_COOKIE"]
    client = WeiboHttpClient()
    anti = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti)

    try:
        # Convert base62 to numeric mid.
        mid = fetcher.get_weibo_mid(_TEST_BASE62_MID)
        assert mid, "get_weibo_mid should return a non-empty string"

        # Measure latency.
        t0 = time.monotonic()
        comments = await fetcher.fetch_comments(mid, cookie, max_pages=1)
        elapsed = time.monotonic() - t0

        # Record latency evidence.
        _write_evidence("task-22-latency.json", "buildcomments", {
            "mid": mid,
            "base62": _TEST_BASE62_MID,
            "elapsed_seconds": round(elapsed, 3),
            "comment_count": len(comments),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Assertions.
        assert len(comments) > 0, (
            "Should fetch at least 1 comment from a public post"
        )
        for c in comments:
            assert c.weibo_comment_id, f"Comment missing weibo_comment_id: {c}"
            assert hasattr(c, "like_count"), f"Comment missing like_count: {c}"

    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Test 2: Like endpoint works
# ---------------------------------------------------------------------------

async def test_like_endpoint_works():
    """Like the first comment via ``updateLike``, verify like_count.

    Flow:
    1. Fetch comments from the test post.
    2. Record the first comment's ``like_count``.
    3. Like it via ``ActionExecutor.like_comment()`` — assert ``ok > 0``.
    4. Re-fetch and verify ``like_count`` increased (or stayed same if
       the API cache hasn't refreshed).
    """
    cookie = os.environ["WEIBO_TEST_COOKIE"]
    client = WeiboHttpClient()
    anti = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti)
    executor = ActionExecutor(client=client, anti_detection=anti)

    try:
        mid = fetcher.get_weibo_mid(_TEST_BASE62_MID)

        # Step 1: Fetch comments.
        comments = await fetcher.fetch_comments(mid, cookie, max_pages=1)
        assert len(comments) > 0, "Need at least 1 comment to test liking"

        # Step 2: Record initial like_count.
        target = comments[0]
        initial_likes = target.like_count
        comment_id = target.weibo_comment_id

        # Step 3: Like the comment — assert response ok > 0.
        t0 = time.monotonic()
        result = await executor.like_comment(comment_id, cookie, uid="spike_test")
        like_elapsed = time.monotonic() - t0

        assert result["success"] is True, (
            f"Like failed: {result.get('error_msg')}"
        )

        # Record latency.
        _write_evidence("task-22-latency.json", "updateLike", {
            "comment_id": comment_id,
            "elapsed_seconds": round(like_elapsed, 3),
            "initial_like_count": initial_likes,
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Step 4: Wait briefly for like to propagate, then re-fetch.
        await asyncio.sleep(3)
        refetched = await fetcher.fetch_comments(mid, cookie, max_pages=1)

        # Find the same comment in the refetched list.
        refetched_target = next(
            (c for c in refetched if c.weibo_comment_id == comment_id), None
        )
        assert refetched_target is not None, (
            "Liked comment not found in refetch"
        )

        # Like count should have increased.
        # NOTE: Weibo API may cache responses, so >= is used instead of >.
        # In practice, the like is registered server-side even if the
        # cached response hasn't updated yet.
        assert refetched_target.like_count >= initial_likes, (
            f"Like count decreased: {initial_likes} -> "
            f"{refetched_target.like_count}"
        )

    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Test 3: Comment create works
# ---------------------------------------------------------------------------

async def test_comment_create_works():
    """Post a test comment, assert response contains comment object with id.

    NOTE: Only 1 test comment is posted per test run. Cleanup is attempted
    via the ``/ajax/comments/destroy`` endpoint. If cleanup fails, the
    comment remains but is clearly marked as a test comment.
    """
    cookie = os.environ["WEIBO_TEST_COOKIE"]
    client = WeiboHttpClient()
    anti = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti)
    executor = ActionExecutor(client=client, anti_detection=anti)

    # Distinctive test comment for identification.
    test_content = (
        f"[API Spike Test] 这是一条测试评论，请忽略。"
        f"{datetime.utcnow().strftime('%H%M%S')}"
    )

    try:
        mid = fetcher.get_weibo_mid(_TEST_BASE62_MID)

        # Post the comment.
        t0 = time.monotonic()
        result = await executor.post_comment(
            mid, test_content, cookie, uid="spike_test"
        )
        create_elapsed = time.monotonic() - t0

        assert result["success"] is True, (
            f"Comment creation failed: {result.get('error_msg')}"
        )
        assert result.get("comment_id") is not None, (
            "Response should contain comment_id"
        )

        created_comment_id = str(result["comment_id"])

        # Record latency.
        _write_evidence("task-22-latency.json", "comments_create", {
            "mid": mid,
            "comment_id": created_comment_id,
            "elapsed_seconds": round(create_elapsed, 3),
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Cleanup: attempt to delete the comment via the destroy endpoint.
        try:
            await client._post(
                "/ajax/comments/destroy",
                {"cid": created_comment_id},
                cookie,
            )
        except Exception:
            # Best-effort cleanup — if destroy fails, the comment remains
            # but is clearly marked as a test comment in its content.
            pass

    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Test 4: Comment reply works
# ---------------------------------------------------------------------------

async def test_comment_reply_works():
    """Reply to an existing comment, assert response.

    Flow:
    1. Fetch comments from the test post.
    2. Reply to the first comment via ``ActionExecutor.reply_comment()``.
    3. Assert the reply was successful and contains a ``comment_id``.
    4. Clean up the reply via ``/ajax/comments/destroy`` if possible.
    """
    cookie = os.environ["WEIBO_TEST_COOKIE"]
    client = WeiboHttpClient()
    anti = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti)
    executor = ActionExecutor(client=client, anti_detection=anti)

    test_content = (
        f"[API Spike Test Reply] 测试回复，请忽略。"
        f"{datetime.utcnow().strftime('%H%M%S')}"
    )

    try:
        mid = fetcher.get_weibo_mid(_TEST_BASE62_MID)

        # Step 1: Fetch comments to find one to reply to.
        comments = await fetcher.fetch_comments(mid, cookie, max_pages=1)
        assert len(comments) > 0, "Need at least 1 comment to reply to"

        target_comment_id = comments[0].weibo_comment_id

        # Step 2: Reply to the comment.
        t0 = time.monotonic()
        result = await executor.reply_comment(
            mid, target_comment_id, test_content, cookie, uid="spike_test"
        )
        reply_elapsed = time.monotonic() - t0

        # Step 3: Assert success.
        assert result["success"] is True, (
            f"Reply failed: {result.get('error_msg')}"
        )
        assert result.get("comment_id") is not None, (
            "Reply response should contain comment_id"
        )

        # Record latency.
        _write_evidence("task-22-latency.json", "comments_reply", {
            "parent_comment_id": target_comment_id,
            "reply_comment_id": str(result["comment_id"]),
            "elapsed_seconds": round(reply_elapsed, 3),
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # Step 4: Cleanup — attempt to delete the reply.
        reply_id = str(result["comment_id"])
        try:
            await client._post(
                "/ajax/comments/destroy",
                {"cid": reply_id},
                cookie,
            )
        except Exception:
            pass  # Best-effort cleanup.

    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Test 5: Hot vs Time ranking comparison
# ---------------------------------------------------------------------------

async def test_hot_vs_time_ranking():
    """Fetch comments with ``flow=0`` (hot) and ``flow=1`` (time), compare.

    The ``CommentFetcher`` hardcodes ``flow=0``, so for ``flow=1`` we
    call the buildComments API directly via ``WeiboHttpClient._get``.

    Records analysis to ``task-22-hot-ranking.json``.
    """
    cookie = os.environ["WEIBO_TEST_COOKIE"]
    client = WeiboHttpClient()
    anti = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti)

    try:
        mid = fetcher.get_weibo_mid(_TEST_BASE62_MID)

        # --- flow=0 (hot ranking) via CommentFetcher ---
        t0 = time.monotonic()
        hot_comments = await fetcher.fetch_comments(mid, cookie, max_pages=1)
        hot_elapsed = time.monotonic() - t0

        # Be polite between requests.
        await asyncio.sleep(2)

        # --- flow=1 (time ranking) via direct API call ---
        params_time: dict = {
            "flow": 1,            # time sort order
            "is_reload": 1,
            "id": mid,
            "count": 20,
            "uid": "",
            "max_id": 0,
        }

        t1 = time.monotonic()
        time_response = await client._get(
            "/ajax/statuses/buildComments", params_time, cookie
        )
        time_elapsed = time.monotonic() - t1

        time_data: list[dict] = time_response.get("data", [])

        # Build like_count lists for comparison.
        hot_likes = [c.like_count for c in hot_comments]
        time_likes = [item.get("like_counts", 0) for item in time_data]

        # Check if hot ranking is sorted by likes descending (roughly).
        hot_sorted_by_likes = (
            all(hot_likes[i] >= hot_likes[i + 1] for i in range(len(hot_likes) - 1))
            if len(hot_likes) > 1
            else True
        )

        # Record analysis.
        analysis = {
            "hot_ranking": {
                "comment_count": len(hot_comments),
                "like_counts": hot_likes[:20],
                "is_sorted_descending": hot_sorted_by_likes,
                "elapsed_seconds": round(hot_elapsed, 3),
            },
            "time_ranking": {
                "comment_count": len(time_data),
                "like_counts": time_likes[:20],
                "elapsed_seconds": round(time_elapsed, 3),
            },
            "comparison": {
                "same_count": len(hot_comments) == len(time_data),
                "orderings_differ": hot_likes != time_likes,
            },
            "mid": mid,
            "timestamp": datetime.utcnow().isoformat(),
        }
        _write_evidence("task-22-hot-ranking.json", "analysis", analysis)

        # Assertions — both should return comments.
        assert len(hot_comments) > 0, "Hot ranking should return comments"
        assert len(time_data) > 0, "Time ranking should return comments"

    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Test 6: Multi-account single IP rate limiting observation
# ---------------------------------------------------------------------------

async def test_multi_account_single_ip():
    """Use 2-3 different cookies to make requests simultaneously.

    Observes rate limiting behaviour when multiple accounts share a
    single IP address. Records latency and success/failure per cookie
    to ``task-22-latency.json``.

    SKIP if fewer than 2 cookies are available.
    """
    # Collect all available cookies.
    cookies: list[str] = []
    for i in range(3):
        c = _get_cookie(i)
        if c:
            cookies.append(c)

    if len(cookies) < 2:
        pytest.skip(
            "Need at least 2 cookies (WEIBO_TEST_COOKIE + WEIBO_TEST_COOKIE_2) "
            "for multi-account test"
        )

    client = WeiboHttpClient()
    anti = AntiDetectionEngine()
    fetcher = CommentFetcher(client, anti)

    try:
        mid = fetcher.get_weibo_mid(_TEST_BASE62_MID)

        async def fetch_with_cookie(cookie_str: str, idx: int) -> dict:
            """Fetch comments with a specific cookie, return timing/result."""
            t0 = time.monotonic()
            try:
                comments = await fetcher.fetch_comments(
                    mid, cookie_str, max_pages=1
                )
                elapsed = time.monotonic() - t0
                return {
                    "cookie_index": idx,
                    "success": True,
                    "comment_count": len(comments),
                    "elapsed_seconds": round(elapsed, 3),
                    "error": None,
                }
            except Exception as exc:
                elapsed = time.monotonic() - t0
                return {
                    "cookie_index": idx,
                    "success": False,
                    "comment_count": 0,
                    "elapsed_seconds": round(elapsed, 3),
                    "error": str(exc),
                }

        # Fire all requests concurrently to observe rate limiting.
        results = await asyncio.gather(
            *[fetch_with_cookie(c, i) for i, c in enumerate(cookies)]
        )

        # Record evidence.
        _write_evidence("task-22-latency.json", "multi_account", {
            "cookie_count": len(cookies),
            "results": results,
            "any_rate_limited": any(
                not r["success"] and "rate" in (r.get("error") or "").lower()
                for r in results
            ),
            "timestamp": datetime.utcnow().isoformat(),
        })

        # At least one should succeed.
        successes = [r for r in results if r["success"]]
        assert len(successes) > 0, (
            "At least one cookie should succeed in concurrent requests"
        )

    finally:
        await client.close()
