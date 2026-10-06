import type { LeadStatus } from "../../api/types";
import { cn } from "../../lib/cn";

export const STATUS_LABELS: Record<LeadStatus, string> = {
  NEW: "New",
  CONTACTED: "Contacted",
  QUALIFIED: "Qualified",
  PROPOSAL: "Proposal",
  WON: "Won",
  LOST: "Lost",
};

export const STATUS_ORDER: LeadStatus[] = ["NEW", "CONTACTED", "QUALIFIED", "PROPOSAL", "WON", "LOST"];

const DOT_CLASSES: Record<LeadStatus, string> = {
  NEW: "bg-status-new",
  CONTACTED: "bg-status-contacted",
  QUALIFIED: "bg-status-qualified",
  PROPOSAL: "bg-status-proposal",
  WON: "bg-status-won",
  LOST: "bg-status-lost",
};

const TEXT_CLASSES: Record<LeadStatus, string> = {
  NEW: "text-status-new",
  CONTACTED: "text-status-contacted",
  QUALIFIED: "text-status-qualified",
  PROPOSAL: "text-status-proposal",
  WON: "text-status-won",
  LOST: "text-status-lost",
};

// The one consistent piece of color-coding used everywhere a lead's
// status appears — lead rows, lead detail, pipeline board, dashboard
// summary — so pipeline health is scannable at a glance across the app.
export function StatusBadge({ status, className }: { status: LeadStatus; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-sm font-medium", TEXT_CLASSES[status], className)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASSES[status])} aria-hidden="true" />
      {STATUS_LABELS[status]}
    </span>
  );
}
