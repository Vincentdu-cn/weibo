"""Tests for CommentFetcher — URL-to-mid conversion, paginated comment fetching,
and snapshot persistence.

TDD: written before implementation. Covers base62 decoding, URL parsing,
buildComments API pagination, DTO construction, anti-detection integration,
and DB snapshot saving.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.comment_fetcher import CommentFetcher
from app.services.anti_detection import AntiDetectionEngine
from app.services.weibo_client import WeiboHttpClient
from app.schemas.comment import CommentDTO
from app.models.comment import Comment
from app.models.comment_snapshot import CommentSnapshot


# ---------------------------------------------------------------------------
# Helper: build a fake buildComments API response
# ---------------------------------------------------------------------------

def _make_comment(
    cid: int,
    text: str,
    likes: int,
    user_id: int,
    screen_name: str,
    created_at: str = "Thu Jun 25 10:00:00 +0800 2025",
) -> dict:
    """Build a single comment item as returned by the buildComments API."""
    return {
        "id": cid,
        "text": text,
        "like_counts": likes,
        "created_at": created_at,
        "user": {"id": user_id, "screen_name": screen_name},
    }


def _make_response(data: list[dict], max_id: int = 0) -> dict:
    """Build a full buildComments API response."""
    return {"data": data, "max_id": max_id, "max_id_type": 0}


# ---------------------------------------------------------------------------
# get_weibo_mid — URL parsing and base62 decoding
# ---------------------------------------------------------------------------

class TestGetWeiboMid:
    """Tests for URL-to-mid base62 conversion."""

    def test_known_value_z0JH2lOMb(self):
        """Known WeiboSpider test case: 'z0JH2lOMb' -> 3501756485200075."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("z0JH2lOMb")
        assert mid == "3501756485200075"

    def test_full_url_with_https(self):
        """Full HTTPS URL must extract base62 part after last '/'."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("https://weibo.com/1234567890/z0JH2lOMb")
        assert mid == "3501756485200075"

    def test_full_url_with_http(self):
        """HTTP protocol URL must also work."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("http://weibo.com/1234567890/z0JH2lOMb")
        assert mid == "3501756485200075"

    def test_url_with_www(self):
        """URL with www prefix must work."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("https://www.weibo.com/1234567890/z0JH2lOMb")
        assert mid == "3501756485200075"

    def test_url_without_protocol(self):
        """URL without protocol must work."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("weibo.com/1234567890/z0JH2lOMb")
        assert mid == "3501756485200075"

    def test_url_with_query_params(self):
        """URL with query params must strip them before decoding."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid(
            "https://weibo.com/1234567890/z0JH2lOMb?type=comment"
        )
        assert mid == "3501756485200075"

    def test_url_with_trailing_slash(self):
        """URL with trailing slash must still extract the base62 part."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("https://weibo.com/1234567890/z0JH2lOMb/")
        assert mid == "3501756485200075"

    def test_just_base62_string(self):
        """Bare base62 string (no URL) must decode correctly."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("z0JH2lOMb")
        assert mid == "3501756485200075"

    def test_simple_four_char_base62(self):
        """4-char base62 'ABCD' must decode to 8724431."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("ABCD")
        assert mid == "8724431"

    def test_five_char_base62(self):
        """5-char base62 'zABCD' must decode to 358724431."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("zABCD")
        assert mid == "358724431"

    def test_three_char_base62(self):
        """3-char base62 'zAB' must decode to 136809."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("zAB")
        assert mid == "136809"

    def test_single_char_base62(self):
        """Single char 'z' must decode to 35."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("z")
        assert mid == "35"

    def test_single_zero(self):
        """Single '0' must return '0' (edge case: lstrip must not eat all)."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("0")
        assert mid == "0"

    def test_returns_string(self):
        """get_weibo_mid must always return a string."""
        fetcher = CommentFetcher.__new__(CommentFetcher)
        mid = fetcher.get_weibo_mid("https://weibo.com/123/ABCD")
        assert isinstance(mid, str)


