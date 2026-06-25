"""TDD tests for HotCommentAnalyzer (Task 9)."""

from datetime import datetime

from app.schemas.comment import CommentDTO
from app.services.hot_analyzer import HotCommentAnalyzer, HotConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comment(
    *,
    id: int = 0,
    weibo_comment_id: str = "",
    user_uid: str = "uid_0",
    user_name: str = "user_0",
    content: str = "comment",
    like_count: int = 0,
    rank: int = 0,
    is_hot: bool = False,
    is_team_member: bool = False,
    created_at: datetime | None = None,
) -> CommentDTO:
    """Build a CommentDTO with sensible defaults."""
    return CommentDTO(
        id=id,
        weibo_comment_id=weibo_comment_id or f"wb_{id}",
        user_uid=user_uid,
        user_name=user_name,
        content=content,
        like_count=like_count,
        rank=rank,
        is_hot=is_hot,
        is_team_member=is_team_member,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# analyze() — basic ranking
# ---------------------------------------------------------------------------

class TestAnalyzeBasicRanking:
    """Test case 1: 3 comments sorted by like_count descending, rank 1/2/3."""

    def test_three_comments_sorted_by_like_count_desc(self):
        comments = [
            _make_comment(id=1, user_uid="a", like_count=5),
            _make_comment(id=2, user_uid="b", like_count=20),
            _make_comment(id=3, user_uid="c", like_count=10),
        ]
        analyzer = HotCommentAnalyzer()
        result = analyzer.analyze(comments, team_uids=[])

        assert len(result) == 3
        assert result[0].like_count == 20
        assert result[1].like_count == 10
        assert result[2].like_count == 5
        assert result[0].rank == 1
        assert result[1].rank == 2
        assert result[2].rank == 3


# ---------------------------------------------------------------------------
# analyze() — is_hot threshold
# ---------------------------------------------------------------------------

class TestAnalyzeHotThreshold:
    """Test case 2: with top_n=2, ranks 1-2 are hot, 3+ are not."""

    def test_top_n_2_marks_only_first_two_hot(self):
        comments = [
            _make_comment(id=1, user_uid="a", like_count=30),
            _make_comment(id=2, user_uid="b", like_count=20),
            _make_comment(id=3, user_uid="c", like_count=10),
        ]
        config = HotConfig(top_n=2)
        analyzer = HotCommentAnalyzer(config=config)
        result = analyzer.analyze(comments, team_uids=[])

        assert result[0].is_hot is True
        assert result[1].is_hot is True
        assert result[2].is_hot is False


# ---------------------------------------------------------------------------
# analyze() — team member flagging
# ---------------------------------------------------------------------------

class TestAnalyzeTeamMemberFlagging:
    """Test case 3: comments from team UIDs get is_team_member=True."""

    def test_team_uids_flagged_correctly(self):
        comments = [
            _make_comment(id=1, user_uid="team_a", like_count=10),
            _make_comment(id=2, user_uid="team_b", like_count=8),
            _make_comment(id=3, user_uid="outsider", like_count=15),
        ]
        analyzer = HotCommentAnalyzer()
        result = analyzer.analyze(comments, team_uids=["team_a", "team_b"])

        # outsider has most likes → rank 1
        assert result[0].user_uid == "outsider"
        assert result[0].is_team_member is False

        # team members flagged
        team_comments = [c for c in result if c.user_uid in ("team_a", "team_b")]
        assert len(team_comments) == 2
        for c in team_comments:
            assert c.is_team_member is True


# ---------------------------------------------------------------------------
# analyze() — empty comment list
# ---------------------------------------------------------------------------

class TestAnalyzeEmptyList:
    """Test case 4: empty comment list returns empty list."""

    def test_empty_list_returns_empty(self):
        analyzer = HotCommentAnalyzer()
        result = analyzer.analyze([], team_uids=["a", "b"])
        assert result == []


# ---------------------------------------------------------------------------
# analyze() — single comment
# ---------------------------------------------------------------------------

class TestAnalyzeSingleComment:
    """Test case 5: single comment gets rank=1, is_hot=True (top_n >= 1)."""

    def test_single_comment_rank_1_hot(self):
        comment = _make_comment(id=1, user_uid="a", like_count=5)
        analyzer = HotCommentAnalyzer()
        result = analyzer.analyze([comment], team_uids=[])

        assert len(result) == 1
        assert result[0].rank == 1
        assert result[0].is_hot is True


# ---------------------------------------------------------------------------
# analyze() — custom ranking_field
# ---------------------------------------------------------------------------

class TestAnalyzeCustomRankingField:
    """Test case 6: sort by a custom field (e.g., id) instead of like_count."""

    def test_custom_ranking_field_by_id(self):
        comments = [
            _make_comment(id=3, user_uid="c", like_count=100),
            _make_comment(id=1, user_uid="a", like_count=1),
            _make_comment(id=2, user_uid="b", like_count=50),
        ]
        config = HotConfig(ranking_field="id")
        analyzer = HotCommentAnalyzer(config=config)
        result = analyzer.analyze(comments, team_uids=[])

        # Sorted by id descending: 3, 2, 1
        assert result[0].id == 3
        assert result[1].id == 2
        assert result[2].id == 1
        assert result[0].rank == 1
        assert result[1].rank == 2
        assert result[2].rank == 3


# ---------------------------------------------------------------------------
# get_team_hot_status() — best-ranked comment selected
# ---------------------------------------------------------------------------

class TestGetTeamHotStatusBestRank:
    """Test case 7: member with best-ranked comment selected when multiple exist."""

    def test_multiple_comments_takes_best_rank(self):
        comments = [
            _make_comment(id=1, user_uid="team_a", user_name="Alice", like_count=50),
            _make_comment(id=2, user_uid="team_a", user_name="Alice", like_count=5),
            _make_comment(id=3, user_uid="team_b", user_name="Bob", like_count=30),
        ]
        analyzer = HotCommentAnalyzer()
        analyzed = analyzer.analyze(comments, team_uids=["team_a", "team_b"])
        statuses = analyzer.get_team_hot_status(analyzed, team_uids=["team_a", "team_b"])

        # Alice's best: like_count=50 → rank 1
        alice_status = next(s for s in statuses if s["uid"] == "team_a")
        assert alice_status["nickname"] == "Alice"
        assert alice_status["rank"] == 1
        assert alice_status["like_count"] == 50
        assert alice_status["is_hot"] is True
        assert alice_status["comment_id"] is not None

        # Bob: like_count=30 → rank 2
        bob_status = next(s for s in statuses if s["uid"] == "team_b")
        assert bob_status["rank"] == 2
        assert bob_status["like_count"] == 30


# ---------------------------------------------------------------------------
# get_team_hot_status() — member with no comment
# ---------------------------------------------------------------------------

class TestGetTeamHotStatusNoComment:
    """Test case 8: member with no comment gets None values."""

    def test_member_without_comment_gets_none_status(self):
        comments = [
            _make_comment(id=1, user_uid="team_a", user_name="Alice", like_count=50),
        ]
        analyzer = HotCommentAnalyzer()
        analyzed = analyzer.analyze(comments, team_uids=["team_a", "team_b"])
        statuses = analyzer.get_team_hot_status(analyzed, team_uids=["team_a", "team_b"])

        bob_status = next(s for s in statuses if s["uid"] == "team_b")
        assert bob_status["nickname"] is None
        assert bob_status["comment_id"] is None
        assert bob_status["rank"] is None
        assert bob_status["like_count"] is None
        assert bob_status["is_hot"] is False


# ---------------------------------------------------------------------------
# get_team_hot_status() — all members have comments
# ---------------------------------------------------------------------------

class TestGetTeamHotStatusAllHaveComments:
    """Test case 9: all members have comments, returns correct ranks."""

    def test_all_members_have_comments_correct_ranks(self):
        comments = [
            _make_comment(id=1, user_uid="t1", user_name="One", like_count=100),
            _make_comment(id=2, user_uid="t2", user_name="Two", like_count=50),
            _make_comment(id=3, user_uid="t3", user_name="Three", like_count=10),
        ]
        analyzer = HotCommentAnalyzer()
        analyzed = analyzer.analyze(comments, team_uids=["t1", "t2", "t3"])
        statuses = analyzer.get_team_hot_status(analyzed, team_uids=["t1", "t2", "t3"])

        assert len(statuses) == 3
        status_by_uid = {s["uid"]: s for s in statuses}
        assert status_by_uid["t1"]["rank"] == 1
        assert status_by_uid["t2"]["rank"] == 2
        assert status_by_uid["t3"]["rank"] == 3
        # All should be hot (top_n=50 default)
        for s in statuses:
            assert s["is_hot"] is True


# ---------------------------------------------------------------------------
# detect_changes() — member drops out of hot
# ---------------------------------------------------------------------------

class TestDetectChangesDropout:
    """Test case 10: member was hot, now not hot → dropped_out."""

    def test_member_drops_out_of_hot(self):
        prev = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
        ]
        curr = [
            {"uid": "a", "nickname": "A", "comment_id": "c2", "rank": 60, "like_count": 5, "is_hot": False},
        ]
        analyzer = HotCommentAnalyzer()
        changes = analyzer.detect_changes(prev, curr)

        assert "a" in changes["dropped_out"]
        assert changes["entered_hot"] == []
        assert changes["rank_changed"] == []


