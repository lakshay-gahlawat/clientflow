import { Navigate, Outlet } from "react-router-dom";
import { useWorkspace } from "./WorkspaceContext";

// Sits inside ProtectedRoute: an authenticated user with no current
// workspace (first login, or their remembered workspace ID failed
// re-verification) gets routed to onboarding instead of a broken
// workspace-scoped page.
export function WorkspaceGate() {
  const { currentWorkspace, isLoading } = useWorkspace();

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

  if (!currentWorkspace) {
    return <Navigate to="/onboarding/workspace" replace />;
  }

  return <Outlet />;
}
