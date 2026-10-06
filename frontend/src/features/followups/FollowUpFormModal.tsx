import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Modal } from "../../components/ui/Modal";
import { InputField, SelectField } from "../../components/ui/Field";
import { Button } from "../../components/ui/Button";
import { listMembers } from "../../api/workspaces";
import { extractErrorMessage } from "../../api/client";
import { useCurrentMembership } from "../../hooks/useCurrentMembership";
import type { FollowUpInput } from "../../api/followUps";

// Local datetime-input helper: <input type="datetime-local"> needs
// "YYYY-MM-DDTHH:mm" in the user's local time, with no timezone suffix.
function defaultDueAt(): string {
  const d = new Date(Date.now() + 24 * 60 * 60 * 1000); // tomorrow, same time
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function FollowUpFormModal({
  open,
  onClose,
  onSubmit,
  workspaceId,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: FollowUpInput) => Promise<void>;
  workspaceId: string;
}) {
  const { role: myRole } = useCurrentMembership();
  const canAssignOthers = myRole === "OWNER" || myRole === "ADMIN";

  const [title, setTitle] = useState("");
  const [dueAt, setDueAt] = useState(defaultDueAt());
  const [assignedTo, setAssignedTo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const membersQuery = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => listMembers(workspaceId),
    enabled: open && canAssignOthers,
  });

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (title.trim().length === 0) {
      setError("Title is required.");
      return;
    }
    setIsSubmitting(true);
    try {
      await onSubmit({
        title: title.trim(),
        due_at: new Date(dueAt).toISOString(),
        assigned_to: assignedTo || null,
      });
      setTitle("");
      setDueAt(defaultDueAt());
      setAssignedTo("");
      onClose();
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't create this follow-up."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="New follow-up">
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <InputField
          label="Title"
          htmlFor="fu-title"
          required
          placeholder="e.g. Send pricing proposal"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={isSubmitting}
        />
        <InputField
          label="Due"
          htmlFor="fu-due"
          type="datetime-local"
          required
          value={dueAt}
          onChange={(e) => setDueAt(e.target.value)}
          disabled={isSubmitting}
        />
        {canAssignOthers && (
          <SelectField
            label="Assigned to"
            htmlFor="fu-assigned"
            value={assignedTo}
            onChange={(e) => setAssignedTo(e.target.value)}
            disabled={isSubmitting || membersQuery.isLoading}
          >
            <option value="">Me</option>
            {membersQuery.data?.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.full_name}
              </option>
            ))}
          </SelectField>
        )}
        {error && (
          <p className="rounded-lg bg-status-lost/10 px-3 py-2 text-sm text-status-lost" role="alert">
            {error}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting}>
            Create follow-up
          </Button>
        </div>
      </form>
    </Modal>
  );
}
