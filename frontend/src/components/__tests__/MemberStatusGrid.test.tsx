import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import MemberStatusGrid from "../MemberStatusGrid";
import type { MemberGridItem } from "@/hooks/useMemberStatus";

const mockMembers: MemberGridItem[] = [
  { uid: "uid1", nickname: "Alice", avatar_url: null, current_rank: 1, like_count: 500, is_hot: true, comment_count: 2, online_status: "online" },
  { uid: "uid2", nickname: "Bob", avatar_url: null, current_rank: 15, like_count: 50, is_hot: false, comment_count: 1, online_status: "online" },
  { uid: "uid3", nickname: "Charlie", avatar_url: null, current_rank: null, like_count: null, is_hot: false, comment_count: 0, online_status: "offline" },
];

// Pad to 20
const fullMembers: MemberGridItem[] = [
  ...mockMembers,
  ...Array.from({ length: 17 }).map(() => ({
    uid: null, nickname: null, avatar_url: null, current_rank: null,
    like_count: null, is_hot: false, comment_count: 0, online_status: "unknown",
  })),
];

describe("MemberStatusGrid", () => {
  it("renders empty state when no members", () => {
    render(<MemberStatusGrid members={[]} />);
    expect(screen.getByText("暂无组员数据")).toBeInTheDocument();
  });

  it("renders 20 member cards when members provided", () => {
    render(<MemberStatusGrid members={fullMembers} />);
    expect(screen.getAllByTestId("member-card")).toHaveLength(20);
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
