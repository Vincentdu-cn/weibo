"""Tests for TeamMemberTracker — TDD test suite (Task 10)."""

from datetime import datetime

from app.models.account import Account
from app.schemas.comment import CommentDTO
from app.services.member_tracker import TeamMemberTracker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_comment(
    *,
    id: int = 1,
    weibo_comment_id: str = "c100",
    user_uid: str = "uid1",
    user_name: str = "Alice",
    content: str = "test content",
    like_count: int = 10,
    rank: int = 1,
    is_hot: bool = False,
    is_team_member: bool = True,
    created_at: datetime | None = None,
) -> CommentDTO:
    """Create a CommentDTO with sensible defaults."""
    return CommentDTO(
        id=id,
        weibo_comment_id=weibo_comment_id,
        user_uid=user_uid,
        user_name=user_name,
        content=content,
        like_count=like_count,
        rank=rank,
        is_hot=is_hot,
        is_team_member=is_team_member,
        created_at=created_at,
    )


def make_account(
    *,
    weibo_uid: str = "uid1",
    nickname: str = "Alice",
    status: str = "active",
    avatar_url: str = "http://example.com/avatar.png",
) -> Account:
    """Create an Account with sensible defaults."""
    return Account(
        weibo_uid=weibo_uid,
        nickname=nickname,
        status=status,
        avatar_url=avatar_url,
    )


# ---------------------------------------------------------------------------
# get_team_uids
# ---------------------------------------------------------------------------

class TestGetTeamUids:
    """Tests for TeamMemberTracker.get_team_uids()."""

    def test_returns_active_account_uids_from_db(self, db_session):
        """get_team_uids() returns weibo_uid of all active accounts."""
        db_session.add(make_account(weibo_uid="uid1", nickname="Alice", status="active"))
        db_session.add(make_account(weibo_uid="uid2", nickname="Bob", status="active"))
        db_session.commit()

        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_team_uids()

        assert set(result) == {"uid1", "uid2"}

    def test_no_db_session_returns_empty_list(self):
        """get_team_uids() returns [] when no DB session is provided."""
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_team_uids()

        assert result == []

    def test_only_returns_active_accounts(self, db_session):
        """get_team_uids() excludes expired and disabled accounts."""
        db_session.add(make_account(weibo_uid="uid1", nickname="Alice", status="active"))
        db_session.add(make_account(weibo_uid="uid2", nickname="Bob", status="expired"))
        db_session.add(make_account(weibo_uid="uid3", nickname="Carol", status="disabled"))
        db_session.commit()

        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_team_uids()

        assert result == ["uid1"]

    def test_empty_db_returns_empty_list(self, db_session):
        """get_team_uids() returns [] when no accounts exist."""
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_team_uids()

        assert result == []


# ---------------------------------------------------------------------------
# track_comments
# ---------------------------------------------------------------------------

