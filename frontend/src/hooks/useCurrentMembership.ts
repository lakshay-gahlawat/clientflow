import { useQuery } from "@tanstack/react-query";
import { listMembers } from "../api/workspaces";
import { useAuth } from "../auth/AuthContext";
import { useWorkspace } from "../workspace/WorkspaceContext";
import type { WorkspaceRole } from "../api/types";

// The backend is the actual source of truth for every permission check —
// this hook only exists so the UI can hide actions a role can't perform,
// instead of showing a button that predictably 403s. Never treat the
// return value here as authorization; it's a UX convenience only.
export function useCurrentMembership(): { role: WorkspaceRole | null; isLoading: boolean } {
  const { user } = useAuth();
  const { currentWorkspace } = useWorkspace();

  const membersQuery = useQuery({
    queryKey: ["workspace-members", currentWorkspace?.id],
    queryFn: () => listMembers(currentWorkspace!.id),
    enabled: !!currentWorkspace,
  });

  const role = membersQuery.data?.find((m) => m.user_id === user?.id)?.role ?? null;
  return { role, isLoading: membersQuery.isLoading };
}
