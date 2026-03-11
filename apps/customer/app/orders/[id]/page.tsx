"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { OrderTracker, OrderStatus } from "@/components/orders/OrderTracker";
import { useSocket } from "@/app/providers/SocketProvider";

type OrderItem = {
  id?: string;
  product_id?: string;
  name?: string;
  quantity?: number;
  unit_price?: number | string;
};

type OrderData = {
  id: string;
  status: OrderStatus;
  total_amount: number | string;
  delivery_address: Record<string, unknown>;
  items?: OrderItem[];
};

const statusFallback: OrderStatus = "pending";

export default function OrderTrackingPage() {
  const params = useParams<{ id: string }>();
  const orderId = params?.id ?? "";
  const { getToken, isLoaded } = useAuth();
  const { latestOrderUpdate, isConnected } = useSocket();

  const [order, setOrder] = useState<OrderData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoaded || !orderId) return;

    let active = true;

    (async () => {
      const token = await getToken();
      if (!token || !active) return;

      const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const resp = await fetch(`${backendUrl}/orders/${orderId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!resp.ok) {
        if (active) {
          setOrder(null);
          setLoading(false);
        }
        return;
      }

      const data = (await resp.json()) as OrderData;
      if (active) {
        setOrder(data);
        setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, [getToken, isLoaded, orderId]);

  useEffect(() => {
    if (!latestOrderUpdate || latestOrderUpdate.order_id !== orderId) return;
    setOrder((prev) =>
      prev
        ? {
            ...prev,
            status: latestOrderUpdate.status as OrderStatus,
          }
        : prev
    );
  }, [latestOrderUpdate, orderId]);

  const status = order?.status ?? statusFallback;

  const addressLines = useMemo(() => {
    if (!order?.delivery_address) return [];
    return Object.entries(order.delivery_address)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .filter(Boolean);
  }, [order?.delivery_address]);

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-6 px-6 py-10">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Order Tracking</h1>
          <p className="text-sm text-neutral-500">Order ID: {orderId}</p>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={
              "h-2.5 w-2.5 rounded-full " +
              (isConnected ? "bg-green-500 animate-pulse" : "bg-neutral-300")
            }
          />
          <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">
            {isConnected ? "Live" : "Offline"}
          </span>
        </div>
      </div>

      <OrderTracker status={status} />

      {loading && <div className="text-sm text-neutral-500">Loading order...</div>}

      {!loading && !order && (
        <div className="rounded-xl border border-neutral-200 p-4 text-sm text-neutral-600">
          Unable to load order details.
        </div>
      )}

      {!loading && order && (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-neutral-200 p-4">
            <div className="text-sm font-semibold">Summary</div>
            <div className="mt-2 text-sm text-neutral-600">Status: {order.status}</div>
            <div className="text-sm text-neutral-600">
              Total: ${Number(order.total_amount).toFixed(2)}
            </div>
          </div>

          <div className="rounded-xl border border-neutral-200 p-4">
            <div className="text-sm font-semibold">Delivery Address</div>
            <ul className="mt-2 text-sm text-neutral-600">
              {addressLines.length === 0 && <li>No address on file.</li>}
              {addressLines.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl border border-neutral-200 p-4 sm:col-span-2">
            <div className="text-sm font-semibold">Items</div>
            {order.items && order.items.length > 0 ? (
              <ul className="mt-2 divide-y text-sm text-neutral-600">
                {order.items.map((item, index) => (
                  <li key={item.id ?? `${item.product_id}-${index}`} className="py-2">
                    <div className="flex items-center justify-between">
                      <span>{item.name ?? item.product_id}</span>
                      <span>x{item.quantity ?? 1}</span>
                    </div>
                    {item.unit_price && (
                      <div className="text-xs text-neutral-400">
                        ${Number(item.unit_price).toFixed(2)} each
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="mt-2 text-sm text-neutral-500">
                Items are not available in the current order response.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
