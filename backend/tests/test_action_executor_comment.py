"""Tests for ActionExecutor — comment posting, replying, and batch commenting.

TDD: written before implementation. Covers:
- post_comment: correct endpoint, body, success/failure handling, comment_id extraction,
  500-comment limit enforcement, DB increment, DB logging
- reply_comment: correct endpoint (reply), cid field, success/failure handling, DB logging
- batch_comment: sequential execution, wait_comment delays, per-cookie results,
  500-limit mid-batch, continues on failure
"""

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
    """An AntiDetectionEngine with wait_comment mocked to return immediately."""
    engine = AntiDetectionEngine()
    engine.wait_comment = AsyncMock(return_value=0.01)
    engine.wait_action = AsyncMock(return_value=0.01)
    return engine


# ---------------------------------------------------------------------------
# post_comment — success / failure / exception
# ---------------------------------------------------------------------------


class TestPostComment:
    """Tests for ActionExecutor.post_comment."""

    @pytest.mark.asyncio
    async def test_post_comment_success(self, mock_client):
        """post_comment returns success=True with comment_id when API returns ok > 0 and comment.id."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "new_c1"}}
        executor = ActionExecutor(client=mock_client)

        result = await executor.post_comment("5056360400000000", "test comment", "SUB=abc")

        assert result["success"] is True
        assert result["comment_id"] == "new_c1"
        assert result["error_msg"] is None

    @pytest.mark.asyncio
    async def test_post_comment_failure_ok_zero(self, mock_client):
        """post_comment returns success=False when ok == 0."""
        mock_client._post.return_value = {"ok": 0, "msg": "rate limited"}
        executor = ActionExecutor(client=mock_client)

        result = await executor.post_comment("123", "test", "SUB=abc")

        assert result["success"] is False
        assert result["comment_id"] is None
        assert result["error_msg"] is not None
        assert "rate limited" in result["error_msg"]

    @pytest.mark.asyncio
    async def test_post_comment_exception(self, mock_client):
        """post_comment catches exceptions and returns success=False."""
        mock_client._post.side_effect = Exception("Network error")
        executor = ActionExecutor(client=mock_client)

        result = await executor.post_comment("123", "test", "SUB=abc")

        assert result["success"] is False
        assert result["comment_id"] is None
        assert "Network error" in result["error_msg"]

    @pytest.mark.asyncio
    async def test_post_comment_success_without_comment_id(self, mock_client):
        """post_comment returns success=True with comment_id=None when response has no comment object."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        result = await executor.post_comment("123", "test", "SUB=abc")

        assert result["success"] is True
        assert result["comment_id"] is None

    @pytest.mark.asyncio
    async def test_post_comment_correct_api_path(self, mock_client):
        """post_comment must POST to /ajax/comments/create."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.post_comment("999", "hello", "SUB=abc; XSRF-TOKEN=tok")

        call_args = mock_client._post.call_args
        assert call_args.args[0] == "/ajax/comments/create"

    @pytest.mark.asyncio
    async def test_post_comment_correct_body(self, mock_client):
        """post_comment must send the correct body structure."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.post_comment("999", "hello world", "SUB=abc")

        _, data, _ = mock_client._post.call_args.args
        assert data["id"] == "999"
        assert data["comment"] == "hello world"
        assert data["pic_id"] == ""
        assert data["is_repost"] == 0
        assert data["comment_ori"] == 0
        assert data["is_comment"] == 0

    @pytest.mark.asyncio
    async def test_post_comment_mid_converted_to_string(self, mock_client):
        """post_comment must convert weibo_mid to string in the body."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.post_comment(12345, "test", "SUB=abc")

        _, data, _ = mock_client._post.call_args.args
        assert data["id"] == "12345"
        assert isinstance(data["id"], str)


# ---------------------------------------------------------------------------
# post_comment — 500-comment limit
# ---------------------------------------------------------------------------


class TestPostCommentLimit:
    """Tests for the 500-comment limit enforcement in post_comment."""

    @pytest.mark.asyncio
    async def test_post_comment_500_limit_blocks(self, mock_client, db_session):
        """post_comment returns failure when total_comments >= 500 — no API call made."""
        from app.models.competition_session import CompetitionSession

        session = CompetitionSession(
            target_weibo_url="https://weibo.com/123",
            target_weibo_mid="999",
            total_comments=500,
        )
        db_session.add(session)
        db_session.commit()

        executor = ActionExecutor(client=mock_client, db_session=db_session)
        result = await executor.post_comment("999", "test", "SUB=abc")

        assert result["success"] is False
        assert result["comment_id"] is None
        assert "limit" in result["error_msg"].lower()
        mock_client._post.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_comment_499_succeeds_and_increments(self, mock_client, db_session):
        """post_comment at 499 comments succeeds and increments to 500."""
        from app.models.competition_session import CompetitionSession

        session = CompetitionSession(
            target_weibo_url="https://weibo.com/123",
            target_weibo_mid="999",
            total_comments=499,
        )
        db_session.add(session)
        db_session.commit()

        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c500"}}
        executor = ActionExecutor(client=mock_client, db_session=db_session)
        result = await executor.post_comment("999", "test", "SUB=abc")

        assert result["success"] is True
        assert result["comment_id"] == "c500"

        db_session.refresh(session)
        assert session.total_comments == 500

    @pytest.mark.asyncio
    async def test_post_comment_no_db_session_no_limit_check(self, mock_client):
        """post_comment with db_session=None — no limit check, no increment, just API call."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c1"}}
        executor = ActionExecutor(client=mock_client, db_session=None)

        result = await executor.post_comment("999", "test", "SUB=abc")

        assert result["success"] is True
        mock_client._post.assert_called_once()


