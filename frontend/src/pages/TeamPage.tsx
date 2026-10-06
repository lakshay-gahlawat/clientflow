import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { useCurrentMembership } from "../hooks/useCurrentMembership";
import { addMember, listMembers, removeMember, updateMemberRole } from "../api/workspaces";
import { Avatar } from "../components/ui/Avatar";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { InputField, SelectField } from "../components/ui/Field";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState } from "../components/ui/ErrorState";
import { useToast } from "../components/ui/Toast";
import { extractErrorMessage } from "../api/client";
import type { WorkspaceMember, WorkspaceRole } from "../api/types";

export function TeamPage() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id;
  const { role: myRole } = useCurrentMembership();
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [inviteOpen, setInviteOpen] = useState(false);
  const [removingMember, setRemovingMember] = useState<WorkspaceMember | null>(null);

  const membersQuery = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => listMembers(workspaceId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["workspace-members", workspaceId] });

  const removeMutation = useMutation({
    mutationFn: (memberId: string) => removeMember(workspaceId, memberId),
    onSuccess: () => {
      invalidate();
      showToast("Member removed.");
      setRemovingMember(null);
    },
    onError: (err) => {
      showToast(extractErrorMessage(err, "Couldn't remove this member."), "error");
      setRemovingMember(null);
    },
  });

  const roleMutation = useMutation({
    mutationFn: ({ memberId, role }: { memberId: string; role: WorkspaceRole }) =>
      updateMemberRole(workspaceId, memberId, role),
    onSuccess: () => {
      invalidate();
      showToast("Role updated.");
    },
    onError: (err) => showToast(extractErrorMessage(err, "Couldn't update role."), "error"),
  });

  // OWNER + ADMIN can manage the team; MEMBER cannot — mirrors the
  // backend's actual permission matrix (Phase 4), just kept in sync here
  // for the UI, not as the enforcement point.
  const canManageMembers = myRole === "OWNER" || myRole === "ADMIN";
  const canChangeRoles = myRole === "OWNER";

  if (membersQuery.isLoading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-14 w-full rounded-xl" />
        ))}
      </div>
    );
  }

  if (membersQuery.isError) {
    return (
      <ErrorState
        message={extractErrorMessage(membersQuery.error, "Couldn't load team members.")}
        onRetry={() => void membersQuery.refetch()}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-2xl font-bold text-ink">Team</h2>
        {canManageMembers && <Button onClick={() => setInviteOpen(true)}>Add member</Button>}
      </div>

      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <ul className="divide-y divide-line">
          {membersQuery.data!.map((member) => (
            <li key={member.id} className="flex items-center justify-between gap-4 px-5 py-4">
              <div className="flex min-w-0 items-center gap-3">
                <Avatar name={member.full_name} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{member.full_name}</p>
                  <p className="truncate text-xs text-ink/60">{member.email}</p>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-3">
                {canChangeRoles && member.role !== "OWNER" ? (
                  <select
                    aria-label={`Change role for ${member.full_name}`}
                    className="rounded-md border border-line bg-white px-2 py-1 text-xs text-ink focus:border-brand"
                    value={member.role}
                    onChange={(e) =>
                      roleMutation.mutate({ memberId: member.id, role: e.target.value as WorkspaceRole })
                    }
                    disabled={roleMutation.isPending}
                  >
                    <option value="ADMIN">Admin</option>
                    <option value="MEMBER">Member</option>
                  </select>
                ) : (
                  <span className="rounded-full bg-canvas px-2.5 py-1 text-xs font-medium text-ink/70">
                    {member.role === "OWNER" ? "Owner" : member.role === "ADMIN" ? "Admin" : "Member"}
                  </span>
                )}

                {canManageMembers && member.role !== "OWNER" && (
                  <button
                    type="button"
                    className="text-sm font-medium text-status-lost/80 hover:text-status-lost"
                    onClick={() => setRemovingMember(member)}
                  >
                    Remove
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>

      <InviteMemberModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        workspaceId={workspaceId}
        onInvited={invalidate}
      />

      <ConfirmDialog
        open={!!removingMember}
        onCancel={() => setRemovingMember(null)}
        onConfirm={() => removingMember && removeMutation.mutate(removingMember.id)}
        title="Remove member"
        message={`Remove ${removingMember?.full_name} from ${currentWorkspace!.name}? They'll lose access to this workspace immediately.`}
        confirmLabel="Remove"
        danger
        isLoading={removeMutation.isPending}
      />
    </div>
  );
}

function InviteMemberModal({
  open,
  onClose,
  workspaceId,
  onInvited,
}: {
  open: boolean;
  onClose: () => void;
  workspaceId: string;
  onInvited: () => void;
}) {
  const { showToast } = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<WorkspaceRole>("MEMBER");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await addMember(workspaceId, email.trim(), role);
      onInvited();
      showToast("Member added.");
      setEmail("");
      setRole("MEMBER");
      onClose();
    } catch (err) {
      setError(
        extractErrorMessage(
          err,
          "Couldn't add this member — make sure they've already registered a ClientFlow account.",
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Add team member">
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <InputField
          label="Email"
          htmlFor="invite-email"
          type="email"
          required
          placeholder="teammate@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isSubmitting}
        />
        <SelectField
          label="Role"
          htmlFor="invite-role"
          value={role}
          onChange={(e) => setRole(e.target.value as WorkspaceRole)}
          disabled={isSubmitting}
        >
          <option value="MEMBER">Member</option>
          <option value="ADMIN">Admin</option>
        </SelectField>
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
            Add member
          </Button>
        </div>
      </form>
    </Modal>
  );
}
