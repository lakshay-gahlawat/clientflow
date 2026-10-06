import { SidebarContent } from "./Sidebar";

// Slide-over drawer for small screens — the sidebar has 6 nav items plus
// a user card, which is too dense for a bottom tab bar, so a full drawer
// (rather than a condensed mobile nav) is the right fit here.
export function MobileNav({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
      <div className="absolute inset-0 bg-ink/30" onClick={onClose} aria-hidden="true" />
      <div className="absolute inset-y-0 left-0 w-72 max-w-[80vw] bg-white shadow-xl">
        <SidebarContent onNavigate={onClose} />
      </div>
    </div>
  );
}