# ---------------------------------------------------------------------------
# post_comment — DB logging
# ---------------------------------------------------------------------------


class TestPostCommentLogging:
    """Tests for ActionLog database logging in post_comment."""

    @pytest.mark.asyncio
    async def test_post_comment_logs_success(self, mock_client, db_session):
        """post_comment creates an ActionLog entry with action_type='comment' on success."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "new_c1"}}
        executor = ActionExecutor(client=mock_client, db_session=db_session)

        await executor.post_comment("789", "test comment", "SUB=abc", uid="uid_001")

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.account_uid == "uid_001"
        assert log.action_type == "comment"
        assert log.target_comment_id == ""
        assert log.status == "success"

    @pytest.mark.asyncio
    async def test_post_comment_logs_failure(self, mock_client, db_session):
        """post_comment creates an ActionLog entry with status='failed' on failure."""
        mock_client._post.return_value = {"ok": 0, "msg": "rate limited"}
        executor = ActionExecutor(client=mock_client, db_session=db_session)

        await executor.post_comment("789", "test", "SUB=abc", uid="uid_002")

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.status == "failed"
        assert log.action_type == "comment"


# ---------------------------------------------------------------------------
# reply_comment
# ---------------------------------------------------------------------------


class TestReplyComment:
    """Tests for ActionExecutor.reply_comment."""

    @pytest.mark.asyncio
    async def test_reply_comment_success(self, mock_client):
        """reply_comment returns success=True with comment_id when API returns ok > 0."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "reply_c1"}}
        executor = ActionExecutor(client=mock_client)

        result = await executor.reply_comment("999", "parent_c1", "reply text", "SUB=abc")

        assert result["success"] is True
        assert result["comment_id"] == "reply_c1"

    @pytest.mark.asyncio
    async def test_reply_comment_failure(self, mock_client):
        """reply_comment returns success=False when ok == 0."""
        mock_client._post.return_value = {"ok": 0}
        executor = ActionExecutor(client=mock_client)

        result = await executor.reply_comment("999", "parent_c1", "reply text", "SUB=abc")

        assert result["success"] is False
        assert result["comment_id"] is None

    @pytest.mark.asyncio
    async def test_reply_comment_correct_api_path(self, mock_client):
        """reply_comment must POST to /ajax/comments/reply."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.reply_comment("999", "parent_c1", "reply text", "SUB=abc")

        call_args = mock_client._post.call_args
        assert call_args.args[0] == "/ajax/comments/reply"

    @pytest.mark.asyncio
    async def test_reply_comment_body_includes_cid(self, mock_client):
        """reply_comment must include cid field (as string) in the request body."""
        mock_client._post.return_value = {"ok": 1}
        executor = ActionExecutor(client=mock_client)

        await executor.reply_comment("999", 12345, "reply text", "SUB=abc")

        _, data, _ = mock_client._post.call_args.args
        assert data["id"] == "999"
        assert data["cid"] == "12345"
        assert isinstance(data["cid"], str)
        assert data["comment"] == "reply text"

    @pytest.mark.asyncio
    async def test_reply_comment_logs_with_action_type_reply(self, mock_client, db_session):
        """reply_comment creates an ActionLog entry with action_type='reply' and target_comment_id set."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "reply_c1"}}
        executor = ActionExecutor(client=mock_client, db_session=db_session)

        await executor.reply_comment("789", "parent_c1", "reply text", "SUB=abc", uid="uid_003")

        from app.models.action_log import ActionLog

        logs = db_session.query(ActionLog).all()
        assert len(logs) == 1
        log = logs[0]
        assert log.account_uid == "uid_003"
        assert log.action_type == "reply"
        assert log.target_comment_id == "parent_c1"
        assert log.status == "success"

    @pytest.mark.asyncio
    async def test_reply_comment_500_limit_blocks(self, mock_client, db_session):
        """reply_comment also enforces the 500-comment limit."""
        from app.models.competition_session import CompetitionSession

        session = CompetitionSession(
            target_weibo_url="https://weibo.com/123",
            target_weibo_mid="999",
            total_comments=500,
        )
        db_session.add(session)
        db_session.commit()

        executor = ActionExecutor(client=mock_client, db_session=db_session)
        result = await executor.reply_comment("999", "parent_c1", "reply", "SUB=abc")

        assert result["success"] is False
        mock_client._post.assert_not_called()


