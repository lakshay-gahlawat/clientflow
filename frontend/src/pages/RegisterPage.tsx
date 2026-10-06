import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { extractErrorMessage } from "../api/client";
import { InputField } from "../components/ui/Field";
import { Button } from "../components/ui/Button";

interface FieldErrors {
  fullName?: string;
  email?: string;
  password?: string;
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const validate = (): boolean => {
    const errors: FieldErrors = {};
    if (fullName.trim().length === 0) errors.fullName = "Full name is required.";
    if (!/^\S+@\S+\.\S+$/.test(email)) errors.email = "Enter a valid email address.";
    // Mirrors the backend's actual constraints (RegisterRequest schema,
    // Phase 4): 8 char minimum, 72-byte bcrypt ceiling — not an arbitrary
    // frontend-only rule.
    if (password.length < 8) errors.password = "Password must be at least 8 characters.";
    else if (new TextEncoder().encode(password).length > 72) errors.password = "Password is too long.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    if (!validate()) return;

    setIsSubmitting(true);
    try {
      await register(email, password, fullName);
      navigate("/onboarding/workspace", { replace: true });
    } catch (err) {
      setFormError(extractErrorMessage(err, "Couldn't create your account. Please try again."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <div className="w-full max-w-sm rounded-xl border border-line bg-white p-8 shadow-sm">
        <h1 className="font-display text-xl font-bold text-ink">Create your account</h1>
        <p className="mt-1 text-sm text-ink/60">Start managing leads in minutes.</p>

        <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
          <InputField
            label="Full name"
            htmlFor="fullName"
            autoComplete="name"
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            error={fieldErrors.fullName}
            disabled={isSubmitting}
          />
          <InputField
            label="Email"
            htmlFor="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={fieldErrors.email}
            disabled={isSubmitting}
          />
          <InputField
            label="Password"
            htmlFor="password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={fieldErrors.password}
            disabled={isSubmitting}
          />

          {formError && (
            <p className="rounded-lg bg-status-lost/10 px-3 py-2 text-sm text-status-lost" role="alert">
              {formError}
            </p>
          )}

          <Button type="submit" className="w-full" isLoading={isSubmitting}>
            Create account
          </Button>
        </form>

        <p className="mt-6 text-center text-sm text-ink/60">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