# ---------------------------------------------------------------------------
# detect_changes() — member enters hot
# ---------------------------------------------------------------------------

class TestDetectChangesEnterHot:
    """Test case 11: member was not hot, now hot → entered_hot."""

    def test_member_enters_hot(self):
        prev = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 60, "like_count": 5, "is_hot": False},
        ]
        curr = [
            {"uid": "a", "nickname": "A", "comment_id": "c2", "rank": 1, "like_count": 100, "is_hot": True},
        ]
        analyzer = HotCommentAnalyzer()
        changes = analyzer.detect_changes(prev, curr)

        assert "a" in changes["entered_hot"]
        assert changes["dropped_out"] == []
        assert changes["rank_changed"] == []


# ---------------------------------------------------------------------------
# detect_changes() — rank changed (still hot)
# ---------------------------------------------------------------------------

class TestDetectChangesRankChanged:
    """Test case 12: member rank changes, still hot → rank_changed."""

    def test_rank_changed_still_hot(self):
        prev = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 3, "like_count": 50, "is_hot": True},
        ]
        curr = [
            {"uid": "a", "nickname": "A", "comment_id": "c2", "rank": 5, "like_count": 40, "is_hot": True},
        ]
        analyzer = HotCommentAnalyzer()
        changes = analyzer.detect_changes(prev, curr)

        assert len(changes["rank_changed"]) == 1
        entry = changes["rank_changed"][0]
        assert entry["uid"] == "a"
        assert entry["prev_rank"] == 3
        assert entry["curr_rank"] == 5
        assert changes["entered_hot"] == []
        assert changes["dropped_out"] == []