# ---------------------------------------------------------------------------
# batch_comment
# ---------------------------------------------------------------------------


class TestBatchComment:
    """Tests for ActionExecutor.batch_comment."""

    @pytest.mark.asyncio
    async def test_batch_comment_all_success(self, mock_client, mock_anti_detection):
        """batch_comment with 3 cookies all succeeding returns 3 success results."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c1"}}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        results = await executor.batch_comment("999", "test comment", cookies)

        assert len(results) == 3
        for r in results:
            assert r["success"] is True
            assert "uid" in r
            assert "comment_id" in r
            assert "error_msg" in r

    @pytest.mark.asyncio
    async def test_batch_comment_partial_failure(self, mock_client, mock_anti_detection):
        """batch_comment continues when one cookie fails — others succeed."""
        mock_client._post.side_effect = [
            {"ok": 1, "comment": {"id": "c1"}},
            {"ok": 0, "msg": "rate limited"},
            {"ok": 1, "comment": {"id": "c3"}},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        results = await executor.batch_comment("42", "test", cookies)

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_batch_comment_uses_wait_comment_between_posts(
        self, mock_client, mock_anti_detection
    ):
        """batch_comment must call wait_comment (NOT wait_action) between posts — N-1 times for N cookies."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c1"}}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        await executor.batch_comment("42", "test", cookies)

        # 3 cookies => 2 waits (between cookie 1-2 and 2-3)
        assert mock_anti_detection.wait_comment.call_count == 2
        # wait_action should NOT be called for batch_comment
        assert mock_anti_detection.wait_action.call_count == 0

    @pytest.mark.asyncio
    async def test_batch_comment_no_wait_for_single_cookie(
        self, mock_client, mock_anti_detection
    ):
        """batch_comment with 1 cookie — no wait_comment calls."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c1"}}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [("uid1", "SUB=c1")]
        await executor.batch_comment("42", "test", cookies)

        assert mock_anti_detection.wait_comment.call_count == 0

    @pytest.mark.asyncio
    async def test_batch_comment_500_limit_mid_batch(self, mock_client, mock_anti_detection, db_session):
        """batch_comment checks 500-limit BEFORE each post — first succeeds (→500), second blocked."""
        from app.models.competition_session import CompetitionSession

        session = CompetitionSession(
            target_weibo_url="https://weibo.com/123",
            target_weibo_mid="999",
            total_comments=499,
        )
        db_session.add(session)
        db_session.commit()

        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c500"}}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection, db_session=db_session
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
        ]
        results = await executor.batch_comment("999", "test", cookies)

        # First succeeds (499 → 500), second blocked by limit
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "limit" in results[1]["error_msg"].lower()
        # Only 1 API call made (first cookie only)
        assert mock_client._post.call_count == 1

    @pytest.mark.asyncio
    async def test_batch_comment_empty_cookies(self, mock_client, mock_anti_detection):
        """batch_comment with empty cookie list returns empty list."""
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        results = await executor.batch_comment("42", "test", [])

        assert results == []
        mock_client._post.assert_not_called()

    @pytest.mark.asyncio
    async def test_batch_comment_exception_continues(
        self, mock_client, mock_anti_detection
    ):
        """batch_comment handles exceptions per-cookie and continues."""
        mock_client._post.side_effect = [
            {"ok": 1, "comment": {"id": "c1"}},
            Exception("timeout"),
            {"ok": 1, "comment": {"id": "c3"}},
        ]
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [
            ("uid1", "SUB=c1"),
            ("uid2", "SUB=c2"),
            ("uid3", "SUB=c3"),
        ]
        results = await executor.batch_comment("42", "test", cookies)

        assert len(results) == 3
        assert results[0]["success"] is True
        assert results[1]["success"] is False
        assert "timeout" in results[1]["error_msg"]
        assert results[2]["success"] is True

    @pytest.mark.asyncio
    async def test_batch_comment_result_has_uid(self, mock_client, mock_anti_detection):
        """batch_comment results include the uid from the cookie tuple."""
        mock_client._post.return_value = {"ok": 1, "comment": {"id": "c1"}}
        executor = ActionExecutor(
            client=mock_client, anti_detection=mock_anti_detection
        )

        cookies = [("my_uid", "SUB=c1"), ("other_uid", "SUB=c2")]
        results = await executor.batch_comment("42", "test", cookies)

        assert results[0]["uid"] == "my_uid"
        assert results[1]["uid"] == "other_uid"
