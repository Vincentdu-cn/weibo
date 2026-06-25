"""Tests for Pydantic schemas: serialization, deserialization, defaults."""

from datetime import datetime

from app.schemas import AccountDTO, AlertDTO, CommentDTO, StatsDTO, WSMessage


class TestCommentDTO:
    """Test CommentDTO serialization/deserialization."""

    def test_create_with_all_fields(self):
        """Create CommentDTO with all fields populated."""
        now = datetime(2025, 6, 25, 12, 0, 0)
        comment = CommentDTO(
            id=1,
            weibo_comment_id="wb_12345",
            user_uid="uid_abc",
            user_name="TestUser",
            content="This is a comment",
            like_count=42,
            rank=1,
            is_hot=True,
            is_team_member=False,
            created_at=now,
        )
        assert comment.id == 1
        assert comment.weibo_comment_id == "wb_12345"
        assert comment.user_uid == "uid_abc"
        assert comment.user_name == "TestUser"
        assert comment.content == "This is a comment"
        assert comment.like_count == 42
        assert comment.rank == 1
        assert comment.is_hot is True
        assert comment.is_team_member is False
        assert comment.created_at == now

    def test_created_at_optional(self):
        """created_at should default to None when not provided."""
        comment = CommentDTO(
            id=1,
            weibo_comment_id="wb_1",
            user_uid="uid_1",
            user_name="User",
            content="Comment",
            like_count=0,
            rank=1,
            is_hot=False,
            is_team_member=False,
        )
        assert comment.created_at is None

    def test_serialize_and_deserialize(self):
        """model_dump() then reconstruct from dict should preserve all values."""
        original = CommentDTO(
            id=99,
            weibo_comment_id="wb_999",
            user_uid="uid_999",
            user_name="SerializedUser",
            content="Round trip content",
            like_count=7,
            rank=3,
            is_hot=True,
            is_team_member=True,
            created_at=datetime(2025, 1, 1, 8, 30, 0),
        )
        dumped = original.model_dump()
        recreated = CommentDTO(**dumped)

        assert recreated.id == original.id
        assert recreated.weibo_comment_id == original.weibo_comment_id
        assert recreated.user_uid == original.user_uid
        assert recreated.user_name == original.user_name
        assert recreated.content == original.content
        assert recreated.like_count == original.like_count
        assert recreated.rank == original.rank
        assert recreated.is_hot == original.is_hot
        assert recreated.is_team_member == original.is_team_member
        assert recreated.created_at == original.created_at


class TestAccountDTO:
    """Test AccountDTO serialization/deserialization."""

    def test_create_and_serialize(self):
        """Create AccountDTO, serialize, deserialize, verify fields."""
        account = AccountDTO(
            id=1,
            weibo_uid="1234567890",
            nickname="WeiboUser",
            status="active",
            avatar_url="https://example.com/avatar.jpg",
        )
        dumped = account.model_dump()
        recreated = AccountDTO(**dumped)

        assert recreated.id == 1
        assert recreated.weibo_uid == "1234567890"
        assert recreated.nickname == "WeiboUser"
        assert recreated.status == "active"
        assert recreated.avatar_url == "https://example.com/avatar.jpg"

    def test_avatar_url_defaults_none(self):
        """avatar_url should default to None."""
        account = AccountDTO(
            id=1,
            weibo_uid="123",
            nickname="NoAvatar",
            status="inactive",
        )
        assert account.avatar_url is None


class TestAlertDTO:
    """Test AlertDTO serialization/deserialization and defaults."""

    def test_create_with_all_fields(self):
        """Create AlertDTO with all fields populated."""
        alert = AlertDTO(
            id=1,
            account_uid="uid_123",
            comment_id=42,
            alert_type="negative_sentiment",
            message="Negative comment detected",
            status="pending",
            comment_input="Please respond",
            selected_account_ids=[1, 2, 3],
        )
        assert alert.id == 1
        assert alert.account_uid == "uid_123"
        assert alert.comment_id == 42
        assert alert.alert_type == "negative_sentiment"
        assert alert.message == "Negative comment detected"
        assert alert.status == "pending"
        assert alert.comment_input == "Please respond"
        assert alert.selected_account_ids == [1, 2, 3]

    def test_optional_fields_default(self):
        """Optional fields should have correct defaults."""
        alert = AlertDTO(
            id=1,
            alert_type="info",
            message="Test alert",
            status="active",
        )
        assert alert.account_uid is None
        assert alert.comment_id is None
        assert alert.comment_input is None
        assert alert.selected_account_ids == []

    def test_serialize_deserialize(self):
        """Round-trip serialization preserves all values."""
        original = AlertDTO(
            id=5,
            account_uid="uid_5",
            comment_id=10,
            alert_type="warning",
            message="Warning message",
            status="resolved",
            comment_input="Input text",
            selected_account_ids=[1, 2],
        )
        dumped = original.model_dump()
        recreated = AlertDTO(**dumped)
        assert recreated == original


class TestStatsDTO:
    """Test StatsDTO serialization and defaults."""

    def test_create_with_required_fields(self):
        """Create StatsDTO with only required fields, verify defaults."""
        stats = StatsDTO(
            total_comments=100,
            team_hot_count=30,
            remaining_quota=70,
            elapsed_time="00:15:30",
            hot_ratio=0.3,
        )
        assert stats.total_comments == 100
        assert stats.team_hot_count == 30
        assert stats.remaining_quota == 70
        assert stats.elapsed_time == "00:15:30"
        assert stats.hot_ratio == 0.3
        # Defaults
        assert stats.team_online_count == 0
        assert stats.pending_alerts == 0
        assert stats.executed_actions == 0

    def test_create_with_all_fields(self):
        """Create StatsDTO with all fields including defaults overridden."""
        stats = StatsDTO(
            total_comments=200,
            team_hot_count=80,
            remaining_quota=120,
            elapsed_time="00:30:00",
            hot_ratio=0.4,
            team_online_count=5,
            pending_alerts=3,
            executed_actions=15,
        )
        assert stats.team_online_count == 5
        assert stats.pending_alerts == 3
        assert stats.executed_actions == 15

    def test_serialize_deserialize(self):
        """Round-trip serialization preserves all values."""
        original = StatsDTO(
            total_comments=50,
            team_hot_count=10,
            remaining_quota=40,
            elapsed_time="00:05:00",
            hot_ratio=0.2,
            team_online_count=2,
            pending_alerts=1,
            executed_actions=3,
        )
        dumped = original.model_dump()
        recreated = StatsDTO(**dumped)
        assert recreated == original


class TestWSMessage:
    """Test WSMessage serialization."""

    def test_create_and_serialize(self):
        """Create WSMessage, serialize, verify fields."""
        msg = WSMessage(
            type="comment_update",
            data={"comment_id": 1, "content": "New comment"},
            timestamp="2025-06-25T12:00:00Z",
        )
        dumped = msg.model_dump()

        assert dumped["type"] == "comment_update"
        assert dumped["data"] == {"comment_id": 1, "content": "New comment"}
        assert dumped["timestamp"] == "2025-06-25T12:00:00Z"

    def test_deserialize_from_dict(self):
        """Reconstruct WSMessage from dict."""
        raw = {
            "type": "stats_update",
            "data": {"total_comments": 100},
            "timestamp": "2025-06-25T12:00:00Z",
        }
        msg = WSMessage(**raw)
        assert msg.type == "stats_update"
        assert msg.data == {"total_comments": 100}
        assert msg.timestamp == "2025-06-25T12:00:00Z"
