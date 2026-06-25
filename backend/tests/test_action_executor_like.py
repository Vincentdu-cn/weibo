"""Tests for ActionExecutor — comment liking, batch liking, and unliking.

TDD: written before implementation. Covers:
- like_comment: correct endpoint, body, success/failure handling, DB logging
- batch_like: sequential execution, delays between likes, per-cookie results
- unlike_comment: correct endpoint (destroyLike), success/failure handling
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.action_executor import ActionExecutor
from app.services.anti_detection import AntiDetectionEngine
from app.services.weibo_client import WeiboHttpClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    """A WeiboHttpClient with _post mocked as AsyncMock."""
    client = WeiboHttpClient()
    client._post = AsyncMock()
    return client


@pytest.fixture
def mock_anti_detection():
    """An AntiDetectionEngine with wait_action mocked to return immediately."""
    engine = AntiDetectionEngine()
    engine.wait_action = AsyncMock(return_value=0.01)
    return engine


# ---------------------------------------------------------------------------
# like_comment — success
# ---------------------------------------------------------------------------


class TestLikeComment:
    """Tests for ActionExecutor.like_comment."""

    @pytest.mark.asyncio
    async def test_like_comment_success(self, mock_client):
        """like_comment returns success=True when API returns ok > 0."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        result = await executor.like_comment("123456", "SUB=abc; XSRF-TOKEN=tok")

        assert result["success"] is True
        assert result["error_msg"] is None

    @pytest.mark.asyncio
    async def test_like_comment_success_ok_gt_1(self, mock_client):
        """like_comment treats ok > 0 as success (not just ok == 1)."""
        mock_client._post.return_value = {"ok": 3}
        executor = ActionExecutor(client=mock_client)

        result = await executor.like_comment("123", "SUB=abc")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_like_comment_already_liked(self, mock_client):
        """like_comment returns success=False when ok == 0 (already liked, deleted, etc.)."""
        mock_client._post.return_value = {"ok": 0, "msg": "already liked"}
        executor = ActionExecutor(client=mock_client)

        result = await executor.like_comment("123", "SUB=abc")

        assert result["success"] is False
        assert result["error_msg"] is not None
        assert "already liked" in result["error_msg"]

    @pytest.mark.asyncio
    async def test_like_comment_ok_zero_no_msg(self, mock_client):
        """like_comment handles ok=0 with no msg field gracefully."""
        mock_client._post.return_value = {"ok": 0}
        executor = ActionExecutor(client=mock_client)

        result = await executor.like_comment("123", "SUB=abc")

        assert result["success"] is False
        assert result["error_msg"] is not None

    @pytest.mark.asyncio
    async def test_like_comment_calls_correct_endpoint(self, mock_client):
        """like_comment must POST to /ajax/statuses/updateLike."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.like_comment("999", "SUB=abc; XSRF-TOKEN=tok")

        mock_client._post.assert_called_once_with(
            "/ajax/statuses/updateLike",
            {"object_id": "999", "object_type": "comment"},
            "SUB=abc; XSRF-TOKEN=tok",
        )

    @pytest.mark.asyncio
    async def test_like_comment_object_type_is_comment(self, mock_client):
        """like_comment must use object_type='comment', NOT 'status' or 'weibo'."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.like_comment("42", "SUB=abc")

        _, data, _ = mock_client._post.call_args.args
        assert data["object_type"] == "comment"

    @pytest.mark.asyncio
    async def test_like_comment_object_id_is_string(self, mock_client):
        """like_comment must send object_id as a string."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.like_comment(12345, "SUB=abc")

        _, data, _ = mock_client._post.call_args.args
        assert data["object_id"] == "12345"
        assert isinstance(data["object_id"], str)

    @pytest.mark.asyncio
    async def test_like_comment_exception_returns_failure(self, mock_client):
        """like_comment catches exceptions and returns success=False."""
        mock_client._post.side_effect = Exception("Network error")
        executor = ActionExecutor(client=mock_client)

        result = await executor.like_comment("123", "SUB=abc")

        assert result["success"] is False
        assert "Network error" in result["error_msg"]


# ---------------------------------------------------------------------------
# like_comment — DB logging
# ---------------------------------------------------------------------------


class TestLikeCommentLogging:
    """Tests for ActionLog database logging in like_comment."""

    @pytest.mark.asyncio
    async def test_like_comment_logs_success(self, mock_client, db_session):
        """like_comment creates an ActionLog entry with status='success' on success."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client, db_session=db_session)

        await executor.like_comment("789", "SUB=abc", uid="uid_001")

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.account_uid == "uid_001"
        assert log.action_type == "like"
        assert log.target_comment_id == "789"
        assert log.status == "success"

    @pytest.mark.asyncio
    async def test_like_comment_logs_failure(self, mock_client, db_session):
        """like_comment creates an ActionLog entry with status='failed' on failure."""
        mock_client._post.return_value = {"ok": 0, "msg": "rate limited"}
        executor = ActionExecutor(client=mock_client, db_session=db_session)

        await executor.like_comment("789", "SUB=abc", uid="uid_002")

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.status == "failed"
        assert log.account_uid == "uid_002"

    @pytest.mark.asyncio
    async def test_like_comment_logs_without_db_session(self, mock_client):
        """like_comment does not crash when db_session is None (no logging)."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client, db_session=None)

        result = await executor.like_comment("789", "SUB=abc")

        assert result["success"] is True  # no crash


# ---------------------------------------------------------------------------
# batch_like — sequential execution
# ---------------------------------------------------------------------------


class TestBatchLike:
    """Tests for ActionExecutor.batch_like."""

    @pytest.mark.asyncio
    async def test_batch_like_returns_one_result_per_cookie(
        self, mock_client, mock_anti_detection
    ):
        """batch_like returns exactly one result dict per cookie."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=cookie1"),
            ("uid2", "SUB=cookie2"),
            ("uid3", "SUB=cookie3"),
        ]
        results = await executor.batch_like("999", cookies)

        assert len(results) == 3
        for r in results:
            assert "uid" in r
            assert "success" in r
            assert "error_msg" in r

    @pytest.mark.asyncio
    async def test_batch_like_all_success(self, mock_client, mock_anti_detection):
        """batch_like returns success=True for all cookies when API returns ok."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [("uid1", "SUB=cookie1"), ("uid2", "SUB=cookie2")]
        results = await executor.batch_like("999", cookies)

        assert all(r["success"] for r in results)
        assert results[0]["uid"] == "uid1"
        assert results[1]["uid"] == "uid2"

    @pytest.mark.asyncio
    async def test_batch_like_partial_failure(self, mock_client, mock_anti_detection):
        """batch_like handles partial failures — some succeed, some fail."""
        mock_client._post.side_effect = [
            {"ok": 1},
            {"ok": 0, "msg": "already liked"},
            {"ok": 1},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        results = await executor.batch_like("42", cookies)

        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_batch_like_calls_wait_action_between_likes(
        self, mock_client, mock_anti_detection
    ):
        """batch_like must call wait_action between each like (N-1 times for N cookies)."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        await executor.batch_like("42", cookies)

        # 3 cookies => 2 waits (between cookie 1-2 and 2-3)
        assert mock_anti_detection.wait_action.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_like_no_wait_before_first_or_after_last(
        self, mock_client, mock_anti_detection
    ):
        """batch_like should not call wait_action before first like or after last."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [("uid1", "SUB=c1")]
        await executor.batch_like("42", cookies)

        # Single cookie => 0 waits
        assert mock_anti_detection.wait_action.call_count == 0

    @pytest.mark.asyncio
    async def test_batch_like_sequential_not_parallel(
        self, mock_client, mock_anti_detection
    ):
        """batch_like executes likes sequentially — _post calls are in order."""
        call_order = []

        async def mock_post(path, data, cookie):
            call_order.append(cookie)
            return {"ok": 1}

        mock_client._post.side_effect = mock_post
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        await executor.batch_like("42", cookies)

        assert call_order == ["SUB=c1", "SUB=c2", "SUB=c3"]

    @pytest.mark.asyncio
    async def test_batch_like_empty_cookies(self, mock_client, mock_anti_detection):
        """batch_like with empty cookie list returns empty list."""
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_like("42", [])

        assert results == []
        mock_client._post.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_like_continues_on_failure(
        self, mock_client, mock_anti_detection
    ):
        """batch_like does not abort when one like fails — continues to next cookie."""
        mock_client._post.side_effect = [
            {"ok": 1},
            {"ok": 0, "msg": "failed"},
            {"ok": 1},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        results = await executor.batch_like("42", cookies)

        assert len(results) == 3
        assert mock_client._post.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_like_exception_does_not_abort(
        self, mock_client, mock_anti_detection
    ):
        """batch_like handles exceptions per-cookie and continues."""
        mock_client._post.side_effect = [
            {"ok": 1},
            Exception("timeout"),
            {"ok": 1},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        results = await executor.batch_like("42", cookies)

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "timeout" in results[1]["error_msg"]
        assert results[2]["success"] is True


# ---------------------------------------------------------------------------
# unlike_comment
# ---------------------------------------------------------------------------


class TestUnlikeComment:
    """Tests for ActionExecutor.unlike_comment."""

    @pytest.mark.asyncio
    async def test_unlike_comment_success(self, mock_client):
        """unlike_comment returns success=True when API returns ok > 0."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        result = await executor.unlike_comment("123456", "SUB=abc")

        assert result["success"] is True
        assert result["error_msg"] is None

    @pytest.mark.asyncio
    async def test_unlike_comment_failure(self, mock_client):
        """unlike_comment returns success=False when ok == 0."""
        mock_client._post.return_value = {"ok": 0, "msg": "not liked"}
        executor = ActionExecutor(client=mock_client)

        result = await executor.unlike_comment("123", "SUB=abc")

        assert result["success"] is False
        assert result["error_msg"] is not None

    @pytest.mark.asyncio
    async def test_unlike_comment_calls_destroy_like_endpoint(self, mock_client):
        """unlike_comment must POST to /ajax/statuses/destroyLike."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.unlike_comment("999", "SUB=abc; XSRF-TOKEN=tok")

        mock_client._post.assert_called_once_with(
            "/ajax/statuses/destroyLike",
            {"object_id": "999", "object_type": "comment"},
            "SUB=abc; XSRF-TOKEN=tok",
        )

    @pytest.mark.asyncio
    async def test_unlike_comment_object_type_is_comment(self, mock_client):
        """unlike_comment must use object_type='comment'."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.unlike_comment("42", "SUB=abc")

        _, data, _ = mock_client._post.call_args.args
        assert data["object_type"] == "comment"

    @pytest.mark.asyncio
    async def test_unlike_comment_exception_returns_failure(self, mock_client):
        """unlike_comment catches exceptions and returns success=False."""
        mock_client._post.side_effect = Exception("Connection refused")
        executor = ActionExecutor(client=mock_client)

        result = await executor.unlike_comment("123", "SUB=abc")

        assert result["success"] is False
        assert "Connection refused" in result["error_msg"]

    @pytest.mark.asyncio
    async def test_unlike_comment_logs_to_db(self, mock_client, db_session):
        """unlike_comment creates an ActionLog entry."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client, db_session=db_session)

        await executor.unlike_comment("789", "SUB=abc", uid="uid_003")

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.account_uid == "uid_003"
        assert log.action_type == "unlike"
        assert log.target_comment_id == "789"
        assert log.status == "success"


# ---------------------------------------------------------------------------
# ActionExecutor initialization
# ---------------------------------------------------------------------------


class TestActionExecutorInit:
    """Tests for ActionExecutor construction and defaults."""

    def test_init_with_all_params(self, mock_client, mock_anti_detection):
        """ActionExecutor accepts client, anti_detection, and db_session."""
        executor = ActionExecutor(
            client=mock_client,
            anti_detection=mock_anti_detection,
            db_session=MagicMock(),
        )
        assert executor.client is mock_client
        assert executor.anti_detection is mock_anti_detection
        assert executor.db_session is not None

    def test_init_creates_default_anti_detection(self, mock_client):
        """ActionExecutor creates a default AntiDetectionEngine when not provided."""
        executor = ActionExecutor(client=mock_client)
        assert executor.anti_detection is not None
        assert isinstance(executor.anti_detection, AntiDetectionEngine)

    def test_init_db_session_defaults_none(self, mock_client):
        """ActionExecutor defaults db_session to None."""
        executor = ActionExecutor(client=mock_client)
        assert executor.db_session is None
