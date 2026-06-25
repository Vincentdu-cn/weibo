import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import HotCommentLeaderboard from "../HotCommentLeaderboard";
import type { CommentDTO } from "@/types/comment";

const mockComments: CommentDTO[] = [
  {
    id: 1,
    weibo_comment_id: "c1",
    user_uid: "uid1",
    user_name: "Alice",
    content: "加油加油！",
    like_count: 500,
    rank: 1,
    is_hot: true,
    is_team_member: true,
  },
  {
    id: 2,
    weibo_comment_id: "c2",
    user_uid: "uid2",
    user_name: "Bob",
    content: "支持支持",
    like_count: 400,
    rank: 2,
    is_hot: true,
    is_team_member: false,
  },
  {
    id: 3,
    weibo_comment_id: "c3",
    user_uid: "uid3",
    user_name: "Charlie",
    content: "厉害了",
    like_count: 300,
    rank: 3,
    is_hot: true,
    is_team_member: false,
  },
  {
    id: 4,
    weibo_comment_id: "c4",
    user_uid: "uid4",
    user_name: "Dave",
    content: "一般般",
    like_count: 50,
    rank: 10,
    is_hot: false,
    is_team_member: false,
  },
];

describe("HotCommentLeaderboard", () => {
  it("renders empty state when no comments", () => {
    render(<HotCommentLeaderboard comments={[]} teamUids={[]} />);
    expect(screen.getByText("暂无热评数据")).toBeInTheDocument();
  });

  it("renders comment rows when comments provided", () => {
    render(<HotCommentLeaderboard comments={mockComments} teamUids={["uid1"]} />);
    expect(screen.getAllByTestId("comment-row")).toHaveLength(4);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("team member row has highlight class", () => {
    render(<HotCommentLeaderboard comments={mockComments} teamUids={["uid1"]} />);
    const rows = screen.getAllByTestId("comment-row");
    // First row (Alice, uid1) is a team member — should have bg-success/10
    expect(rows[0].className).toContain("bg-success/10");
    expect(rows[0].className).toContain("border-success");
    // Second row (Bob, uid2) is NOT a team member
    expect(rows[1].className).not.toContain("bg-success/10");
  });

  it("top 3 ranks get special badges", () => {
    render(<HotCommentLeaderboard comments={mockComments} teamUids={[]} />);
    const badges = screen.getAllByText(/#\d+/);
    // Rank 1 = gold
    expect(badges[0].className).toContain("yellow-500");
    // Rank 2 = silver
    expect(badges[1].className).toContain("gray-300");
    // Rank 3 = bronze
    expect(badges[2].className).toContain("orange-700");
    // Rank 10 = outline (no special color)
    expect(badges[3].className).not.toContain("yellow-500");
  });

  it("loading state shows skeletons", () => {
    render(<HotCommentLeaderboard comments={[]} teamUids={[]} isLoading={true} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
