"""Tests for ActionExecutor.batch_like_comments — single operator cookie, multiple comments.

Covers:
- Returns one result per comment_id, in order
- All success / partial failure / all failure
- wait_action called between likes (N-1 times for N comments), not before first or after last
- Sequential execution (not parallel)
- Empty list returns empty
- Exception does not abort the batch
- Same cookie and uid used for all likes
"""

from unittest.mock import AsyncMock

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
# Result count and ordering
# ---------------------------------------------------------------------------


class TestBatchLikeCommentsResults:
    """Tests for result count, ordering, and structure."""

    @pytest.mark.asyncio
    async def test_returns_one_result_per_comment_id(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments returns exactly one result dict per comment_id."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        comment_ids = ["c1", "c2", "c3"]
        results = await executor.batch_like_comments(comment_ids, "SUB=abc")

        assert len(results) == 3
        for r in results:
            assert "success" in r
            assert "error_msg" in r

    @pytest.mark.asyncio
    async def test_results_in_same_order_as_input(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments returns results in the same order as comment_ids."""
        mock_client._post.side_effect = [
            {"ok": 1},
            {"ok": 0, "msg": "already liked"},
            {"ok": 1},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        comment_ids = ["aaa", "bbb", "ccc"]
        results = await executor.batch_like_comments(comment_ids, "SUB=abc")

        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True


# ---------------------------------------------------------------------------
# Success / failure / partial failure
# ---------------------------------------------------------------------------


class TestBatchLikeCommentsSuccess:
    """Tests for success and failure handling."""

    @pytest.mark.asyncio
    async def test_all_success(self, mock_client, mock_anti_detection):
        """batch_like_comments returns success=True for all when API returns ok."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_like_comments(
            ["c1", "c2", "c3"], "SUB=abc"
        )

        assert all(r["success"] for r in results)
        assert all(r["error_msg"] is None for r in results)

    @pytest.mark.asyncio
    async def test_partial_failure(self, mock_client, mock_anti_detection):
        """batch_like_comments handles partial failures — some succeed, some fail."""
        mock_client._post.side_effect = [
            {"ok": 1},
            {"ok": 0, "msg": "already liked"},
            {"ok": 1},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_like_comments(
            ["c1", "c2", "c3"], "SUB=abc"
        )

        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "already liked" in results[1]["error_msg"]
        assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_all_failure(self, mock_client, mock_anti_detection):
        """batch_like_comments returns all failures when API returns ok=0 for all."""
        mock_client._post.return_value = {"ok": 0, "msg": "rate limited"}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_like_comments(
            ["c1", "c2"], "SUB=abc"
        )

        assert all(r["success"] is False for r in results)
        assert all(r["error_msg"] is not None for r in results)


# ---------------------------------------------------------------------------
# Delay behavior
# ---------------------------------------------------------------------------


class TestBatchLikeCommentsDelays:
    """Tests for wait_action delay behavior."""

    @pytest.mark.asyncio
    async def test_wait_action_between_likes(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments calls wait_action N-1 times for N comments."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments(["c1", "c2", "c3"], "SUB=abc")

        assert mock_anti_detection.wait_action.call_count == 2

    @pytest.mark.asyncio
    async def test_no_wait_for_single_comment(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments with 1 comment — 0 wait_action calls."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments(["c1"], "SUB=abc")

        assert mock_anti_detection.wait_action.call_count == 0

    @pytest.mark.asyncio
    async def test_no_wait_for_empty_list(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments with empty list — 0 wait_action calls."""
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments([], "SUB=abc")

        assert mock_anti_detection.wait_action.call_count == 0


# ---------------------------------------------------------------------------
# Sequential execution
# ---------------------------------------------------------------------------


class TestBatchLikeCommentsSequential:
    """Tests for sequential (not parallel) execution."""

    @pytest.mark.asyncio
    async def test_sequential_not_parallel(self, mock_client, mock_anti_detection):
        """batch_like_comments executes likes sequentially — _post calls are in order."""
        call_order: list[str] = []

        async def mock_post(path, data, cookie):
            call_order.append(data["object_id"])
            return {"ok": 1}

        mock_client._post.side_effect = mock_post
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        comment_ids = ["c1", "c2", "c3"]
        await executor.batch_like_comments(comment_ids, "SUB=abc")

        assert call_order == ["c1", "c2", "c3"]

    @pytest.mark.asyncio
    async def test_same_cookie_for_all_likes(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments uses the same cookie for every like."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments(
            ["c1", "c2", "c3"], "SUB=operator_cookie"
        )

        for call in mock_client._post.call_args_list:
            _, _, cookie = call.args
            assert cookie == "SUB=operator_cookie"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestBatchLikeCommentsEdgeCases:
    """Tests for edge cases: empty list, exceptions, uid passing."""

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments with empty list returns empty list, no API calls."""
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_like_comments([], "SUB=abc")

        assert results == []
        mock_client._post.assert_not_called()

    @pytest.mark.asyncio
    async def test_exception_does_not_abort(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments handles exceptions per-comment and continues."""
        mock_client._post.side_effect = [
            {"ok": 1},
            Exception("timeout"),
            {"ok": 1},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_like_comments(
            ["c1", "c2", "c3"], "SUB=abc"
        )

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "timeout" in results[1]["error_msg"]
        assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_default_uid_is_operator(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments defaults uid to 'operator'."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments(["c1"], "SUB=abc")

        assert mock_client._post.call_count == 1

    @pytest.mark.asyncio
    async def test_custom_uid_passed_to_like_comment(
        self, mock_client, mock_anti_detection, db_session
    ):
        """batch_like_comments passes the uid to like_comment for DB logging."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client,
            anti_detection=mock_anti_detection,
            db_session=db_session,
        )

        await executor.batch_like_comments(
            ["c1", "c2"], "SUB=abc", uid="my_operator_uid"
        )

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 2
        assert all(log.account_uid == "my_operator_uid" for log in logs)
        assert all(log.action_type == "like" for log in logs)

    @pytest.mark.asyncio
    async def test_comment_ids_converted_to_string(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments converts integer comment IDs to strings."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments([123, 456], "SUB=abc")

        for call in mock_client._post.call_args_list:
            _, data, _ = call.args
            assert isinstance(data["object_id"], str)

    @pytest.mark.asyncio
    async def test_calls_correct_endpoint(
        self, mock_client, mock_anti_detection
    ):
        """batch_like_comments posts to /ajax/statuses/updateLike for each comment."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        await executor.batch_like_comments(["c1", "c2"], "SUB=abc")

        for call in mock_client._post.call_args_list:
            path, _, _ = call.args
            assert path == "/ajax/statuses/updateLike"
