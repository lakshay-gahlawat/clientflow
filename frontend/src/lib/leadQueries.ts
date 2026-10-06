import type { QueryClient } from "@tanstack/react-query";
import type { LeadStatus } from "../api/types";

const COUNT_STATUSES: LeadStatus[] = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "WON", "LOST"];

// All list/aggregate lead queries share the prefix ["leads", workspaceId]
// so a single invalidateQueries call keeps the list, pipeline, dashboard
// counts, and follow-up lookup in sync. Detail queries use ["lead", ...]
// (singular) and are invalidated separately.
export const leadKeys = {
  all: (workspaceId: string) => ["leads", workspaceId] as const,
  list: (workspaceId: string, filters: unknown) => ["leads", workspaceId, filters] as const,
  total: (workspaceId: string) => ["leads", workspaceId, "total"] as const,
  count: (workspaceId: string, status: LeadStatus) => ["leads", workspaceId, "count", status] as const,
  recent: (workspaceId: string) => ["leads", workspaceId, "recent"] as const,
  pipeline: (workspaceId: string, status: LeadStatus) =>
    ["leads", workspaceId, "pipeline", status] as const,
  lookup: (workspaceId: string) => ["leads", workspaceId, "lookup"] as const,
  detail: (workspaceId: string, leadId?: string) =>
    leadId ? (["lead", workspaceId, leadId] as const) : (["lead", workspaceId] as const),
};

export function invalidateWorkspaceLeads(
  queryClient: QueryClient,
  workspaceId: string,
  leadId?: string,
  options?: { refetchDetail?: boolean },
): void {
  // refetchType: "all" also refetches inactive dashboard queries so
  // totals/status counts/recent leads are fresh without a full reload.
  void queryClient.invalidateQueries({
    queryKey: leadKeys.all(workspaceId),
    refetchType: "all",
    // Pipeline columns are updated optimistically; refetching them is
    // what produced the brief empty/stale flash after a status change.
    predicate: (query) => query.queryKey[2] !== "pipeline",
  });
  void queryClient.invalidateQueries({ queryKey: leadKeys.total(workspaceId), refetchType: "all" });
  void queryClient.invalidateQueries({ queryKey: leadKeys.recent(workspaceId), refetchType: "all" });
  for (const status of COUNT_STATUSES) {
    void queryClient.invalidateQueries({ queryKey: leadKeys.count(workspaceId, status), refetchType: "all" });
  }
  if (options?.refetchDetail !== false) {
    void queryClient.invalidateQueries({ queryKey: leadKeys.detail(workspaceId, leadId) });
  }
}