# ---------------------------------------------------------------------------
# detect_changes() — no changes
# ---------------------------------------------------------------------------

class TestDetectChangesNoChanges:
    """Test case 13: no changes → all lists empty."""

    def test_no_changes_all_empty(self):
        prev = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
            {"uid": "b", "nickname": "B", "comment_id": "c2", "rank": 2, "like_count": 50, "is_hot": True},
        ]
        curr = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
            {"uid": "b", "nickname": "B", "comment_id": "c2", "rank": 2, "like_count": 50, "is_hot": True},
        ]
        analyzer = HotCommentAnalyzer()
        changes = analyzer.detect_changes(prev, curr)

        assert changes["entered_hot"] == []
        assert changes["dropped_out"] == []
        assert changes["rank_changed"] == []


# ---------------------------------------------------------------------------
# detect_changes() — new member appears
# ---------------------------------------------------------------------------

class TestDetectChangesNewMember:
    """Test case 14: new member appears in curr_status (not in prev) → entered_hot if hot."""

    def test_new_member_appears_hot(self):
        prev = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
        ]
        curr = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
            {"uid": "b", "nickname": "B", "comment_id": "c2", "rank": 2, "like_count": 50, "is_hot": True},
        ]
        analyzer = HotCommentAnalyzer()
        changes = analyzer.detect_changes(prev, curr)

        assert "b" in changes["entered_hot"]
        assert changes["dropped_out"] == []
        assert changes["rank_changed"] == []


# ---------------------------------------------------------------------------
# detect_changes() — member disappears
# ---------------------------------------------------------------------------

class TestDetectChangesMemberDisappears:
    """Test case 15: member disappears from curr_status (was in prev) → dropped_out."""

    def test_member_disappears_from_curr(self):
        prev = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
            {"uid": "b", "nickname": "B", "comment_id": "c2", "rank": 2, "like_count": 50, "is_hot": True},
        ]
        curr = [
            {"uid": "a", "nickname": "A", "comment_id": "c1", "rank": 1, "like_count": 100, "is_hot": True},
        ]
        analyzer = HotCommentAnalyzer()
        changes = analyzer.detect_changes(prev, curr)

        assert "b" in changes["dropped_out"]
        assert changes["entered_hot"] == []
        assert changes["rank_changed"] == []


# ---------------------------------------------------------------------------
# HotConfig defaults
# ---------------------------------------------------------------------------

class TestHotConfigDefaults:
    """Verify HotConfig dataclass defaults."""

    def test_default_config_values(self):
        config = HotConfig()
        assert config.top_n == 50
        assert config.min_likes == 0
        assert config.ranking_field == "like_count"
        assert config.flow_param == 0

    def test_analyzer_uses_default_config_when_none(self):
        analyzer = HotCommentAnalyzer()
        assert analyzer.config.top_n == 50
        assert analyzer.config.ranking_field == "like_count"

    def test_min_likes_filter_applied(self):
        """Comments below min_likes are excluded from ranking."""
        comments = [
            _make_comment(id=1, user_uid="a", like_count=0),
            _make_comment(id=2, user_uid="b", like_count=10),
            _make_comment(id=3, user_uid="c", like_count=20),
        ]
        config = HotConfig(min_likes=5)
        analyzer = HotCommentAnalyzer(config=config)
        result = analyzer.analyze(comments, team_uids=[])

        # Only comments with like_count >= 5 are ranked
        assert len(result) == 2
        assert result[0].like_count == 20
        assert result[0].rank == 1
        assert result[1].like_count == 10
        assert result[1].rank == 2
