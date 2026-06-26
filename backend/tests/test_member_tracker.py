"""Tests for TeamMemberTracker — TDD test suite."""

from datetime import datetime

from app.models.team_member import TeamMember
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


def make_team_member(
    *,
    weibo_uid: str = "uid1",
    nickname: str = "Alice",
) -> TeamMember:
    """Create a TeamMember with sensible defaults."""
    return TeamMember(
        weibo_uid=weibo_uid,
        nickname=nickname,
    )


# ---------------------------------------------------------------------------
# get_team_uids
# ---------------------------------------------------------------------------

class TestGetTeamUids:
    """Tests for TeamMemberTracker.get_team_uids()."""

    def test_returns_all_team_member_uids_from_db(self, db_session):
        """get_team_uids() returns weibo_uid of all team members."""
        db_session.add(make_team_member(weibo_uid="uid1", nickname="Alice"))
        db_session.add(make_team_member(weibo_uid="uid2", nickname="Bob"))
        db_session.commit()

        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_team_uids()

        assert set(result) == {"uid1", "uid2"}

    def test_no_db_session_returns_empty_list(self):
        """get_team_uids() returns [] when no DB session is provided."""
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_team_uids()

        assert result == []

    def test_empty_db_returns_empty_list(self, db_session):
        """get_team_uids() returns [] when no team members exist."""
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_team_uids()

        assert result == []


# ---------------------------------------------------------------------------
# track_comments
# ---------------------------------------------------------------------------

