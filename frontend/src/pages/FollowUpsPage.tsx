import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { cancelFollowUp, listFollowUps } from "../api/followUps";
import { listLeads } from "../api/leads";
import { FollowUpStatusBadge } from "../components/ui/FollowUpStatusBadge";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { useToast } from "../components/ui/Toast";
import { extractErrorMessage } from "../api/client";
import { leadKeys } from "../lib/leadQueries";

export function FollowUpsPage() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id;
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [scope, setScope] = useState<"mine" | "all">("mine");

  const followUpsQuery = useQuery({
    queryKey: ["follow-ups", workspaceId, scope],
    queryFn: () => listFollowUps(workspaceId, { status: "PENDING", mine: scope === "mine" }),
  });

  // Follow-ups don't carry lead name/company directly (API returns
  // lead_id only) — fetch a lookup map from the leads list rather than
  // making one request per row.
  const leadsLookupQuery = useQuery({
    queryKey: leadKeys.lookup(workspaceId),
    queryFn: () => listLeads(workspaceId, { page: 1, page_size: 100 }),
  });
  const leadById = new Map((leadsLookupQuery.data?.items ?? []).map((l) => [l.id, l]));

  const cancelMutation = useMutation({
    mutationFn: (followUpId: string) => cancelFollowUp(workspaceId, followUpId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups", workspaceId] });
      showToast("Follow-up cancelled.");
    },
    onError: (err) => showToast(extractErrorMessage(err, "Couldn't cancel this follow-up."), "error"),
  });

  const isLoading = followUpsQuery.isLoading || leadsLookupQuery.isLoading;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Follow-ups</h2>
        <p className="mt-1 text-sm text-ink/60">Pending reminders across your pipeline.</p>
      </div>

      <div className="flex gap-1 rounded-lg bg-canvas p-1 w-fit">
        <button
          type="button"
          onClick={() => setScope("mine")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            scope === "mine" ? "bg-white text-ink shadow-sm" : "text-ink/60"
          }`}
        >
          Mine
        </button>
        <button
          type="button"
          onClick={() => setScope("all")}
          className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
            scope === "all" ? "bg-white text-ink shadow-sm" : "text-ink/60"
          }`}
        >
          Everyone's
        </button>
      </div>

      {isLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : followUpsQuery.isError ? (
        <ErrorState
          message={extractErrorMessage(followUpsQuery.error, "Couldn't load follow-ups.")}
          onRetry={() => void followUpsQuery.refetch()}
        />
      ) : followUpsQuery.data!.length === 0 ? (
        <EmptyState
          title="No pending follow-ups"
          description={
            scope === "mine"
              ? "Follow-ups assigned to you will show up here as they come due."
              : "No one has any pending follow-ups right now."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-line bg-white">
          <ul className="divide-y divide-line">
            {followUpsQuery.data!.map((followUp) => {
              const lead = leadById.get(followUp.lead_id);
              const overdue = new Date(followUp.due_at) < new Date();
              return (
                <li key={followUp.id} className="flex items-center justify-between gap-4 px-5 py-4">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{followUp.title}</p>
                    <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-ink/60">
                      {lead && (
                        <Link to={`/leads/${lead.id}`} className="hover:text-brand">
                          {lead.name} · {lead.company}
                        </Link>
                      )}
                      <span className={overdue ? "font-medium text-status-lost" : ""}>
                        Due {new Date(followUp.due_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <FollowUpStatusBadge status={followUp.status} />
                    <Button
                      variant="ghost"
                      onClick={() => cancelMutation.mutate(followUp.id)}
                      disabled={cancelMutation.isPending}
                    >
                      Cancel
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
