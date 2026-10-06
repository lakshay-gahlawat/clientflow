import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorkspaceProvider, useWorkspace } from "./WorkspaceContext";
import { queryClient } from "../lib/queryClient";
import type { User, Workspace } from "../api/types";

const mockListMyWorkspaces = vi.fn();

vi.mock("../api/workspaces", () => ({
  listMyWorkspaces: (...args: unknown[]) => mockListMyWorkspaces(...args),
  createWorkspace: vi.fn(),
  getWorkspace: vi.fn(),
}));

let auth = {
  user: null as User | null,
  isAuthenticated: false,
  isLoading: true,
};

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => auth,
}));

const WORKSPACE_A: Workspace = {
  id: "ws-a",
  name: "Acme",
  slug: "acme",
  owner_id: "user-a",
  created_at: "2026-01-01T00:00:00Z",
};
const WORKSPACE_B: Workspace = {
  id: "ws-b",
  name: "Beta",
  slug: "beta",
  owner_id: "user-b",
  created_at: "2026-01-01T00:00:00Z",
};
const USER_A: User = { id: "user-a", email: "a@test.com", full_name: "A" };
const USER_B: User = { id: "user-b", email: "b@test.com", full_name: "B" };

function GateProbe() {
  const { currentWorkspace, isLoading } = useWorkspace();
  if (isLoading) return <div data-testid="gate">loading</div>;
  if (!currentWorkspace) return <div data-testid="gate">onboarding</div>;
  return <div data-testid="gate">{currentWorkspace.id}</div>;
}

function renderGate() {
  return render(
    <WorkspaceProvider>
      <GateProbe />
    </WorkspaceProvider>,
  );
}

describe("WorkspaceProvider session restore", () => {
  beforeEach(() => {
    mockListMyWorkspaces.mockReset();
    queryClient.clear();
    localStorage.clear();
    auth = { user: null, isAuthenticated: false, isLoading: true };
  });

  it("does not send an existing workspace to onboarding while auth is still restoring", () => {
    mockListMyWorkspaces.mockResolvedValue([WORKSPACE_A]);
    renderGate();
    expect(screen.getByTestId("gate").textContent).toBe("loading");
  });

  it("restores the existing workspace after auth + workspace list resolve (browser refresh)", async () => {
    mockListMyWorkspaces.mockResolvedValue([WORKSPACE_A]);
    const { rerender } = renderGate();
    expect(screen.getByTestId("gate").textContent).toBe("loading");

    auth = { user: USER_A, isAuthenticated: true, isLoading: false };
    rerender(
      <WorkspaceProvider>
        <GateProbe />
      </WorkspaceProvider>,
    );

    expect(screen.getByTestId("gate").textContent).toBe("loading");
    await waitFor(() => expect(screen.getByTestId("gate").textContent).toBe("ws-a"));
  });

  it("does not reuse the previous account's workspace when switching users", async () => {
    mockListMyWorkspaces.mockResolvedValueOnce([WORKSPACE_A]).mockResolvedValueOnce([WORKSPACE_B]);
    const { rerender } = renderGate();

    auth = { user: USER_A, isAuthenticated: true, isLoading: false };
    rerender(
      <WorkspaceProvider>
        <GateProbe />
      </WorkspaceProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("gate").textContent).toBe("ws-a"));

    auth = { user: USER_B, isAuthenticated: true, isLoading: false };
    rerender(
      <WorkspaceProvider>
        <GateProbe />
      </WorkspaceProvider>,
    );
    expect(screen.getByTestId("gate").textContent).toBe("loading");
    await waitFor(() => expect(screen.getByTestId("gate").textContent).toBe("ws-b"));
  });
});
