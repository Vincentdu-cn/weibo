import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MemberStatusGrid from "../MemberStatusGrid";
import type { MemberCard } from "@/hooks/useMemberStatus";

const mockMembers: MemberCard[] = [
  {
    uid: "uid1",
    nickname: "Alice",
    avatar_url: null,
    total_comments: 2,
    total_likes: 500,
    best_rank: 1,
    in_hot: true,
    comments: [
      { comment_id: "c1", content: "test", like_count: 300, rank: 1, is_hot: true, created_at: "2024-01-01" },
      { comment_id: "c2", content: "test2", like_count: 200, rank: 5, is_hot: false, created_at: "2024-01-01" },
    ],
  },
  {
    uid: "uid2",
    nickname: "Bob",
    avatar_url: null,
    total_comments: 1,
    total_likes: 50,
    best_rank: 15,
    in_hot: false,
    comments: [
      { comment_id: "c3", content: "bob comment", like_count: 50, rank: 15, is_hot: false, created_at: "2024-01-01" },
    ],
  },
  {
    uid: "uid3",
    nickname: "Charlie",
    avatar_url: null,
    total_comments: 0,
    total_likes: 0,
    best_rank: null,
    in_hot: false,
    comments: [],
  },
];

describe("MemberStatusGrid", () => {
  it("renders empty state when no members", () => {
    render(<MemberStatusGrid members={[]} />);
    expect(screen.getByText("暂无组员数据")).toBeInTheDocument();
  });

  it("renders member cards when members provided", () => {
    render(<MemberStatusGrid members={mockMembers} />);
    expect(screen.getAllByTestId("member-card")).toHaveLength(3);
  });

  it("hot member card has border-success class", () => {
    render(<MemberStatusGrid members={mockMembers} />);
    const cards = screen.getAllByTestId("member-card");
    // Alice (index 0) is hot
    expect(cards[0].className).toContain("border-success");
  });

  it("dropped member card has border-destructive class", () => {
    render(<MemberStatusGrid members={mockMembers} />);
    const cards = screen.getAllByTestId("member-card");
    // Bob (index 1) has comment but not hot
    expect(cards[1].className).toContain("border-destructive");
  });

  it("loading state shows skeletons", () => {
    render(<MemberStatusGrid members={[]} isLoading={true} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
