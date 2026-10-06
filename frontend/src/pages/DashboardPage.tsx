import { Link } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { listLeads } from "../api/leads";
import { STATUS_ORDER, StatusBadge } from "../components/ui/StatusBadge";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState } from "../components/ui/ErrorState";
import { EmptyState } from "../components/ui/EmptyState";
import { Button } from "../components/ui/Button";
import { extractErrorMessage } from "../api/client";
import { leadKeys } from "../lib/leadQueries";

export function DashboardPage() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id; // WorkspaceGate guarantees this is non-null here

  // page_size=1 on each of these: we only need the `total` field the
  // pagination endpoint already returns — not the actual rows — so this
  // stays cheap regardless of how many leads exist. This is real
  // aggregate data derived from the existing API, not invented analytics.
  const totalQuery = useQuery({
    queryKey: leadKeys.total(workspaceId),
    queryFn: () => listLeads(workspaceId, { page: 1, page_size: 1 }),
    placeholderData: (previousData) => previousData,
  });

  const statusQueries = useQueries({
    queries: STATUS_ORDER.map((status) => ({
      queryKey: leadKeys.count(workspaceId, status),
      queryFn: () => listLeads(workspaceId, { status, page: 1, page_size: 1 }),
      placeholderData: (previousData: { total: number } | undefined) => previousData,
    })),
  });

  const recentQuery = useQuery({
    queryKey: leadKeys.recent(workspaceId),
    queryFn: () => listLeads(workspaceId, { page: 1, page_size: 5, sort_by: "created_at", sort_order: "desc" }),
    placeholderData: (previousData) => previousData,
  });

  const countsPending = totalQuery.isPending && !totalQuery.data;
  const recentPending = recentQuery.isPending && !recentQuery.data;
  const firstError = totalQuery.error ?? statusQueries.find((q) => q.error)?.error ?? recentQuery.error;

  if (firstError) {
    return (
      <ErrorState
        message={extractErrorMessage(firstError, "Couldn't load your dashboard.")}
        onRetry={() => {
          void totalQuery.refetch();
          void recentQuery.refetch();
        }}
      />
    );
  }

  const totalLeads = totalQuery.data?.total ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">{currentWorkspace!.name}</h2>
        <p className="mt-1 text-sm text-ink/60">Here's what's happening with your pipeline.</p>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link to="/leads?new=1">
          <Button>New lead</Button>
        </Link>
        <Link to="/pipeline">
          <Button variant="secondary">View pipeline</Button>
        </Link>
      </div>

      <section>
        <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink/50">Overview</h3>
        <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
          <div className="rounded-xl border border-line bg-white p-5">
            <p className="text-sm text-ink/60">Total leads</p>
            {countsPending ? (
              <Skeleton className="mt-2 h-8 w-16" />
            ) : (
              <p className="mt-1 font-display text-3xl font-bold text-ink">{totalLeads}</p>
            )}
          </div>
          {STATUS_ORDER.map((status, i) => (
            <div key={status} className="rounded-xl border border-line bg-white p-5">
              <StatusBadge status={status} />
              {statusQueries[i]?.isPending && !statusQueries[i]?.data ? (
                <Skeleton className="mt-2 h-8 w-12" />
              ) : (
                <p className="mt-1 font-display text-3xl font-bold text-ink">
                  {statusQueries[i]?.data?.total ?? 0}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between">
          <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink/50">Recent leads</h3>
          <Link to="/leads" className="text-sm font-medium text-brand hover:underline">
            View all
          </Link>
        </div>

        <div className="mt-3 overflow-hidden rounded-xl border border-line bg-white">
          {recentPending ? (
            <div className="divide-y divide-line">
              {[1, 2, 3].map((i) => (
                <div key={i} className="flex items-center justify-between px-5 py-4">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-4 w-20" />
                </div>
              ))}
            </div>
          ) : recentQuery.data && recentQuery.data.items.length > 0 ? (
            <div className="divide-y divide-line">
              {recentQuery.data.items.map((lead) => (
                <Link
                  key={lead.id}
                  to={`/leads/${lead.id}`}
                  className="flex items-center justify-between px-5 py-4 hover:bg-canvas"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{lead.name}</p>
                    <p className="truncate text-xs text-ink/60">{lead.company}</p>
                  </div>
                  <StatusBadge status={lead.status} />
                </Link>
              ))}
            </div>
          ) : (
            <div className="p-2">
              <EmptyState
                title="No leads yet"
                description="Add your first lead to start tracking it through your pipeline."
                action={
                  <Link to="/leads?new=1">
                    <Button>Add a lead</Button>
                  </Link>
                }
              />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
