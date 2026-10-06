import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useWorkspace } from "../workspace/WorkspaceContext";
import { useCurrentMembership } from "../hooks/useCurrentMembership";
import { createCheckoutSession, getBilling } from "../api/billing";
import { Button } from "../components/ui/Button";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState } from "../components/ui/ErrorState";
import { useToast } from "../components/ui/Toast";
import { extractErrorMessage } from "../api/client";

const STATUS_LABELS: Record<string, string> = {
  ACTIVE: "Active",
  PAST_DUE: "Past due",
  CANCELLED: "Cancelled",
  INCOMPLETE: "Incomplete",
};

export function BillingPage() {
  const { currentWorkspace } = useWorkspace();
  const workspaceId = currentWorkspace!.id;
  const { role: myRole } = useCurrentMembership();
  const { showToast } = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [isRedirecting, setIsRedirecting] = useState(false);

  const billingQuery = useQuery({
    queryKey: ["billing", workspaceId],
    queryFn: () => getBilling(workspaceId),
  });

  // Purely a UX signal from the Stripe Checkout redirect — the actual
  // plan change only ever happens via a verified webhook (see backend
  // billing_service). This just tells the user what happened and lets
  // the query above reflect the real state once the webhook lands.
  useEffect(() => {
    const checkout = searchParams.get("checkout");
    if (checkout === "success") {
      showToast("Payment received — your plan will update shortly.");
      void billingQuery.refetch();
    } else if (checkout === "cancelled") {
      showToast("Checkout cancelled.", "error");
    }
    if (checkout) {
      searchParams.delete("checkout");
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const upgradeMutation = useMutation({
    mutationFn: () => createCheckoutSession(workspaceId),
    onSuccess: (checkoutUrl) => {
      setIsRedirecting(true);
      window.location.href = checkoutUrl;
    },
    onError: (err) => showToast(extractErrorMessage(err, "Couldn't start checkout."), "error"),
  });

  const isOwner = myRole === "OWNER";

  if (billingQuery.isLoading) {
    return <Skeleton className="h-40 w-full max-w-md rounded-xl" />;
  }

  if (billingQuery.isError) {
    return (
      <ErrorState
        message={extractErrorMessage(billingQuery.error, "Couldn't load billing information.")}
        onRetry={() => void billingQuery.refetch()}
      />
    );
  }

  const subscription = billingQuery.data!;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-2xl font-bold text-ink">Billing</h2>
        <p className="mt-1 text-sm text-ink/60">Manage your workspace's plan.</p>
      </div>

      <div className="max-w-md rounded-xl border border-line bg-white p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-display text-lg font-semibold text-ink">
              {subscription.plan === "PRO" ? "Pro" : "Free"} plan
            </p>
            <p className="mt-1 text-sm text-ink/60">
              Status: {STATUS_LABELS[subscription.status] ?? subscription.status}
            </p>
            {subscription.current_period_end && (
              <p className="mt-1 text-xs text-ink/50">
                Renews {new Date(subscription.current_period_end).toLocaleDateString()}
              </p>
            )}
          </div>
        </div>

        {subscription.plan === "FREE" && isOwner && (
          <Button className="mt-5 w-full" onClick={() => upgradeMutation.mutate()} isLoading={isRedirecting}>
            Upgrade to Pro
          </Button>
        )}
        {subscription.plan === "FREE" && !isOwner && (
          <p className="mt-5 text-sm text-ink/50">Only the workspace owner can manage billing.</p>
        )}
      </div>
    </div>
  );
}
