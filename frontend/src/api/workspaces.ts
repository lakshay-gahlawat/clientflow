import { apiClient } from "./client";
import type { Workspace, WorkspaceMember, WorkspaceRole } from "./types";

export async function listMyWorkspaces(): Promise<Workspace[]> {
  const { data } = await apiClient.get<Workspace[]>("/workspaces");
  return data;
}

export async function createWorkspace(name: string, slug: string): Promise<Workspace> {
  const { data } = await apiClient.post<Workspace>("/workspaces", { name, slug });
  return data;
}

// Doubles as a membership check: 404 means "doesn't exist, or you're not
// a member" (the backend deliberately doesn't distinguish — see Phase 4
// tenant-isolation design), which is exactly what we want when verifying
// a locally-remembered workspace ID is still valid.
export async function getWorkspace(workspaceId: string): Promise<Workspace> {
  const { data } = await apiClient.get<Workspace>(`/workspaces/${workspaceId}`);
  return data;
}

export async function listMembers(workspaceId: string): Promise<WorkspaceMember[]> {
  const { data } = await apiClient.get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`);
  return data;
}

export async function addMember(
  workspaceId: string,
  email: string,
  role: WorkspaceRole,
): Promise<WorkspaceMember> {
  const { data } = await apiClient.post<WorkspaceMember>(`/workspaces/${workspaceId}/members`, {
    email,
    role,
  });
  return data;
}

export async function updateMemberRole(
  workspaceId: string,
  memberId: string,
  role: WorkspaceRole,
): Promise<WorkspaceMember> {
  const { data } = await apiClient.patch<WorkspaceMember>(
    `/workspaces/${workspaceId}/members/${memberId}`,
    { role },
  );
  return data;
}

export async function removeMember(workspaceId: string, memberId: string): Promise<void> {
  await apiClient.delete(`/workspaces/${workspaceId}/members/${memberId}`);
}