class TestTrackComments:
    """Tests for TeamMemberTracker.track_comments()."""

    def test_member_with_one_comment_returns_correct_data(self):
        """Member with a single comment gets correct stats and comments list."""
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
        assert entry["total_comments"] == 1
        assert entry["total_likes"] == 50
        assert entry["best_rank"] == 3
        assert entry["in_hot"] is True
        assert len(entry["comments"]) == 1
        assert entry["comments"][0]["comment_id"] == "c100"
        assert entry["comments"][0]["content"] == "hello"
        assert entry["comments"][0]["like_count"] == 50
        assert entry["comments"][0]["rank"] == 3
        assert entry["comments"][0]["is_hot"] is True

    def test_member_with_multiple_comments_tracks_all(self):
        """When member has multiple comments, all are tracked (not just best)."""
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
        assert entry["total_comments"] == 2
        assert entry["total_likes"] == 110  # 30 + 80
        assert entry["best_rank"] == 2  # lowest rank
        assert entry["in_hot"] is True
        assert len(entry["comments"]) == 2
        comment_ids = {c["comment_id"] for c in entry["comments"]}
        assert comment_ids == {"c100", "c200"}

    def test_member_with_no_comment_gets_empty_comments(self):
        """Member with no comment gets empty comments list and zero stats."""
        comments: list[CommentDTO] = []
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        entry = result["uid1"]
        assert entry["comments"] == []
        assert entry["total_comments"] == 0
        assert entry["total_likes"] == 0
        assert entry["best_rank"] is None
        assert entry["in_hot"] is False

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
        assert result["uid1"]["total_comments"] == 1

    def test_empty_comment_list_all_members_zero_stats(self):
        """Empty comment list gives all members zero stats."""
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments([], ["uid1", "uid2", "uid3"])

        for uid in ("uid1", "uid2", "uid3"):
            assert result[uid]["total_comments"] == 0
            assert result[uid]["best_rank"] is None
            assert result[uid]["in_hot"] is False

    def test_comment_content_included_in_result(self):
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

        assert result["uid1"]["comments"][0]["content"] == "This is a test comment with special characters 你好"

    def test_total_likes_sums_all_comments(self):
        """total_likes is the sum of like_count across all member's comments."""
        comments = [
            make_comment(id=1, user_uid="uid1", like_count=10, rank=1),
            make_comment(id=2, user_uid="uid1", weibo_comment_id="c2", like_count=25, rank=3),
            make_comment(id=3, user_uid="uid1", weibo_comment_id="c3", like_count=5, rank=7),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["total_likes"] == 40

    def test_best_rank_is_lowest_rank_number(self):
        """best_rank is the lowest rank number among the member's comments."""
        comments = [
            make_comment(id=1, user_uid="uid1", like_count=10, rank=8),
            make_comment(id=2, user_uid="uid1", weibo_comment_id="c2", like_count=5, rank=3),
            make_comment(id=3, user_uid="uid1", weibo_comment_id="c3", like_count=20, rank=15),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["best_rank"] == 3

    def test_in_hot_true_if_any_comment_is_hot(self):
        """in_hot is True if any comment has is_hot=True."""
        comments = [
            make_comment(id=1, user_uid="uid1", like_count=10, rank=1, is_hot=False),
            make_comment(id=2, user_uid="uid1", weibo_comment_id="c2", like_count=5, rank=3, is_hot=True),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["in_hot"] is True

    def test_in_hot_false_if_no_comment_is_hot(self):
        """in_hot is False if no comment has is_hot=True."""
        comments = [
            make_comment(id=1, user_uid="uid1", like_count=10, rank=1, is_hot=False),
            make_comment(id=2, user_uid="uid1", weibo_comment_id="c2", like_count=5, rank=3, is_hot=False),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["in_hot"] is False

    def test_nickname_from_team_member_table(self, db_session):
        """nickname comes from TeamMember table, not from the comment."""
        db_session.add(make_team_member(weibo_uid="uid1", nickname="AliceFromDB"))
        db_session.commit()

        comments = [
            make_comment(user_uid="uid1", user_name="AliceFromComment", rank=1),
        ]
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["nickname"] == "AliceFromDB"

    def test_nickname_none_when_no_db_session(self):
        """nickname is None when no DB session is available."""
        comments = [
            make_comment(user_uid="uid1", user_name="Alice", rank=1),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["nickname"] is None

    def test_created_at_included_in_comment(self):
        """created_at is included in each comment dict as ISO string."""
        ts = datetime(2024, 1, 15, 10, 30, 0)
        comments = [
            make_comment(user_uid="uid1", rank=1, created_at=ts),
        ]
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.track_comments(comments, ["uid1"])

        assert result["uid1"]["comments"][0]["created_at"] == "2024-01-15T10:30:00"


# ---------------------------------------------------------------------------
# get_member_grid_data
# ---------------------------------------------------------------------------

class TestGetMemberGridData:
    """Tests for TeamMemberTracker.get_member_grid_data()."""

    def test_returns_exactly_n_entries_no_padding(self):
        """Grid returns exactly len(team_uids) entries — no padding."""
        tracker = TeamMemberTracker(db_session=None)
        tracked: dict[str, dict] = {}
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert len(result) == 1

    def test_returns_exactly_n_entries_for_multiple_members(self):
        """Grid returns exactly len(team_uids) entries for multiple members."""
        tracker = TeamMemberTracker(db_session=None)
        tracked: dict[str, dict] = {}
        result = tracker.get_member_grid_data(["uid1", "uid2", "uid3"], tracked)

        assert len(result) == 3

    def test_more_than_20_members_not_truncated(self):
        """More than 20 members → all are returned (no truncation)."""
        team_uids = [f"uid{i}" for i in range(25)]
        tracked: dict[str, dict] = {}
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(team_uids, tracked)

        assert len(result) == 25
        for i, card in enumerate(result):
            assert card["uid"] == f"uid{i}"

    def test_member_with_comment_has_correct_data(self):
        """Member with a comment shows correct stats in grid."""
        tracked = {
            "uid1": {
                "nickname": "Alice",
                "comments": [{"comment_id": "c100", "content": "hello", "like_count": 42, "rank": 5, "is_hot": True, "created_at": None}],
                "total_comments": 1,
                "total_likes": 42,
                "best_rank": 5,
                "in_hot": True,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        card = result[0]
        assert card["uid"] == "uid1"
        assert card["total_comments"] == 1
        assert card["total_likes"] == 42
        assert card["best_rank"] == 5
        assert card["in_hot"] is True
        assert len(card["comments"]) == 1

    def test_member_without_comment_has_zero_stats(self):
        """Member without comment shows zero/None stats in grid."""
        tracked = {
            "uid1": {
                "nickname": None,
                "comments": [],
                "total_comments": 0,
                "total_likes": 0,
                "best_rank": None,
                "in_hot": False,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        card = result[0]
        assert card["total_comments"] == 0
        assert card["total_likes"] == 0
        assert card["best_rank"] is None
        assert card["in_hot"] is False
        assert card["comments"] == []

    def test_avatar_url_always_none(self, db_session):
        """avatar_url is always None (TeamMember has no avatar)."""
        db_session.add(make_team_member(weibo_uid="uid1", nickname="Alice"))
        db_session.commit()

        tracked = {
            "uid1": {
                "nickname": "Alice",
                "comments": [],
                "total_comments": 0,
                "total_likes": 0,
                "best_rank": None,
                "in_hot": False,
            }
        }
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert result[0]["avatar_url"] is None

    def test_comments_included_in_grid(self):
        """Grid card includes the full comments list from tracked data."""
        comment_entry = {"comment_id": "c1", "content": "hi", "like_count": 10, "rank": 1, "is_hot": True, "created_at": None}
        tracked = {
            "uid1": {
                "nickname": "Alice",
                "comments": [comment_entry],
                "total_comments": 1,
                "total_likes": 10,
                "best_rank": 1,
                "in_hot": True,
            }
        }
        tracker = TeamMemberTracker(db_session=None)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert result[0]["comments"] == [comment_entry]

    def test_nickname_from_team_member_table_in_grid(self, db_session):
        """Grid card nickname comes from TeamMember table."""
        db_session.add(make_team_member(weibo_uid="uid1", nickname="AliceFromDB"))
        db_session.commit()

        tracked = {
            "uid1": {
                "nickname": None,
                "comments": [],
                "total_comments": 0,
                "total_likes": 0,
                "best_rank": None,
                "in_hot": False,
            }
        }
        tracker = TeamMemberTracker(db_session=db_session)
        result = tracker.get_member_grid_data(["uid1"], tracked)

        assert result[0]["nickname"] == "AliceFromDB"


# ---------------------------------------------------------------------------
# _get_member_info
# ---------------------------------------------------------------------------

class TestGetMemberInfo:
    """Tests for TeamMemberTracker._get_member_info()."""

    def test_returns_member_info_when_found(self, db_session):
        """_get_member_info returns nickname for existing team member."""
        db_session.add(make_team_member(
            weibo_uid="uid1",
            nickname="Alice",
        ))
        db_session.commit()

        tracker = TeamMemberTracker(db_session=db_session)
        info = tracker._get_member_info("uid1")

        assert info["nickname"] == "Alice"
        assert info["avatar_url"] is None
        assert info["status"] == "active"

    def test_returns_none_values_when_not_found(self, db_session):
        """_get_member_info returns None/unknown for non-existent member."""
        tracker = TeamMemberTracker(db_session=db_session)
        info = tracker._get_member_info("nonexistent")

        assert info["nickname"] is None
        assert info["avatar_url"] is None
        assert info["status"] == "unknown"

    def test_returns_none_values_when_no_db_session(self):
        """_get_member_info returns None/unknown when no DB session."""
        tracker = TeamMemberTracker(db_session=None)
        info = tracker._get_member_info("uid1")

        assert info["nickname"] is None
        assert info["avatar_url"] is None
        assert info["status"] == "unknown"
