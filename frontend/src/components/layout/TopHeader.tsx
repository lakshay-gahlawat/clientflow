export function TopHeader({ title, onOpenMenu }: { title: string; onOpenMenu: () => void }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line bg-white px-4 md:px-6">
      <button
        type="button"
        onClick={onOpenMenu}
        className="rounded-md p-1.5 text-ink/60 hover:bg-canvas hover:text-ink md:hidden"
        aria-label="Open navigation"
      >
        <MenuIcon />
      </button>
      <h1 className="truncate font-display text-base font-semibold text-ink">{title}</h1>
    </header>
  );
}

function MenuIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" className="h-5 w-5" aria-hidden="true">
      <path
        d="M3 6h14M3 10h14M3 14h14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