# ---------------------------------------------------------------------------
# fetch_comments — single page
# ---------------------------------------------------------------------------

class TestFetchCommentsSinglePage:
    """Tests for single-page comment fetching."""

    async def test_single_page_returns_comments(self):
        """Single page with 2 comments, max_id=0 must return 2 DTOs."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([
            _make_comment(101, "Great!", 10, 1001, "alice"),
            _make_comment(102, "Nice.", 5, 1002, "bob"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert len(results) == 2
        assert all(isinstance(c, CommentDTO) for c in results)
        await client.close()

    async def test_dto_fields_populated(self):
        """Each DTO must have correct field values from API response."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([
            _make_comment(101, "Great post!", 10, 1001, "alice"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        dto = results[0]
        assert dto.weibo_comment_id == "101"
        assert dto.user_uid == "1001"
        assert dto.user_name == "alice"
        assert dto.content == "Great post!"
        assert dto.like_count == 10
        assert dto.created_at is not None
        await client.close()

    async def test_rank_starts_at_1(self):
        """First comment must have rank=1, second rank=2, etc."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([
            _make_comment(101, "first", 10, 1001, "a"),
            _make_comment(102, "second", 5, 1002, "b"),
            _make_comment(103, "third", 1, 1003, "c"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[2].rank == 3
        await client.close()

    async def test_is_hot_true_within_threshold(self):
        """Comments with rank <= 50 must have is_hot=True."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        comments = [_make_comment(i, f"c{i}", i, i, f"u{i}") for i in range(1, 51)]
        resp = _make_response(comments, max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert all(c.is_hot for c in results)
        await client.close()

    async def test_is_hot_false_beyond_threshold(self):
        """Comments with rank > 50 must have is_hot=False (default threshold)."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        comments = [_make_comment(i, f"c{i}", i, i, f"u{i}") for i in range(1, 61)]
        resp = _make_response(comments, max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert results[49].is_hot is True   # rank 50
        assert results[50].is_hot is False  # rank 51
        await client.close()

    async def test_is_hot_custom_threshold(self):
        """Custom hot_threshold must be respected."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti, hot_threshold=5)

        comments = [_make_comment(i, f"c{i}", i, i, f"u{i}") for i in range(1, 11)]
        resp = _make_response(comments, max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert results[4].is_hot is True   # rank 5
        assert results[5].is_hot is False  # rank 6
        await client.close()

    async def test_is_team_member_always_false(self):
        """is_team_member must always be False (set later by analyzer)."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([
            _make_comment(101, "c1", 10, 1001, "a"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert all(c.is_team_member is False for c in results)
        await client.close()

    async def test_empty_response(self):
        """Empty data array must return empty list."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "fake_cookie")

        assert results == []
        await client.close()

    async def test_correct_api_params(self):
        """Must call _get with correct endpoint and params."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([_make_comment(1, "c", 0, 1, "u")], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)) as mock_get:
            await fetcher.fetch_comments("MID123", "cookie_str")

        mock_get.assert_awaited_once()
        call_args = mock_get.call_args
        path = call_args.args[0]
        params = call_args.args[1]
        cookie = call_args.args[2]

        assert path == "/ajax/statuses/buildComments"
        assert params["flow"] == 0
        assert params["is_reload"] == 1
        assert params["id"] == "MID123"
        assert params["count"] == 20
        assert "uid" in params
        assert "max_id" in params
        assert cookie == "cookie_str"
        await client.close()

    async def test_created_at_parsed(self):
        """created_at string from Weibo must be parsed to datetime."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([
            _make_comment(101, "c", 5, 1, "u", "Thu Jun 25 10:00:00 +0800 2025"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "cookie")

        assert isinstance(results[0].created_at, datetime)
        assert results[0].created_at.year == 2025
        assert results[0].created_at.month == 6
        assert results[0].created_at.day == 25
        await client.close()

    async def test_created_at_none_on_unparseable(self):
        """Unparseable created_at must result in None."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([
            _make_comment(101, "c", 5, 1, "u", "not-a-date"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "cookie")

        assert results[0].created_at is None
        await client.close()


# ---------------------------------------------------------------------------
# fetch_comments — multi-page pagination
# ---------------------------------------------------------------------------

class TestFetchCommentsPagination:
    """Tests for multi-page comment fetching."""

    async def test_multi_page_fetch(self):
        """Two pages of comments must be concatenated."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        page1 = _make_response([
            _make_comment(101, "p1c1", 10, 1, "a"),
            _make_comment(102, "p1c2", 5, 2, "b"),
        ], max_id=999)
        page2 = _make_response([
            _make_comment(103, "p2c1", 3, 3, "c"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(side_effect=[page1, page2])):
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)):
                results = await fetcher.fetch_comments("12345", "cookie", max_pages=5)

        assert len(results) == 3
        assert results[0].weibo_comment_id == "101"
        assert results[1].weibo_comment_id == "102"
        assert results[2].weibo_comment_id == "103"
        await client.close()

    async def test_rank_continues_across_pages(self):
        """Rank must continue incrementing across pages."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        page1 = _make_response([
            _make_comment(101, "c1", 1, 1, "a"),
            _make_comment(102, "c2", 2, 2, "b"),
        ], max_id=999)
        page2 = _make_response([
            _make_comment(103, "c3", 3, 3, "c"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(side_effect=[page1, page2])):
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)):
                results = await fetcher.fetch_comments("12345", "cookie", max_pages=5)

        assert results[0].rank == 1
        assert results[1].rank == 2
        assert results[2].rank == 3
        await client.close()

    async def test_max_pages_limit(self):
        """Must stop after max_pages even if more data available."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        # Every page returns data with non-zero max_id
        resp = _make_response([
            _make_comment(101, "c", 1, 1, "a"),
        ], max_id=999)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)):
                results = await fetcher.fetch_comments("12345", "cookie", max_pages=3)

        assert len(results) == 3  # 3 pages × 1 comment each
        await client.close()

    async def test_stops_when_max_id_zero(self):
        """Must stop when max_id=0 in response."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        page1 = _make_response([
            _make_comment(101, "c1", 1, 1, "a"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=page1)) as mock_get:
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)):
                results = await fetcher.fetch_comments("12345", "cookie", max_pages=5)

        assert len(results) == 1
        assert mock_get.await_count == 1  # Only one API call
        await client.close()

    async def test_stops_when_data_empty(self):
        """Must stop when data array is empty."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        page1 = _make_response([
            _make_comment(101, "c1", 1, 1, "a"),
        ], max_id=999)
        page2 = _make_response([], max_id=999)

        with patch.object(client, "_get", new=AsyncMock(side_effect=[page1, page2])):
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)):
                results = await fetcher.fetch_comments("12345", "cookie", max_pages=5)

        assert len(results) == 1
        await client.close()

    async def test_wait_monitor_called_between_pages(self):
        """wait_monitor must be called between page requests."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        page1 = _make_response([_make_comment(101, "c1", 1, 1, "a")], max_id=999)
        page2 = _make_response([_make_comment(102, "c2", 2, 2, "b")], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(side_effect=[page1, page2])):
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)) as mock_wait:
                await fetcher.fetch_comments("12345", "cookie", max_pages=5)

        # wait_monitor called once (between page 1 and page 2, not after page 2)
        assert mock_wait.await_count == 1
        await client.close()

    async def test_wait_monitor_not_called_single_page(self):
        """wait_monitor must NOT be called for a single-page fetch."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([_make_comment(101, "c", 1, 1, "a")], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            with patch.object(anti, "wait_monitor", new=AsyncMock(return_value=1.0)) as mock_wait:
                await fetcher.fetch_comments("12345", "cookie", max_pages=5)

        assert mock_wait.await_count == 0
        await client.close()


