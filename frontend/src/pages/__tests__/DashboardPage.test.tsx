import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import DashboardPage from "../DashboardPage";

describe("DashboardPage", () => {
  it("renders dashboard root", () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    expect(screen.getByTestId("dashboard-root")).toBeInTheDocument();
  });

  it("renders hot comments zone", () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    expect(screen.getByTestId("hot-comments-zone")).toBeInTheDocument();
  });

  it("renders stats zone", () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    expect(screen.getByTestId("stats-zone")).toBeInTheDocument();
  });

  it("renders member status zone", () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    expect(screen.getByTestId("member-status-zone")).toBeInTheDocument();
  });

  it("renders batch like zone", () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    expect(screen.getByTestId("batch-like-zone")).toBeInTheDocument();
  });
});
