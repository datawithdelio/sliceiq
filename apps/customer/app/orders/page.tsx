"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

import { OrderCard, OrderSummary } from "@/components/orders/OrderCard";

export default function OrdersHistoryPage() {
  const { getToken, isLoaded } = useAuth();
  const router = useRouter();

  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded) return;

    let active = true;

    (async () => {
      const token = await getToken();
      if (!token || !active) return;

      const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${backendUrl}/orders/history`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!active) return;

      if (!resp.ok) {
        setError("Unable to load order history.");
        setLoading(false);
        return;
      }

      const data = (await resp.json()) as OrderSummary[];
      setOrders(data);
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, [getToken, isLoaded]);

  const handleReorder = async (orderId: string) => {
    const token = await getToken();
    if (!token) return;

    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const resp = await fetch(`${backendUrl}/orders/${orderId}/reorder`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!resp.ok) {
      setError("Unable to re-order at this time.");
      return;
    }

    const data = await resp.json();
    try {
      localStorage.setItem("sliceiq:prefill_cart", JSON.stringify(data.items || []));
    } catch {
      // ignore storage errors
    }

    router.push("/cart");
  };

  if (loading) {
    return (
      <div className="mx-auto flex w-full max-w-4xl items-center justify-center px-6 py-16 text-sm text-neutral-500">
        Loading orders...
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-6 py-16">
        <div className="text-sm text-red-600">{error}</div>
        <Link
          href="/"
          className="w-fit rounded-full bg-orange-500 px-4 py-2 text-sm font-semibold text-white"
        >
          Back to Home
        </Link>
      </div>
    );
  }

  if (orders.length === 0) {
    return (
      <div className="mx-auto flex w-full max-w-4xl flex-col items-center gap-4 px-6 py-16 text-center">
        <h1 className="text-2xl font-semibold">You haven’t ordered anything yet!</h1>
        <p className="text-sm text-neutral-500">Start your first SliceIQ order now.</p>
        <Link
          href="/"
          className="rounded-full bg-orange-500 px-4 py-2 text-sm font-semibold text-white"
        >
          Start Ordering
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-10">
      <div>
        <h1 className="text-2xl font-semibold">Your Orders</h1>
        <p className="text-sm text-neutral-500">Track your favorites and re-order in one click.</p>
      </div>
      <div className="flex flex-col gap-4">
        {orders.map((order) => (
          <OrderCard key={order.id} order={order} onReorder={handleReorder} />
        ))}
      </div>
    </div>
  );
}
