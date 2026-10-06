import { apiClient } from "./client";
import type { Subscription } from "./types";

export async function getBilling(workspaceId: string): Promise<Subscription> {
  const { data } = await apiClient.get<Subscription>(`/workspaces/${workspaceId}/billing`);
  return data;
}

export async function createCheckoutSession(workspaceId: string): Promise<string> {
  const { data } = await apiClient.post<{ checkout_url: string }>(
    `/workspaces/${workspaceId}/billing/checkout-session`,
  );
  return data.checkout_url;
}
