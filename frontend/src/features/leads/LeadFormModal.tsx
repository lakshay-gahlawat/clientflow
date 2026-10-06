import { useEffect, useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Modal } from "../../components/ui/Modal";
import { InputField, SelectField, TextareaField } from "../../components/ui/Field";
import { Button } from "../../components/ui/Button";
import { listMembers } from "../../api/workspaces";
import { extractErrorMessage } from "../../api/client";
import type { Lead } from "../../api/types";
import type { LeadInput } from "../../api/leads";

interface FieldErrors {
  name?: string;
  company?: string;
  email?: string;
}

export function LeadFormModal({
  open,
  onClose,
  onSubmit,
  workspaceId,
  lead,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (input: LeadInput) => Promise<void>;
  workspaceId: string;
  lead?: Lead | null;
}) {
  const isEdit = !!lead;

  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [source, setSource] = useState("");
  const [notes, setNotes] = useState("");
  const [assignedTo, setAssignedTo] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const membersQuery = useQuery({
    queryKey: ["workspace-members", workspaceId],
    queryFn: () => listMembers(workspaceId),
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    setName(lead?.name ?? "");
    setCompany(lead?.company ?? "");
    setEmail(lead?.email ?? "");
    setPhone(lead?.phone ?? "");
    setSource(lead?.source ?? "");
    setNotes(lead?.notes ?? "");
    setAssignedTo(lead?.assigned_to ?? "");
    setFieldErrors({});
    setFormError(null);
    // Re-seed when the modal opens or the lead identity changes — not on
    // every parent refetch of the same lead (that reset the form mid-edit
    // and flashed the fields).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, lead?.id]);

  const validate = (): boolean => {
    const errors: FieldErrors = {};
    if (name.trim().length === 0) errors.name = "Name is required.";
    if (company.trim().length === 0) errors.company = "Company is required.";
    if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = "Enter a valid email address.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await onSubmit({
        name: name.trim(),
        company: company.trim(),
        email: email.trim(),
        phone: phone.trim() || null,
        source: source.trim() || null,
        notes: notes.trim() || null,
        assigned_to: assignedTo || null,
      });
      onClose();
    } catch (err) {
      setFormError(extractErrorMessage(err, "Couldn't save this lead."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? "Edit lead" : "New lead"}>
      <form onSubmit={handleSubmit} className="space-y-4" noValidate>
        <div className="grid grid-cols-2 gap-4">
          <InputField
            label="Name"
            htmlFor="lead-name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={fieldErrors.name}
            disabled={isSubmitting}
          />
          <InputField
            label="Company"
            htmlFor="lead-company"
            required
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            error={fieldErrors.company}
            disabled={isSubmitting}
          />
        </div>
        <InputField
          label="Email"
          htmlFor="lead-email"
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldErrors.email}
          disabled={isSubmitting}
        />
        <div className="grid grid-cols-2 gap-4">
          <InputField
            label="Phone"
            htmlFor="lead-phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            disabled={isSubmitting}
          />
          <InputField
            label="Source"
            htmlFor="lead-source"
            placeholder="e.g. Referral"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            disabled={isSubmitting}
          />
        </div>
        <SelectField
          label="Assigned to"
          htmlFor="lead-assigned"
          value={assignedTo}
          onChange={(e) => setAssignedTo(e.target.value)}
          disabled={isSubmitting || membersQuery.isLoading}
        >
          <option value="">Unassigned</option>
          {membersQuery.data?.map((member) => (
            <option key={member.user_id} value={member.user_id}>
              {member.full_name}
            </option>
          ))}
        </SelectField>
        <TextareaField
          label="Notes"
          htmlFor="lead-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isSubmitting}
        />

        {formError && (
          <p className="rounded-lg bg-status-lost/10 px-3 py-2 text-sm text-status-lost" role="alert">
            {formError}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSubmitting}>
            {isEdit ? "Save changes" : "Create lead"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
