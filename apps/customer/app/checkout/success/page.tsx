"use client";

import { useAuth } from "@clerk/nextjs";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function CheckoutSuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { getToken, isLoaded } = useAuth();

  const sessionId = searchParams.get("session_id");
  const orderId = searchParams.get("order_id");

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;
    if (!sessionId || !orderId) {
      setError("Missing checkout session information.");
      return;
    }

    let active = true;

    (async () => {
      const token = await getToken();
      if (!token || !active) return;

      const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${backendUrl}/payments/verify/${sessionId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!active) return;

      if (resp.ok) {
        router.push(`/orders/${orderId}`);
        return;
      }

      const payload = await resp.json().catch(() => ({}));
      const detail = typeof payload.detail === "string" ? payload.detail : "Payment verification failed.";
      setError(detail);
    })();

    return () => {
      active = false;
    };
  }, [getToken, isLoaded, orderId, router, sessionId]);

  return (
    <div className="mx-auto flex min-h-[60vh] w-full max-w-xl flex-col items-center justify-center gap-4 px-6 py-12 text-center">
      {!error ? (
        <>
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-neutral-200 border-t-orange-500" />
          <h1 className="text-xl font-semibold">Verifying your payment...</h1>
          <p className="text-sm text-neutral-500">We’ll send you to your live order tracker shortly.</p>
        </>
      ) : (
        <>
          <h1 className="text-xl font-semibold">We couldn’t verify your payment</h1>
          <p className="text-sm text-neutral-500">{error}</p>
          <button
            type="button"
            onClick={() => (window.location.href = "mailto:support@sliceiq.com")}
            className="rounded-full bg-orange-500 px-4 py-2 text-sm font-semibold text-white"
          >
            Contact Support
          </button>
        </>
      )}
    </div>
  );
}
