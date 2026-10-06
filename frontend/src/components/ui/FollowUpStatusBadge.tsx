import type { FollowUpStatus } from "../../api/types";
import { cn } from "../../lib/cn";

const LABELS: Record<FollowUpStatus, string> = {
  PENDING: "Pending",
  PROCESSING: "Sending",
  SENT: "Sent",
  CANCELLED: "Cancelled",
};

const DOT_CLASSES: Record<FollowUpStatus, string> = {
  PENDING: "bg-status-proposal",
  PROCESSING: "bg-status-contacted",
  SENT: "bg-status-won",
  CANCELLED: "bg-ink/30",
};

export function FollowUpStatusBadge({ status }: { status: FollowUpStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-ink/70">
      <span className={cn("h-1.5 w-1.5 rounded-full", DOT_CLASSES[status])} aria-hidden="true" />
      {LABELS[status]}
    </span>
  );
}
