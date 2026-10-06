import { apiClient } from "./client";
import type { FollowUp, FollowUpStatus } from "./types";

export interface ListFollowUpsParams {
  status?: FollowUpStatus;
  lead_id?: string;
  mine?: boolean;
}

export async function listFollowUps(workspaceId: string, params: ListFollowUpsParams = {}): Promise<FollowUp[]> {
  const { data } = await apiClient.get<FollowUp[]>(`/workspaces/${workspaceId}/follow-ups`, { params });
  return data;
}

export interface FollowUpInput {
  title: string;
  due_at: string;
  assigned_to?: string | null;
}

export async function createFollowUp(workspaceId: string, leadId: string, input: FollowUpInput): Promise<FollowUp> {
  const { data } = await apiClient.post<FollowUp>(
    `/workspaces/${workspaceId}/leads/${leadId}/follow-ups`,
    input,
  );
  return data;
}

export async function cancelFollowUp(workspaceId: string, followUpId: string): Promise<FollowUp> {
  const { data } = await apiClient.post<FollowUp>(`/workspaces/${workspaceId}/follow-ups/${followUpId}/cancel`);
  return data;
}

export async function deleteFollowUp(workspaceId: string, followUpId: string): Promise<void> {
  await apiClient.delete(`/workspaces/${workspaceId}/follow-ups/${followUpId}`);
}
