import { Button } from "./Button";

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-status-lost/30 bg-status-lost/5 px-6 py-16 text-center">
      <p className="font-display text-base font-semibold text-ink">Couldn't load this</p>
      <p className="mt-1 max-w-sm text-sm text-ink/60">{message}</p>
      {onRetry && (
        <Button variant="secondary" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
