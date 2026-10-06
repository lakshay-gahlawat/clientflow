import { Link, NavLink, useNavigate } from "react-router-dom";
import { useState } from "react";
import { cn } from "../../lib/cn";
import { Avatar } from "../ui/Avatar";
import { useAuth } from "../../auth/AuthContext";
import { useWorkspace } from "../../workspace/WorkspaceContext";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/leads", label: "Leads" },
  { to: "/pipeline", label: "Pipeline" },
  { to: "/follow-ups", label: "Follow-ups" },
  { to: "/team", label: "Team" },
  { to: "/billing", label: "Billing" },
];

function WorkspaceSwitcher() {
  const { currentWorkspace, workspaces, switchWorkspace } = useWorkspace();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);

  if (!currentWorkspace) return null;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left hover:bg-canvas"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <span className="truncate text-sm font-medium text-ink">{currentWorkspace.name}</span>
        <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4 shrink-0 text-ink/40" aria-hidden="true">
          <path d="M6 8l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="absolute left-0 right-0 z-20 mt-1 rounded-lg border border-line bg-white py-1 shadow-lg">
            {workspaces.map((ws) => (
              <button
                key={ws.id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  if (ws.id !== currentWorkspace.id) switchWorkspace(ws.id);
                }}
                className={cn(
                  "block w-full truncate px-3 py-1.5 text-left text-sm hover:bg-canvas",
                  ws.id === currentWorkspace.id ? "font-medium text-brand" : "text-ink"
                )}
              >
                {ws.name}
              </button>
            ))}
            <div className="my-1 border-t border-line" />
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                navigate("/onboarding/workspace");
              }}
              className="block w-full px-3 py-1.5 text-left text-sm text-ink/60 hover:bg-canvas hover:text-ink"
            >
              Create or join another…
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// Shared between the fixed desktop sidebar and the mobile drawer — same
// content, different container, one source of truth for nav structure.
export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 items-center border-b border-line px-4">
        <Link to="/dashboard" className="font-display text-base font-bold text-brand-deep">
          ClientFlow
        </Link>
      </div>

      <div className="border-b border-line px-3 py-3">
        <WorkspaceSwitcher />
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4" aria-label="Primary">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "block rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive ? "bg-brand-light text-brand-deep" : "text-ink/70 hover:bg-canvas hover:text-ink"
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="shrink-0 border-t border-line p-3">
        {user ? (
          <div className="flex items-center gap-2 rounded-lg px-2 py-2">
            <Avatar name={user.full_name} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{user.full_name}</p>
              <p className="truncate text-xs text-ink/60">{user.email}</p>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              className="shrink-0 rounded-md p-1.5 text-ink/50 hover:bg-canvas hover:text-ink"
              aria-label="Log out"
              title="Log out"
            >
              <LogoutIcon />
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-2 py-2" aria-hidden="true">
            <div className="h-8 w-8 animate-pulse rounded-full bg-line" />
            <div className="h-3 flex-1 animate-pulse rounded bg-line" />
          </div>
        )}
      </div>
    </div>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-4 w-4" aria-hidden="true">
      <path
        d="M7.5 17.5H4.5a1 1 0 01-1-1v-13a1 1 0 011-1h3M13.5 14l3.5-4-3.5-4M17 10H7.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 border-r border-line bg-white md:block">
      <SidebarContent />
    </aside>
  );
}
