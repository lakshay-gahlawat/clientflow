import { apiClient } from "./client";
import type { Lead, LeadStatus, PaginatedLeads } from "./types";

export interface ListLeadsParams {
  status?: LeadStatus;
  assigned_to?: string;
  search?: string;
  sort_by?: "created_at" | "updated_at" | "name";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export async function listLeads(workspaceId: string, params: ListLeadsParams = {}): Promise<PaginatedLeads> {
  const { data } = await apiClient.get<PaginatedLeads>(`/workspaces/${workspaceId}/leads`, { params });
  return data;
}

export async function getLead(workspaceId: string, leadId: string): Promise<Lead> {
  const { data } = await apiClient.get<Lead>(`/workspaces/${workspaceId}/leads/${leadId}`);
  return data;
}

export interface LeadInput {
  name: string;
  company: string;
  email: string;
  phone?: string | null;
  source?: string | null;
  notes?: string | null;
  assigned_to?: string | null;
}

export async function createLead(workspaceId: string, input: LeadInput): Promise<Lead> {
  const { data } = await apiClient.post<Lead>(`/workspaces/${workspaceId}/leads`, input);
  return data;
}

export async function updateLead(
  workspaceId: string,
  leadId: string,
  input: Partial<LeadInput>,
): Promise<Lead> {
  const { data } = await apiClient.patch<Lead>(`/workspaces/${workspaceId}/leads/${leadId}`, input);
  return data;
}

export async function updateLeadStatus(workspaceId: string, leadId: string, status: LeadStatus): Promise<Lead> {
  const { data } = await apiClient.patch<Lead>(`/workspaces/${workspaceId}/leads/${leadId}/status`, {
    status,
  });
  return data;
}

export async function deleteLead(workspaceId: string, leadId: string): Promise<void> {
  await apiClient.delete(`/workspaces/${workspaceId}/leads/${leadId}`);
}
