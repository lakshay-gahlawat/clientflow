import { useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { listLeads, updateLeadStatus } from "../api/leads";
import { STATUS_LABELS, STATUS_ORDER } from "../components/ui/StatusBadge";
import { Skeleton } from "../components/ui/Skeleton";
import { useToast } from "../components/ui/Toast";
import { extractErrorMessage } from "../api/client";
import { invalidateWorkspaceLeads, leadKeys } from "../lib/leadQueries";
import type { Lead, LeadStatus, PaginatedLeads } from "../api/types";

const COLUMN_PAGE_SIZE = 50;

let activeDrag: { leadId: string; fromStatus: LeadStatus } | null = null;

function readDragPayload(e: DragEvent): { leadId: string; fromStatus: LeadStatus } | null {
  const raw = e.dataTransfer.getData("application/json") || e.dataTransfer.getData("text/plain");
  if (raw) {
    try {
      const parsed = JSON.parse(raw) as { leadId?: string; fromStatus?: LeadStatus };
      if (parsed.leadId && parsed.fromStatus) return { leadId: parsed.leadId, fromStatus: parsed.fromStatus };
    } catch {
      // Older payload was a bare lead id; fall through to activeDrag.
    }
  }
  return activeDrag;
}

export function PipelinePage() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id;
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [dropTarget, setDropTarget] = useState<LeadStatus | null>(null);

  const columnQueries = useQueries({
    queries: STATUS_ORDER.map((status) => ({
      queryKey: leadKeys.pipeline(workspaceId, status),
      queryFn: () =>
        listLeads(workspaceId, {
          status,
          page: 1,
          page_size: COLUMN_PAGE_SIZE,
          sort_by: "updated_at",
          sort_order: "desc",
        }),
      placeholderData: (previousData: PaginatedLeads | undefined) => previousData,
    })),
  });

  const statusMutation = useMutation({
    mutationFn: ({ leadId, status }: { leadId: string; fromStatus: LeadStatus; status: LeadStatus }) =>
      updateLeadStatus(workspaceId, leadId, status),
    onMutate: async ({ leadId, fromStatus, status }) => {
      if (fromStatus === status) return { previous: [] as { status: LeadStatus; data: PaginatedLeads | undefined }[] };

      await queryClient.cancelQueries({ queryKey: leadKeys.all(workspaceId) });
      const previous = STATUS_ORDER.map((columnStatus) => ({
        status: columnStatus,
        data: queryClient.getQueryData<PaginatedLeads>(leadKeys.pipeline(workspaceId, columnStatus)),
      }));

      let moved: Lead | undefined;
      const sourceKey = leadKeys.pipeline(workspaceId, fromStatus);
      const source = queryClient.getQueryData<PaginatedLeads>(sourceKey);
      if (source) {
        moved = source.items.find((lead) => lead.id === leadId);
        queryClient.setQueryData<PaginatedLeads>(sourceKey, {
          ...source,
          items: source.items.filter((lead) => lead.id !== leadId),
          total: Math.max(0, source.total - 1),
        });
      }

      if (moved) {
        const destKey = leadKeys.pipeline(workspaceId, status);
        const dest = queryClient.getQueryData<PaginatedLeads>(destKey);
        const updated = { ...moved, status };
        if (dest) {
          queryClient.setQueryData<PaginatedLeads>(destKey, {
            ...dest,
            items: [updated, ...dest.items.filter((lead) => lead.id !== leadId)],
            total: dest.total + 1,
          });
        }
      }

      return { previous };
    },
    onError: (err, _vars, context) => {
      context?.previous.forEach(({ status, data }) => {
        queryClient.setQueryData(leadKeys.pipeline(workspaceId, status), data);
      });
      showToast(extractErrorMessage(err, "Couldn't move this lead."), "error");
    },
    onSettled: (_data, _err, vars) => {
      invalidateWorkspaceLeads(queryClient, workspaceId, vars?.leadId);
    },
  });

  const moveLead = (leadId: string, fromStatus: LeadStatus, status: LeadStatus) => {
    if (fromStatus === status) return;
    statusMutation.mutate({ leadId, fromStatus, status });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Pipeline</h2>
        <p className="mt-1 text-sm text-ink/60">
          Drag a card into another stage, or use "Move to". Every stage transition is allowed, same as the API.
        </p>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {STATUS_ORDER.map((status, i) => {
          const query = columnQueries[i];
          const columnData = query?.data;
          const columnPending = query?.isPending && !columnData;
          return (
            <div
              key={status}
              className={`w-72 shrink-0 rounded-xl border bg-white ${
                dropTarget === status ? "border-brand ring-2 ring-brand/30" : "border-line"
              }`}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = "move";
                setDropTarget(status);
              }}
              onDrop={(e) => {
                e.preventDefault();
                setDropTarget(null);
                const drag = readDragPayload(e);
                activeDrag = null;
                if (!drag) return;
                moveLead(drag.leadId, drag.fromStatus, status);
              }}
            >
              <div className="flex items-center justify-between border-b border-line px-4 py-3">
                <span className="text-sm font-semibold text-ink">{STATUS_LABELS[status]}</span>
                <span className="rounded-full bg-canvas px-2 py-0.5 text-xs font-medium text-ink/60">
                  {columnPending ? "…" : columnData?.total ?? 0}
                </span>
              </div>

              <div className="max-h-[60vh] space-y-2 overflow-y-auto p-3">
                {columnPending ? (
                  <>
                    <Skeleton className="h-20 w-full rounded-lg" />
                    <Skeleton className="h-20 w-full rounded-lg" />
                  </>
                ) : columnData && columnData.items.length > 0 ? (
                  columnData.items.map((lead) => {
                    const movingThis =
                      statusMutation.isPending && statusMutation.variables?.leadId === lead.id;
                    return (
                      <div
                        key={lead.id}
                        draggable
                        onDragStart={(e) => {
                          const payload = { leadId: lead.id, fromStatus: lead.status };
                          activeDrag = payload;
                          e.dataTransfer.effectAllowed = "move";
                          e.dataTransfer.setData("application/json", JSON.stringify(payload));
                          e.dataTransfer.setData("text/plain", JSON.stringify(payload));
                        }}
                        onDragEnd={() => {
                          activeDrag = null;
                          setDropTarget(null);
                        }}
                        className={`cursor-grab rounded-lg border border-line p-3 active:cursor-grabbing ${
                          movingThis ? "opacity-60" : ""
                        }`}
                      >
                        <Link
                          to={`/leads/${lead.id}`}
                          draggable={false}
                          className="text-sm font-medium text-ink hover:text-brand"
                        >
                          {lead.name}
                        </Link>
                        <p className="truncate text-xs text-ink/60">{lead.company}</p>
                        <select
                          aria-label={`Move ${lead.name} to a different stage`}
                          className="mt-2 w-full rounded-md border border-line bg-white px-2 py-1 text-xs text-ink focus:border-brand"
                          value={lead.status}
                          draggable={false}
                          onPointerDown={(e) => e.stopPropagation()}
                          onChange={(e) =>
                            moveLead(lead.id, lead.status, e.target.value as LeadStatus)
                          }
                          disabled={movingThis}
                        >
                          {STATUS_ORDER.map((s) => (
                            <option key={s} value={s}>
                              Move to {STATUS_LABELS[s]}
                            </option>
                          ))}
                        </select>
                      </div>
                    );
                  })
                ) : (
                  <p className="px-1 py-6 text-center text-xs text-ink/40">No leads here</p>
                )}
                {columnData && columnData.total > COLUMN_PAGE_SIZE && (
                  <Link
                    to={`/leads?status=${status}`}
                    className="block px-1 py-1 text-center text-xs font-medium text-brand hover:underline"
                  >
                    +{columnData.total - COLUMN_PAGE_SIZE} more — view all
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
