import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { extractErrorMessage } from "../api/client";
import { InputField } from "../components/ui/Field";
import { Button } from "../components/ui/Button";
import { useToast } from "../components/ui/Toast";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
}

export function OnboardingWorkspacePage() {
  const { createWorkspace, joinWorkspace, currentWorkspace, isLoading } = useWorkspace();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"create" | "join">("create");

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugTouched, setSlugTouched] = useState(false);
  const [joinId, setJoinId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleNameChange = (value: string) => {
    setName(value);
    if (!slugTouched) setSlug(slugify(value));
  };

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await createWorkspace(name.trim(), slug);
      showToast(`${name} is ready.`);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err, "Couldn't create the workspace."));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleJoin = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const workspace = await joinWorkspace(joinId.trim());
      showToast(`Switched to ${workspace.name}.`);
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(
        extractErrorMessage(
          err,
          "Couldn't find that workspace — check the ID and make sure you've been added as a member.",
        ),
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-canvas">
        <div
          className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-brand"
          role="status"
          aria-label="Loading"
        />
      </div>
    );
  }

  if (currentWorkspace) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-md rounded-xl border border-line bg-white p-8 shadow-sm">
        <h1 className="font-display text-xl font-bold text-ink">Set up your workspace</h1>
        <p className="mt-1 text-sm text-ink/60">
          Every lead and teammate lives inside a workspace. Create a new one, or join an existing one if a
          teammate has already added you.
        </p>

        <div className="mt-6 flex gap-1 rounded-lg bg-canvas p-1">
          <button
            type="button"
            onClick={() => setMode("create")}
            className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors ${
              mode === "create" ? "bg-white text-ink shadow-sm" : "text-ink/60"
            }`}
          >
            Create new
          </button>
          <button
            type="button"
            onClick={() => setMode("join")}
            className={`flex-1 rounded-md py-1.5 text-sm font-medium transition-colors ${
              mode === "join" ? "bg-white text-ink shadow-sm" : "text-ink/60"
            }`}
          >
            Join existing
          </button>
        </div>

        {mode === "create" ? (
          <form onSubmit={handleCreate} className="mt-6 space-y-4" noValidate>
            <InputField
              label="Workspace name"
              htmlFor="ws-name"
              required
              placeholder="Acme Inc"
              value={name}
              onChange={(e) => handleNameChange(e.target.value)}
              disabled={isSubmitting}
            />
            <InputField
              label="Workspace URL slug"
              htmlFor="ws-slug"
              required
              pattern="^[a-z0-9-]+$"
              title="Lowercase letters, numbers, and hyphens only"
              value={slug}
              onChange={(e) => {
                setSlugTouched(true);
                setSlug(e.target.value);
              }}
              disabled={isSubmitting}
            />
            {error && (
              <p className="rounded-lg bg-status-lost/10 px-3 py-2 text-sm text-status-lost" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" isLoading={isSubmitting}>
              Create workspace
            </Button>
          </form>
        ) : (
          <form onSubmit={handleJoin} className="mt-6 space-y-4" noValidate>
            <InputField
              label="Workspace ID"
              htmlFor="join-id"
              required
              placeholder="Ask a teammate for this"
              value={joinId}
              onChange={(e) => setJoinId(e.target.value)}
              disabled={isSubmitting}
            />
            {error && (
              <p className="rounded-lg bg-status-lost/10 px-3 py-2 text-sm text-status-lost" role="alert">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full" isLoading={isSubmitting}>
              Join workspace
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
