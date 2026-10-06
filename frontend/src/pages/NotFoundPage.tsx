import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-2 bg-canvas px-4 text-center">
      <p className="font-display text-2xl font-bold text-ink">Page not found</p>
      <p className="text-sm text-ink/60">The page you're looking for doesn't exist.</p>
      <Link to="/dashboard" className="mt-2 text-sm font-medium text-brand hover:underline">
        Back to dashboard
      </Link>
    </div>
  );
}
