// Mirrors the backend Pydantic schemas exactly (app/schemas/*.py).
// Keep these in sync by hand for now — no codegen step exists yet.

export type WorkspaceRole = "OWNER" | "ADMIN" | "MEMBER";

export type LeadStatus = "NEW" | "CONTACTED" | "QUALIFIED" | "PROPOSAL" | "WON" | "LOST";

export interface User {
  id: string;
  email: string;
  full_name: string;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  created_at: string;
}

export interface WorkspaceMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: WorkspaceRole;
  joined_at: string;
}

export interface Lead {
  id: string;
  workspace_id: string;
  name: string;
  company: string;
  email: string;
  phone: string | null;
  source: string | null;
  status: LeadStatus;
  notes: string | null;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedLeads {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

// Shape of FastAPI's default error body: {"detail": "..."} or, for 422
// validation errors, {"detail": [{"loc": [...], "msg": "...", ...}]}.
export interface ApiErrorBody {
  detail?: string | { msg: string; loc: (string | number)[] }[];
}

export type FollowUpStatus = "PENDING" | "PROCESSING" | "SENT" | "CANCELLED";

export interface FollowUp {
  id: string;
  lead_id: string;
  workspace_id: string;
  assigned_to: string | null;
  title: string;
  due_at: string;
  status: FollowUpStatus;
  created_at: string;
}

export type SubscriptionPlan = "FREE" | "PRO";
export type SubscriptionStatus = "ACTIVE" | "PAST_DUE" | "CANCELLED" | "INCOMPLETE";

export interface Subscription {
  workspace_id: string;
  plan: SubscriptionPlan;
  status: SubscriptionStatus;
  current_period_end: string | null;
}
