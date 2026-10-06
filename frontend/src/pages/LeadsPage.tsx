import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { useCurrentMembership } from "../hooks/useCurrentMembership";
import { createLead, deleteLead, listLeads, updateLead, type LeadInput } from "../api/leads";
import { StatusBadge, STATUS_LABELS, STATUS_ORDER } from "../components/ui/StatusBadge";
import { Button } from "../components/ui/Button";
import { SelectField, InputField } from "../components/ui/Field";
import { Skeleton } from "../components/ui/Skeleton";
import { EmptyState } from "../components/ui/EmptyState";
import { ErrorState } from "../components/ui/ErrorState";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { LeadFormModal } from "../features/leads/LeadFormModal";
import { useToast } from "../components/ui/Toast";
import { extractErrorMessage } from "../api/client";
import { invalidateWorkspaceLeads, leadKeys } from "../lib/leadQueries";
import type { Lead, LeadStatus } from "../api/types";

const PAGE_SIZE = 20;

export function LeadsPage() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id;
  const { role: myRole } = useCurrentMembership();
  const canDelete = myRole === "OWNER" || myRole === "ADMIN";
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<LeadStatus | "">(
    (searchParams.get("status") as LeadStatus | null) ?? "",
  );
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [deletingLead, setDeletingLead] = useState<Lead | null>(null);

  // Deep links: /leads?new=1 opens the create form, /leads?status=X
  // pre-filters (used by the Pipeline board's "view all" links).
  useEffect(() => {
    let changed = false;
    if (searchParams.get("new") === "1") {
      setFormOpen(true);
      searchParams.delete("new");
      changed = true;
    }
    if (searchParams.get("status")) {
      searchParams.delete("status");
      changed = true;
    }
    if (changed) setSearchParams(searchParams, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounce search so every keystroke doesn't fire a request.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const timeout = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(timeout);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, statusFilter]);

  const queryKey = useMemo(
    () => leadKeys.list(workspaceId, { search: debouncedSearch, status: statusFilter, page }),
    [workspaceId, debouncedSearch, statusFilter, page],
  );

  const leadsQuery = useQuery({
    queryKey,
    queryFn: () =>
      listLeads(workspaceId, {
        search: debouncedSearch || undefined,
        status: statusFilter || undefined,
        page,
        page_size: PAGE_SIZE,
        sort_by: "created_at",
        sort_order: "desc",
      }),
    placeholderData: (previousData) => previousData,
  });

  const invalidateLeads = () => invalidateWorkspaceLeads(queryClient, workspaceId);

  const createMutation = useMutation({
    mutationFn: (input: LeadInput) => createLead(workspaceId, input),
    onSuccess: () => {
      invalidateLeads();
      showToast("Lead created.");
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ leadId, input }: { leadId: string; input: LeadInput }) => updateLead(workspaceId, leadId, input),
    onSuccess: () => {
      invalidateLeads();
      showToast("Lead updated.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (leadId: string) => deleteLead(workspaceId, leadId),
    onSuccess: () => {
      invalidateLeads();
      showToast("Lead deleted.");
      setDeletingLead(null);
    },
    onError: (err) => {
      showToast(extractErrorMessage(err, "Couldn't delete this lead."), "error");
      setDeletingLead(null);
    },
  });

  const totalPages = leadsQuery.data ? Math.max(1, Math.ceil(leadsQuery.data.total / PAGE_SIZE)) : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-bold text-ink">Leads</h2>
        <Button
          onClick={() => {
            setEditingLead(null);
            setFormOpen(true);
          }}
        >
          New lead
        </Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <InputField
          label="Search"
          htmlFor="lead-search"
          placeholder="Name, company, or email"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-64"
        />
        <SelectField
          label="Status"
          htmlFor="status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as LeadStatus | "")}
          className="w-44"
        >
          <option value="">All statuses</option>
          {STATUS_ORDER.map((status) => (
            <option key={status} value={status}>
              {STATUS_LABELS[status]}
            </option>
          ))}
        </SelectField>
      </div>

      {leadsQuery.isPending && !leadsQuery.data ? (
        <div className="space-y-2">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : leadsQuery.isError ? (
        <ErrorState
          message={extractErrorMessage(leadsQuery.error, "Couldn't load leads.")}
          onRetry={() => void leadsQuery.refetch()}
        />
      ) : leadsQuery.data!.items.length === 0 ? (
        <EmptyState
          title={debouncedSearch || statusFilter ? "No leads match your filters" : "No leads yet"}
          description={
            debouncedSearch || statusFilter
              ? "Try a different search or status."
              : "Add your first lead to start tracking it through your pipeline."
          }
          action={
            !debouncedSearch && !statusFilter ? (
              <Button
                onClick={() => {
                  setEditingLead(null);
                  setFormOpen(true);
                }}
              >
                Add a lead
              </Button>
            ) : undefined
          }
        />
      ) : (
        <>
          <div className="overflow-hidden rounded-xl border border-line bg-white">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-canvas/50 text-xs uppercase tracking-wide text-ink/50">
                <tr>
                  <th className="px-5 py-3 font-medium">Name</th>
                  <th className="px-5 py-3 font-medium">Company</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {leadsQuery.data!.items.map((lead) => (
                  <tr key={lead.id} className="hover:bg-canvas/40">
                    <td className="px-5 py-3">
                      <Link to={`/leads/${lead.id}`} className="font-medium text-ink hover:text-brand">
                        {lead.name}
                      </Link>
                      <p className="text-xs text-ink/50">{lead.email}</p>
                    </td>
                    <td className="px-5 py-3 text-ink/80">{lead.company}</td>
                    <td className="px-5 py-3">
                      <StatusBadge status={lead.status} />
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-3">
                        <button
                          type="button"
                          className="text-sm font-medium text-ink/60 hover:text-ink"
                          onClick={() => {
                            setEditingLead(lead);
                            setFormOpen(true);
                          }}
                        >
                          Edit
                        </button>
                        {canDelete && (
                          <button
                            type="button"
                            className="text-sm font-medium text-status-lost/80 hover:text-status-lost"
                            onClick={() => setDeletingLead(lead)}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm text-ink/60">
              <span>
                Page {page} of {totalPages} · {leadsQuery.data!.total} total
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
                  Previous
                </Button>
                <Button variant="secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      <LeadFormModal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        workspaceId={workspaceId}
        lead={editingLead}
        onSubmit={async (input) => {
          if (editingLead) {
            await updateMutation.mutateAsync({ leadId: editingLead.id, input });
          } else {
            await createMutation.mutateAsync(input);
          }
        }}
      />

      <ConfirmDialog
        open={!!deletingLead}
        onCancel={() => setDeletingLead(null)}
        onConfirm={() => deletingLead && deleteMutation.mutate(deletingLead.id)}
        title="Delete lead"
        message={`Delete "${deletingLead?.name}"? This can't be undone.`}
        confirmLabel="Delete"
        danger
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
