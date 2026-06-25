import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import LoginPage from "../LoginPage";

// Mock the API module
vi.mock("@/api/qr", async () => {
  const actual = await vi.importActual<typeof import("@/api/qr")>("@/api/qr");
  return {
    ...actual,
    generateQr: vi.fn(),
    getQrStatus: vi.fn(),
    getAccounts: vi.fn(),
    logoutAccount: vi.fn(),
  };
});

// Mock the hook — return a controlled state for most tests
vi.mock("@/hooks/useQrLogin", () => ({
  useQrLogin: vi.fn(() => ({
    qrUrl: "https://example.com/qr.png",
    status: "waiting" as const,
    sessionId: "test-session-123",
    generate: vi.fn(),
    checkStatus: vi.fn(),
    reset: vi.fn(),
  })),
}));

import { getAccounts } from "@/api/qr";

const mockedGetAccounts = vi.mocked(getAccounts);

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders QR code section with 扫码登录 title", async () => {
    mockedGetAccounts.mockResolvedValue([]);
    await act(async () => {
      render(<LoginPage />);
    });
    expect(screen.getByText("扫码登录")).toBeInTheDocument();
  });

  it("renders account list section with 已登录账号 title", async () => {
    mockedGetAccounts.mockResolvedValue([]);
    await act(async () => {
      render(<LoginPage />);
    });
    expect(screen.getByText("已登录账号")).toBeInTheDocument();
  });

  it("shows 等待扫码 status badge initially", async () => {
    mockedGetAccounts.mockResolvedValue([]);
    await act(async () => {
      render(<LoginPage />);
    });
    expect(screen.getByText("等待扫码")).toBeInTheDocument();
  });

  it("displays progress 已登录 0/20 when no accounts", async () => {
    mockedGetAccounts.mockResolvedValue([]);
    await act(async () => {
      render(<LoginPage />);
    });
    await waitFor(() => {
      expect(screen.getByText("已登录 0/20")).toBeInTheDocument();
    });
  });

  it("renders account rows when accounts provided", async () => {
    const accounts = [
      {
        id: 1,
        weibo_uid: "1234567890",
        nickname: "TestUser1",
        status: "active",
        avatar_url: "https://example.com/avatar1.png",
      },
      {
        id: 2,
        weibo_uid: "0987654321",
        nickname: "TestUser2",
        status: "inactive",
        avatar_url: null,
      },
    ];
    mockedGetAccounts.mockResolvedValue(accounts);
    await act(async () => {
      render(<LoginPage />);
    });

    await waitFor(() => {
      expect(screen.getByTestId("account-list")).toBeInTheDocument();
    });

    const rows = screen.getAllByTestId("account-row");
    expect(rows).toHaveLength(2);

    // Check first row content
    expect(screen.getByText("TestUser1")).toBeInTheDocument();
    expect(screen.getByText("1234567890")).toBeInTheDocument();
    expect(screen.getByText("有效")).toBeInTheDocument();

    // Check second row
    expect(screen.getByText("TestUser2")).toBeInTheDocument();
    expect(screen.getByText("过期")).toBeInTheDocument();
  });

  it("shows skeleton loading state", async () => {
    // Delay the accounts resolution so loading state is visible
    mockedGetAccounts.mockImplementation(
      () => new Promise(() => {}) // never resolves
    );
    await act(async () => {
      render(<LoginPage />);
    });
    // Should show skeleton elements (multiple skeleton divs)
    const skeletons = document.querySelectorAll('[data-testid="skeleton"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});
