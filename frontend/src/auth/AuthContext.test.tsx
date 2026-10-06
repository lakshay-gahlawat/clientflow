import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";

// Mock the api/auth and api/client modules entirely — this test is
// about AuthContext's own state-management logic (loading → resolved,
// login/register/logout state transitions, staying in sync with the
// api client's session broadcast), not about re-testing the interceptor
// itself (that's client.test.ts).
const mockRestoreSession = vi.fn();
const mockOnSessionChange = vi.fn();
const mockLoginRequest = vi.fn();
const mockRegisterRequest = vi.fn();
const mockLogoutRequest = vi.fn();

vi.mock("../api/client", () => ({
  restoreSession: (...args: unknown[]) => mockRestoreSession(...args),
  onSessionChange: (...args: unknown[]) => mockOnSessionChange(...args),
}));

vi.mock("../api/auth", () => ({
  loginRequest: (...args: unknown[]) => mockLoginRequest(...args),
  registerRequest: (...args: unknown[]) => mockRegisterRequest(...args),
  logoutRequest: (...args: unknown[]) => mockLogoutRequest(...args),
  fetchCurrentUser: vi.fn(),
}));

const TEST_USER = { id: "u1", email: "a@test.com", full_name: "Test User" };

function TestConsumer({ onReady }: { onReady?: (auth: ReturnType<typeof useAuth>) => void }) {
  const auth = useAuth();
  onReady?.(auth);
  return (
    <div>
      <div data-testid="loading">{String(auth.isLoading)}</div>
      <div data-testid="authenticated">{String(auth.isAuthenticated)}</div>
      <div data-testid="email">{auth.user?.email ?? "none"}</div>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    mockRestoreSession.mockReset();
    mockOnSessionChange.mockReset().mockReturnValue(() => {});
    mockLoginRequest.mockReset();
    mockRegisterRequest.mockReset();
    mockLogoutRequest.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("starts loading, then resolves to unauthenticated when no session exists", async () => {
    mockRestoreSession.mockResolvedValue(null);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    // Immediately after mount, still resolving the session-restore call.
    expect(screen.getByTestId("loading").textContent).toBe("true");

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(mockRestoreSession).toHaveBeenCalledTimes(1);
  });

  it("stays loading if a null session is broadcast before restoreSession settles", async () => {
    let resolveRestore: (value: typeof TEST_USER | null) => void = () => {};
    mockRestoreSession.mockReturnValue(
      new Promise((resolve) => {
        resolveRestore = resolve;
      }),
    );
    let capturedListener: ((user: typeof TEST_USER | null) => void) | undefined;
    mockOnSessionChange.mockImplementation((listener) => {
      capturedListener = listener;
      return () => {};
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    expect(screen.getByTestId("loading").textContent).toBe("true");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");

    await act(async () => {
      capturedListener?.(null);
    });

    expect(screen.getByTestId("loading").textContent).toBe("true");
    expect(screen.getByTestId("authenticated").textContent).toBe("false");

    await act(async () => {
      resolveRestore(TEST_USER);
    });

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
  });

  it("restores an existing session on mount (e.g. after a page refresh)", async () => {
    mockRestoreSession.mockResolvedValue(TEST_USER);

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );

    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("email").textContent).toBe("a@test.com");
  });

  it("login() sets the user and marks the session authenticated", async () => {
    mockRestoreSession.mockResolvedValue(null);
    mockLoginRequest.mockResolvedValue(TEST_USER);
    let auth: ReturnType<typeof useAuth> | undefined;

    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (auth = a)} />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));

    await act(async () => {
      await auth!.login("a@test.com", "password123");
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("true");
    expect(screen.getByTestId("email").textContent).toBe("a@test.com");
    expect(mockLoginRequest).toHaveBeenCalledWith("a@test.com", "password123");
  });

  it("logout() clears the user state even when the API call rejects (finally runs before the error propagates)", async () => {
    // This matters: an already-invalid session (e.g. the refresh cookie
    // already expired server-side) shouldn't trap the user in a state
    // where they can't get back to the login page.
    mockRestoreSession.mockResolvedValue(TEST_USER);
    mockLogoutRequest.mockRejectedValue(new Error("network error"));
    let auth: ReturnType<typeof useAuth> | undefined;

    render(
      <AuthProvider>
        <TestConsumer onReady={(a) => (auth = a)} />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("authenticated").textContent).toBe("true"));

    await act(async () => {
      // logout()'s try/finally clears state before re-throwing — it
      // does NOT swallow the error (the real Sidebar caller uses
      // `void logout()`, fire-and-forget, relying on finally alone).
      // A caller that DOES await it, like this test, correctly sees
      // the rejection — asserting that is part of confirming the
      // real contract, not a bug to work around.
      await expect(auth!.logout()).rejects.toThrow("network error");
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
    expect(screen.getByTestId("email").textContent).toBe("none");
  });

  it("stays in sync when the api client broadcasts a session change (e.g. a transparent mid-session refresh failure)", async () => {
    mockRestoreSession.mockResolvedValue(TEST_USER);
    let capturedListener: ((user: typeof TEST_USER | null) => void) | undefined;
    mockOnSessionChange.mockImplementation((listener) => {
      capturedListener = listener;
      return () => {};
    });

    render(
      <AuthProvider>
        <TestConsumer />
      </AuthProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("authenticated").textContent).toBe("true"));

    // Simulate the api client's response interceptor deciding, entirely
    // on its own (a failed background refresh), that the session is dead.
    await act(async () => {
      capturedListener?.(null);
    });

    expect(screen.getByTestId("authenticated").textContent).toBe("false");
  });

  it("useAuth throws when used outside an AuthProvider", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow("useAuth must be used within an AuthProvider");
    consoleError.mockRestore();
  });
});
