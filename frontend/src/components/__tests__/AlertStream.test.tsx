import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import AlertStream from "../AlertStream";
import type { AlertDTO } from "@/types/alert";

const mockAlerts: AlertDTO[] = [
  { id: 1, alert_type: "dropped_out", message: "Alice掉出热评!", status: "pending" },
  { id: 2, alert_type: "rank_changed", message: "Bob排名下降", status: "pending" },
];

describe("AlertStream", () => {
  it("renders empty state when no alerts", () => {
    render(<AlertStream alerts={[]} />);
    expect(screen.getByText("暂无告警, 监控中...")).toBeInTheDocument();
  });

  it("renders alert items when alerts provided", () => {
    render(<AlertStream alerts={mockAlerts} />);
    expect(screen.getAllByTestId("alert-item")).toHaveLength(2);
    expect(screen.getByText("Alice掉出热评!")).toBeInTheDocument();
  });

  it("clicking expand button shows AlertCard", () => {
    render(<AlertStream alerts={mockAlerts} />);
    // AlertCard not visible initially
    expect(screen.queryByTestId("alert-card")).not.toBeInTheDocument();
    // Click expand on first alert
    fireEvent.click(screen.getByTestId("alert-expand-1"));
    expect(screen.getByTestId("alert-card")).toBeInTheDocument();
  });

  it("loading state shows skeletons", () => {
    render(<AlertStream alerts={[]} isLoading={true} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
