import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import AlertCard from "../AlertCard";
import type { AlertDTO } from "@/types/alert";
import type { AccountDTO } from "@/types/account";

const mockAlert: AlertDTO = {
  id: 1,
  alert_type: "dropped_out",
  message: "Alice掉出热评!",
  status: "pending",
};

const mockAccounts: AccountDTO[] = [
  { id: 1, weibo_uid: "uid1", nickname: "Alice", status: "active" },
  { id: 2, weibo_uid: "uid2", nickname: "Bob", status: "active" },
];

describe("AlertCard", () => {
  it("renders with alert info", () => {
    render(<AlertCard alert={mockAlert} accounts={mockAccounts} />);
    expect(screen.getByTestId("alert-card")).toBeInTheDocument();
    expect(screen.getByText("Alice掉出热评!")).toBeInTheDocument();
  });

  it("buttons disabled when no comment text", () => {
    render(<AlertCard alert={mockAlert} accounts={mockAccounts} />);
    expect(screen.getByTestId("like-support-btn")).toBeDisabled();
    expect(screen.getByTestId("comment-support-btn")).toBeDisabled();
    expect(screen.getByTestId("both-support-btn")).toBeDisabled();
  });

  it("buttons disabled when no accounts selected", () => {
    render(<AlertCard alert={mockAlert} accounts={mockAccounts} />);
    // Type comment
    fireEvent.change(screen.getByTestId("comment-input"), { target: { value: "加油!" } });
    // Buttons still disabled — no account selected
    expect(screen.getByTestId("comment-support-btn")).toBeDisabled();
  });

  it("typing comment and selecting account enables buttons", () => {
    render(<AlertCard alert={mockAlert} accounts={mockAccounts} />);
    // Type comment
    fireEvent.change(screen.getByTestId("comment-input"), { target: { value: "加油!" } });
    // Check account checkbox
    fireEvent.click(screen.getByTestId("account-checkbox-1"));
    // Buttons should be enabled now
    expect(screen.getByTestId("like-support-btn")).not.toBeDisabled();
    expect(screen.getByTestId("comment-support-btn")).not.toBeDisabled();
    expect(screen.getByTestId("both-support-btn")).not.toBeDisabled();
  });

  it("clicking execute calls onExecute callback", async () => {
    const onExecute = vi.fn().mockResolvedValue(undefined);
    render(<AlertCard alert={mockAlert} accounts={mockAccounts} onExecute={onExecute} />);
    // Type comment
    fireEvent.change(screen.getByTestId("comment-input"), { target: { value: "加油!" } });
    // Select account
    fireEvent.click(screen.getByTestId("account-checkbox-1"));
    // Click execute
    fireEvent.click(screen.getByTestId("comment-support-btn"));
    await waitFor(() => {
      expect(onExecute).toHaveBeenCalledWith(1, "加油!", [1]);
    });
  });
});
