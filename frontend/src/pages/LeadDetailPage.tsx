import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { useCurrentMembership } from "../hooks/useCurrentMembership";
import { deleteLead, getLead, updateLead, updateLeadStatus, type LeadInput } from "../api/leads";
import { cancelFollowUp, createFollowUp, listFollowUps, type FollowUpInput } from "../api/followUps";
import { STATUS_LABELS, STATUS_ORDER, StatusBadge } from "../components/ui/StatusBadge";
import { FollowUpStatusBadge } from "../components/ui/FollowUpStatusBadge";
import { Button } from "../components/ui/Button";
import { SelectField } from "../components/ui/Field";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState } from "../components/ui/ErrorState";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { LeadFormModal } from "../features/leads/LeadFormModal";
import { FollowUpFormModal } from "../features/followups/FollowUpFormModal";
import { useToast } from "../components/ui/Toast";
import { extractErrorMessage } from "../api/client";
import { invalidateWorkspaceLeads, leadKeys } from "../lib/leadQueries";
import type { Lead, LeadStatus } from "../api/types";

export function LeadDetailPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id;
  const { role: myRole } = useCurrentMembership();
  const canDelete = myRole === "OWNER" || myRole === "ADMIN";
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [followUpFormOpen, setFollowUpFormOpen] = useState(false);

  const leadQuery = useQuery({
    queryKey: leadKeys.detail(workspaceId, leadId),
    queryFn: () => getLead(workspaceId, leadId!),
    enabled: !!leadId,
    placeholderData: (previousData: Lead | undefined) => previousData,
  });

  const invalidateLists = () =>
    invalidateWorkspaceLeads(queryClient, workspaceId, leadId, { refetchDetail: false });

  const statusMutation = useMutation({
    mutationFn: (status: LeadStatus) => updateLeadStatus(workspaceId, leadId!, status),
    onMutate: async (status) => {
      const key = leadKeys.detail(workspaceId, leadId);
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<Lead>(key);
      if (previous) {
        queryClient.setQueryData<Lead>(key, { ...previous, status });
      }
      return { previous };
    },
    onError: (err, _status, context) => {
      if (context?.previous) {
        queryClient.setQueryData(leadKeys.detail(workspaceId, leadId), context.previous);
      }
      showToast(extractErrorMessage(err, "Couldn't update status."), "error");
    },
    onSuccess: (updated) => {
      queryClient.setQueryData(leadKeys.detail(workspaceId, leadId), updated);
      showToast("Status updated.");
    },
    onSettled: () => {
      invalidateLists();
    },
  });

  const updateMutation = useMutation({
    mutationFn: (input: LeadInput) => updateLead(workspaceId, leadId!, input),
    onSuccess: (updated) => {
      queryClient.setQueryData(leadKeys.detail(workspaceId, leadId), updated);
      invalidateLists();
      showToast("Lead updated.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteLead(workspaceId, leadId!),
    onSuccess: () => {
      invalidateWorkspaceLeads(queryClient, workspaceId, leadId);
      showToast("Lead deleted.");
      navigate("/leads", { replace: true });
    },
    onError: (err) => {
      showToast(extractErrorMessage(err, "Couldn't delete this lead."), "error");
      setDeleteOpen(false);
    },
  });

  const followUpsQuery = useQuery({
    queryKey: ["follow-ups", workspaceId, "lead", leadId],
    queryFn: () => listFollowUps(workspaceId, { lead_id: leadId }),
    enabled: !!leadId,
  });

  const createFollowUpMutation = useMutation({
    mutationFn: (input: FollowUpInput) => createFollowUp(workspaceId, leadId!, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups", workspaceId, "lead", leadId] });
      showToast("Follow-up created.");
    },
  });

  const cancelFollowUpMutation = useMutation({
    mutationFn: (followUpId: string) => cancelFollowUp(workspaceId, followUpId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["follow-ups", workspaceId, "lead", leadId] });
      showToast("Follow-up cancelled.");
    },
    onError: (err) => showToast(extractErrorMessage(err, "Couldn't cancel this follow-up."), "error"),
  });

  if (leadQuery.isPending && !leadQuery.data) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (leadQuery.isError) {
    // A workspace member navigating to another workspace's lead ID gets
    // 404 from the backend (Phase 5 tenant isolation) — surfaced here as
    // a plain "not found", not a raw error dump.
    return (
      <ErrorState
        message={extractErrorMessage(leadQuery.error, "This lead couldn't be found.")}
        onRetry={() => void leadQuery.refetch()}
      />
    );
  }

  const lead = leadQuery.data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm">
        <Link to="/leads" className="text-ink/60 hover:text-ink">
          Leads
        </Link>
        <span className="text-ink/30">/</span>
        <span className="text-ink/80">{lead.name}</span>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-2xl font-bold text-ink">{lead.name}</h2>
          <p className="text-sm text-ink/60">{lead.company}</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEditOpen(true)}>
            Edit
          </Button>
          {canDelete && (
            <Button variant="danger" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <div className="space-y-4 rounded-xl border border-line bg-white p-5 md:col-span-2">
          <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink/50">Contact</h3>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-ink/50">Email</dt>
              <dd className="text-ink">{lead.email}</dd>
            </div>
            <div>
              <dt className="text-ink/50">Phone</dt>
              <dd className="text-ink">{lead.phone ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-ink/50">Source</dt>
              <dd className="text-ink">{lead.source ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-ink/50">Created</dt>
              <dd className="text-ink">{new Date(lead.created_at).toLocaleDateString()}</dd>
            </div>
          </dl>

          <div>
            <h4 className="text-sm text-ink/50">Notes</h4>
            <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{lead.notes || "No notes yet."}</p>
          </div>
        </div>

        <div className="space-y-4 rounded-xl border border-line bg-white p-5">
          <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink/50">Status</h3>
          <StatusBadge status={lead.status} className="text-base" />
          <SelectField
            label="Move to"
            htmlFor="status-select"
            value={lead.status}
            onChange={(e) => statusMutation.mutate(e.target.value as LeadStatus)}
            disabled={statusMutation.isPending}
          >
            {STATUS_ORDER.map((status) => (
              <option key={status} value={status}>
                {STATUS_LABELS[status]}
              </option>
            ))}
          </SelectField>
        </div>
      </div>

      <div className="rounded-xl border border-line bg-white p-5">
        <div className="flex items-center justify-between">
          <h3 className="font-display text-sm font-semibold uppercase tracking-wide text-ink/50">Follow-ups</h3>
          <Button variant="secondary" onClick={() => setFollowUpFormOpen(true)}>
            New follow-up
          </Button>
        </div>

        <div className="mt-4">
          {followUpsQuery.isLoading ? (
            <Skeleton className="h-12 w-full rounded-lg" />
          ) : followUpsQuery.data && followUpsQuery.data.length > 0 ? (
            <ul className="divide-y divide-line">
              {followUpsQuery.data.map((followUp) => (
                <li key={followUp.id} className="flex items-center justify-between gap-3 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{followUp.title}</p>
                    <p className="text-xs text-ink/60">
                      Due {new Date(followUp.due_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <FollowUpStatusBadge status={followUp.status} />
                    {followUp.status === "PENDING" && (
                      <Button
                        variant="ghost"
                        onClick={() => cancelFollowUpMutation.mutate(followUp.id)}
                        disabled={cancelFollowUpMutation.isPending}
                      >
                        Cancel
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-ink/50">No follow-ups yet for this lead.</p>
          )}
        </div>
      </div>

      <LeadFormModal
        open={editOpen}
        onClose={() => setEditOpen(false)}
        workspaceId={workspaceId}
        lead={lead}
        onSubmit={async (input) => {
          await updateMutation.mutateAsync(input);
        }}
      />

      <ConfirmDialog
        open={deleteOpen}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => deleteMutation.mutate()}
        title="Delete lead"
        message={`Delete "${lead.name}"? This can't be undone.`}
        confirmLabel="Delete"
        danger
        isLoading={deleteMutation.isPending}
      />

      <FollowUpFormModal
        open={followUpFormOpen}
        onClose={() => setFollowUpFormOpen(false)}
        workspaceId={workspaceId}
        onSubmit={async (input) => {
          await createFollowUpMutation.mutateAsync(input);
        }}
      />
    </div>
  );
}
