import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import {
  createWorkspace as createWorkspaceRequest,
  getWorkspace,
  listMyWorkspaces,
} from "../api/workspaces";
import { useAuth } from "../auth/AuthContext";
import { queryClient } from "../lib/queryClient";
import type { Workspace } from "../api/types";

// As of Phase 6, workspace membership is discovered via the real
// GET /workspaces endpoint (added this phase specifically to fix this).
// localStorage is used ONLY to remember which of the user's real
// workspaces was last selected, scoped per-user — ordinary UX
// persistence, not a workaround for a missing backend capability.

function currentIdKey(userId: string): string {
  return `clientflow:currentWorkspaceId:${userId}`;
}

interface WorkspaceContextValue {
  currentWorkspace: Workspace | null;
  workspaces: Workspace[];
  isLoading: boolean;
  error: string | null;
  switchWorkspace: (workspaceId: string) => void;
  createWorkspace: (name: string, slug: string) => Promise<Workspace>;
  joinWorkspace: (workspaceId: string) => Promise<Workspace>;
  refetch: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user, isAuthenticated, isLoading: authLoading } = useAuth();
  const userId = user?.id;
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentWorkspace, setCurrentWorkspace] = useState<Workspace | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadedUserId, setLoadedUserId] = useState<string | null>(null);
  const cacheUserIdRef = useRef<string | null>(null);

  const loadWorkspaces = useCallback(async () => {
    if (!userId) return;
    setIsLoading(true);
    setError(null);
    try {
      const list = await listMyWorkspaces();
      setWorkspaces(list);

      const storedId = localStorage.getItem(currentIdKey(userId));
      const stored = storedId ? list.find((w) => w.id === storedId) : undefined;
      const next = stored ?? list[0] ?? null;
      setCurrentWorkspace(next);
      if (next) localStorage.setItem(currentIdKey(userId), next.id);
    } catch {
      setError("Couldn't load your workspaces.");
      setWorkspaces([]);
      setCurrentWorkspace(null);
    } finally {
      setLoadedUserId(userId);
      setIsLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    // Auth is still restoring — keep the workspace gate in a loading
    // state. Setting isLoading false here is what sent a logged-in user
    // with a workspace to /onboarding/workspace on browser refresh.
    if (authLoading) return;

    if (!isAuthenticated || !userId) {
      if (cacheUserIdRef.current !== null) {
        queryClient.clear();
        cacheUserIdRef.current = null;
      }
      setWorkspaces([]);
      setCurrentWorkspace(null);
      setLoadedUserId(null);
      setIsLoading(false);
      return;
    }

    if (cacheUserIdRef.current !== userId) {
      queryClient.clear();
      cacheUserIdRef.current = userId;
    }
    void loadWorkspaces();
  }, [authLoading, isAuthenticated, userId, loadWorkspaces]);

  const switchWorkspace = useCallback(
    (workspaceId: string) => {
      if (!user) return;
      const workspace = workspaces.find((w) => w.id === workspaceId);
      if (!workspace) return;
      setCurrentWorkspace(workspace);
      localStorage.setItem(currentIdKey(user.id), workspace.id);
    },
    [user, workspaces],
  );

  const createWorkspace = useCallback(
    async (name: string, slug: string) => {
      const workspace = await createWorkspaceRequest(name, slug);
      setWorkspaces((current) => [...current, workspace]);
      setCurrentWorkspace(workspace);
      if (user) localStorage.setItem(currentIdKey(user.id), workspace.id);
      return workspace;
    },
    [user],
  );

  const joinWorkspace = useCallback(
    async (workspaceId: string) => {
      // getWorkspace 404s if the user isn't actually a member — the real
      // check. This is now just a convenience for immediately switching
      // to a workspace a teammate just added the user to, without
      // waiting for a full workspace-list refetch.
      const workspace = await getWorkspace(workspaceId);
      setWorkspaces((current) => (current.some((w) => w.id === workspace.id) ? current : [...current, workspace]));
      setCurrentWorkspace(workspace);
      if (user) localStorage.setItem(currentIdKey(user.id), workspace.id);
      return workspace;
    },
    [user],
  );

  const waitingForThisUser = !!userId && loadedUserId !== userId;

  const value: WorkspaceContextValue = {
    currentWorkspace: waitingForThisUser ? null : currentWorkspace,
    workspaces: waitingForThisUser ? [] : workspaces,
    isLoading: authLoading || isLoading || waitingForThisUser,
    error,
    switchWorkspace,
    createWorkspace,
    joinWorkspace,
    refetch: loadWorkspaces,
  };

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within a WorkspaceProvider");
  return ctx;
}
