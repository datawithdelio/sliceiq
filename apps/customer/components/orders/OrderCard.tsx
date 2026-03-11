"use client";

import Link from "next/link";

import { OrderStatus } from "./OrderTracker";

export type OrderItemSummary = {
  product_id: string;
  quantity: number;
  name?: string | null;
};

export type OrderSummary = {
  id: string;
  status: OrderStatus | string;
  total_amount: number | string;
  created_at: string;
  items?: OrderItemSummary[];
};

function summarizeItems(items: OrderItemSummary[] | undefined) {
  if (!items || items.length === 0) return "No items";
  const first = items[0];
  const name = first.name || first.product_id;
  const extraCount = items.length - 1;
  if (extraCount <= 0) return `${name}`;
  return `${name} + ${extraCount} more`;
}

const activeStatuses = new Set(["pending", "processing", "out_for_delivery"]);

export function OrderCard({
  order,
  onReorder,
}: {
  order: OrderSummary;
  onReorder: (orderId: string) => void;
}) {
  const createdAt = new Date(order.created_at).toLocaleString();
  const isActive = activeStatuses.has(String(order.status));

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="text-sm text-neutral-500">{createdAt}</div>
          <div className="text-lg font-semibold">${Number(order.total_amount).toFixed(2)}</div>
          <div className="text-sm text-neutral-600">Status: {order.status}</div>
        </div>
        <div className="flex items-center gap-2">
          {isActive && (
            <Link
              href={`/orders/${order.id}`}
              className="rounded-full border border-neutral-300 px-4 py-2 text-sm font-semibold"
            >
              Track Order
            </Link>
          )}
          <button
            type="button"
            onClick={() => onReorder(order.id)}
            className="rounded-full bg-orange-500 px-4 py-2 text-sm font-semibold text-white"
          >
            Re-order
          </button>
        </div>
      </div>
      <div className="mt-3 text-sm text-neutral-600">
        {summarizeItems(order.items)}
      </div>
    </div>
  );
}
