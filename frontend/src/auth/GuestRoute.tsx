import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "./AuthContext";

// The inverse of ProtectedRoute: /login and /register should bounce an
// already-authenticated user straight to the app, not show them a login
// form for a session they already have.
export function GuestRoute() {
  const { isAuthenticated, isLoading } = useAuth();

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

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