# ---------------------------------------------------------------------------
# fetch_comments — DB snapshot saving
# ---------------------------------------------------------------------------

class TestFetchCommentsSnapshots:
    """Tests for saving comment snapshots to the database."""

    async def test_snapshots_saved_with_db_session(self, db_session):
        """When db_session is provided, comments and snapshots must be saved."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti, db_session=db_session)

        resp = _make_response([
            _make_comment(101, "Great!", 10, 1001, "alice"),
            _make_comment(102, "Nice.", 5, 1002, "bob"),
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("MID123", "cookie")

        # Verify Comment records saved
        db_comments = db_session.query(Comment).all()
        assert len(db_comments) == 2
        assert db_comments[0].weibo_comment_id == "101"
        assert db_comments[0].weibo_post_id == "MID123"
        assert db_comments[0].content == "Great!"
        assert db_comments[0].like_count == 10

        # Verify CommentSnapshot records saved
        snapshots = db_session.query(CommentSnapshot).all()
        assert len(snapshots) == 2
        assert snapshots[0].rank == 1
        assert snapshots[0].is_hot is True
        assert snapshots[0].is_team_member is False
        assert snapshots[1].rank == 2
        await client.close()

    async def test_no_snapshots_without_db_session(self):
        """When no db_session, must not crash and must still return DTOs."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        resp = _make_response([_make_comment(101, "c", 1, 1, "u")], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            results = await fetcher.fetch_comments("12345", "cookie")

        assert len(results) == 1
        await client.close()

    async def test_existing_comment_updated(self, db_session):
        """Re-fetching an existing comment must update like_count, not duplicate."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()

        # Pre-populate a comment
        existing = Comment(
            weibo_comment_id="101",
            weibo_post_id="MID123",
            user_uid="1001",
            user_name="alice",
            content="Great!",
            like_count=5,
            fetched_at=datetime.utcnow(),
        )
        db_session.add(existing)
        db_session.commit()

        fetcher = CommentFetcher(client, anti, db_session=db_session)

        resp = _make_response([
            _make_comment(101, "Great!", 15, 1001, "alice"),  # like_count changed
        ], max_id=0)

        with patch.object(client, "_get", new=AsyncMock(return_value=resp)):
            await fetcher.fetch_comments("MID123", "cookie")

        # Should still be 1 Comment (updated), but 1 snapshot
        db_comments = db_session.query(Comment).all()
        assert len(db_comments) == 1
        assert db_comments[0].like_count == 15  # Updated

        snapshots = db_session.query(CommentSnapshot).all()
        assert len(snapshots) == 1
        assert snapshots[0].like_count == 15
        await client.close()


# ---------------------------------------------------------------------------
# fetch_comment_likes — optional deep analysis
# ---------------------------------------------------------------------------

class TestFetchCommentLikes:
    """Tests for the optional fetch_comment_likes method."""

    async def test_returns_dict(self):
        """fetch_comment_likes must return a dict."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        result = await fetcher.fetch_comment_likes("101", "cookie")
        assert isinstance(result, dict)
        await client.close()

    async def test_contains_comment_id(self):
        """Result must contain the queried comment_id."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)

        result = await fetcher.fetch_comment_likes("101", "cookie")
        assert result.get("comment_id") == "101"
        await client.close()


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

class TestConstructor:
    """Tests for CommentFetcher constructor."""

    def test_default_hot_threshold(self):
        """Default hot_threshold must be 50."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)
        assert fetcher.hot_threshold == 50

    def test_custom_hot_threshold(self):
        """Custom hot_threshold must be set."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti, hot_threshold=10)
        assert fetcher.hot_threshold == 10

    def test_stores_client_and_anti_detection(self):
        """Constructor must store client and anti_detection references."""
        client = WeiboHttpClient()
        anti = AntiDetectionEngine()
        fetcher = CommentFetcher(client, anti)
        assert fetcher.client is client
        assert fetcher.anti_detection is anti