class TestTrackComments:
    """Tests for TeamMemberTracker.track_comments()."""

    def test_member_with_one_comment_returns_correct_data(self):
        """Member with a single comment gets correct rank, like_count, is_hot."""
        comments = [
            make_comment(
                user_uid="uid1",
                user_name="Alice",
                weibo_comment_id="c100",
                content="hello",
                like_count=50,
                rank=3,
                is_hot=True,
            ),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        entry = result["uid1"]
        assert entry["nickname"] == "Alice"
        assert entry["comment_id"] == "c100"
        assert entry["rank"] == 3
        assert entry["like_count"] == 50
        assert entry["is_hot"] is True
        assert entry["content"] == "hello"
        assert entry["status"] == "has_comment"

    def test_member_with_multiple_comments_takes_best_rank(self):
        """When member has multiple comments, the one with lowest rank is kept."""
        comments = [
            make_comment(
                id=1,
                user_uid="uid1",
                user_name="Alice",
                weibo_comment_id="c100",
                content="first comment",
                like_count=30,
                rank=5,
                is_hot=True,
            ),
            make_comment(
                id=2,
                user_uid="uid1",
                user_name="Alice",
                weibo_comment_id="c200",
                content="second comment",
                like_count=80,
                rank=2,
                is_hot=True,
            ),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        entry = result["uid1"]
        assert entry["comment_id"] == "c200"
        assert entry["rank"] == 2
        assert entry["like_count"] == 80
        assert entry["content"] == "second comment"

    def test_member_with_no_comment_gets_no_comment_status(self):
        """Member with no comment gets status='no_comment' and None values."""
        comments: list[CommentDTO] = []
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        entry = result["uid1"]
        assert entry["nickname"] is None
        assert entry["comment_id"] is None
        assert entry["rank"] is None
        assert entry["like_count"] is None
        assert entry["is_hot"] is False
        assert entry["content"] is None
        assert entry["status"] == "no_comment"

    def test_non_team_comments_are_ignored(self):
        """Comments from non-team UIDs do not appear in the result."""
        comments = [
            make_comment(user_uid="uid1", user_name="Alice", rank=1),
            make_comment(
                id=2,
                user_uid="stranger",
                user_name="Stranger",
                weibo_comment_id="c999",
                rank=2,
            ),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert "uid1" in result
        assert "stranger" not in result
        assert result["uid1"]["status"] == "has_comment"

    def test_empty_comment_list_all_members_no_comment(self):
        """Empty comment list gives all members no_comment status."""
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments([], ["uid1", "uid2", "uid3"])

        for uid in ("uid1", "uid2", "uid3"):
            assert result[uid]["status"] == "no_comment"
            assert result[uid]["rank"] is None

    def test_member_comment_content_included_in_result(self):
        """The comment content is included in the tracking result."""
        comments = [
            make_comment(
                user_uid="uid1",
                user_name="Alice",
                content="This is a test comment with special characters 你好",
                rank=1,
            ),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["content"] == "This is a test comment with special characters 你好"


# ---------------------------------------------------------------------------
# get_member_grid_data
# ---------------------------------------------------------------------------

class TestGetMemberGridData:
    """Tests for TeamMemberTracker.get_member_grid_data()."""

    def test_returns_exactly_20_entries(self):
        """Grid always returns 20 entries."""
        tracker = TeamMemberTracker(db_session=None)
        tracked: dict[str, dict] = {}
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert len(result) == 20

    def test_member_with_comment_has_correct_data(self):
        """Member with a comment shows correct rank/like_count/is_hot in grid."""
        tracked = {
            "uid1": {
                "nickname": "Alice",
                "comment_id": "c100",
                "rank": 5,
                "like_count": 42,
                "is_hot": True,
                "content": "hello",
                "status": "has_comment",
                "comment_count": 1,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        card = result[0]
        assert card["uid"] == "uid1"
        assert card["current_rank"] == 5
        assert card["like_count"] == 42
        assert card["is_hot"] is True

    def test_member_without_comment_has_none_rank_and_false_is_hot(self):
        """Member without comment shows rank=None, is_hot=False."""
        tracked = {
            "uid1": {
                "nickname": None,
                "comment_id": None,
                "rank": None,
                "like_count": None,
                "is_hot": False,
                "content": None,
                "status": "no_comment",
                "comment_count": 0,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        card = result[0]
        assert card["current_rank"] is None
        assert card["is_hot"] is False
        assert card["like_count"] is None

    def test_fewer_than_20_members_padded_with_empty_slots(self):
        """Fewer than 20 members → remaining slots are empty dicts."""
        tracked: dict[str, dict] = {}
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        # First entry is the member
        assert result[0]["uid"] == "uid1"
        # Entries 1..19 are empty slots
        for slot in result[1:]:
            assert slot["uid"] is None
            assert slot["nickname"] is None
            assert slot["current_rank"] is None

    def test_more_than_20_members_truncated(self):
        """More than 20 members → only first 20 are returned."""
        team_uids = [f"uid{i}" for i in range(25)]
        tracked: dict[str, dict] = {}
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(team_uids, tracked)

        assert len(result) == 20
        # First 20 UIDs should be present
        for i, card in enumerate(result):
            assert card["uid"] == f"uid{i}"

    def test_avatar_url_from_account_included(self, db_session):
        """avatar_url in grid card comes from the Account model."""
        db_session.add(make_account(
            weibo_uid="uid1",
            nickname="Alice",
            avatar_url="http://img.weibo.com/avatar/alice.jpg",
        ))
        db_session.commit()

        tracked = {
            "uid1": {
                "nickname": "Alice",
                "comment_id": "c1",
                "rank": 1,
                "like_count": 10,
                "is_hot": True,
                "content": "hi",
                "status": "has_comment",
                "comment_count": 1,
            }
        }
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert result[0]["avatar_url"] == "http://img.weibo.com/avatar/alice.jpg"

    def test_online_status_derived_from_account_status(self, db_session):
        """online_status is 'online' for active accounts, 'offline' otherwise."""
        db_session.add(make_account(weibo_uid="uid1", nickname="Alice", status="active"))
        db_session.add(make_account(weibo_uid="uid2", nickname="Bob", status="expired"))
        db_session.add(make_account(weibo_uid="uid3", nickname="Carol", status="disabled"))
        db_session.commit()

        tracked: dict[str, dict] = {}
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_member_grid_data(["uid1", "uid2", "uid3"], tracked)

        assert result[0]["online_status"] == "online"
        assert result[1]["online_status"] == "offline"
        assert result[2]["online_status"] == "offline"

    def test_comment_count_zero_for_no_comment(self):
        """comment_count is 0 for members with no_comment status."""
        tracked = {
            "uid1": {
                "nickname": None,
                "comment_id": None,
                "rank": None,
                "like_count": None,
                "is_hot": False,
                "content": None,
                "status": "no_comment",
                "comment_count": 0,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert result[0]["comment_count"] == 0

    def test_comment_count_at_least_one_for_has_comment(self):
        """comment_count is >= 1 for members with has_comment status."""
        tracked = {
            "uid1": {
                "nickname": "Alice",
                "comment_id": "c1",
                "rank": 1,
                "like_count": 10,
                "is_hot": True,
                "content": "hi",
                "status": "has_comment",
                "comment_count": 3,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert result[0]["comment_count"] >= 1


# ---------------------------------------------------------------------------
# _get_account_info
# ---------------------------------------------------------------------------

class TestGetAccountInfo:
    """Tests for TeamMemberTracker._get_account_info()."""

    def test_returns_account_info_when_found(self, db_session):
        """_get_account_info returns nickname, avatar_url, status for existing account."""
        db_session.add(make_account(
            weibo_uid="uid1",
            nickname="Alice",
            status="active",
            avatar_url="http://img.weibo.com/a.jpg",
        ))
        db_session.commit()

        tracker = TeamMemberTracker(db_session=db_session)
        info = tracker._get_account_info("uid1")

        assert info["nickname"] == "Alice"
        assert info["avatar_url"] == "http://img.weibo.com/a.jpg"
        assert info["status"] == "active"

    def test_returns_none_values_when_not_found(self, db_session):
        """_get_account_info returns None/unknown for non-existent account."""
        tracker = TeamMemberTracker(db_session=db_session)
        info = tracker._get_account_info("nonexistent")

        assert info["nickname"] is None
        assert info["avatar_url"] is None
        assert info["status"] == "unknown"

    def test_returns_none_values_when_no_db_session(self):
        """_get_account_info returns None/unknown when no DB session."""
        tracker = TeamMemberTracker(db_session=None)
        info = tracker._get_account_info("uid1")

        assert info["nickname"] is None
        assert info["avatar_url"] is None
        assert info["status"] == "unknown"
