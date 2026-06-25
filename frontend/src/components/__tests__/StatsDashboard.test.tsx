import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatsDashboard from "../StatsDashboard";
import type { StatsDTO } from "@/types/stats";

// recharts ResponsiveContainer needs ResizeObserver
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

const mockStats: StatsDTO = {
  total_comments: 150,
  team_hot_count: 8,
  remaining_quota: 350,
  elapsed_time: "12:30",
  hot_ratio: 0.16,
  team_online_count: 18,
  pending_alerts: 2,
  executed_actions: 5,
};

describe("StatsDashboard", () => {
  it("renders empty state when stats is null", () => {
    render(<StatsDashboard stats={null} />);
    expect(screen.getByText("暂无统计数据")).toBeInTheDocument();
  });

  it("renders big number and stats when stats provided", () => {
    render(<StatsDashboard stats={mockStats} />);
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText(/16.0%/)).toBeInTheDocument();
    expect(screen.getByText("12:30")).toBeInTheDocument();
  });

  it("progress bar shows correct value", () => {
    render(<StatsDashboard stats={mockStats} />);
    expect(screen.getByText("150/500")).toBeInTheDocument();
  });

  it("mini stat cards show correct numbers", () => {
    render(<StatsDashboard stats={mockStats} />);
    expect(screen.getByText("18")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("loading state shows skeletons", () => {
    render(<StatsDashboard stats={null} isLoading={true} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
