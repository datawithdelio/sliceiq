"use client";

import { useEffect, useMemo, useState } from "react";
import { io, Socket } from "socket.io-client";

const STATUSES = ["processing", "out_for_delivery", "delivered", "cancelled"] as const;

type OrderStatus = (typeof STATUSES)[number] | string;

type AdminOrder = {
  id: string;
  status: OrderStatus;
  total_amount: number | string;
  created_at: string;
  user: {
    id: string;
    email: string;
    full_name: string;
    role: string;
  };
};

const ACTIVE_STATUSES = new Set(["processing", "out_for_delivery", "pending"]);

export default function AdminOrdersPage() {
  const [orders, setOrders] = useState<AdminOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [onlyActive, setOnlyActive] = useState(true);
  const [token, setToken] = useState<string>(
    typeof window !== "undefined" ? localStorage.getItem("sliceiq:admin_token") || "" : ""
  );
  const [adminAlert, setAdminAlert] = useState<string | null>(null);

  const filteredOrders = useMemo(() => {
    if (!onlyActive) return orders;
    return orders.filter((order) => ACTIVE_STATUSES.has(String(order.status)));
  }, [onlyActive, orders]);

  const fetchOrders = async (authToken: string) => {
    setLoading(true);
    setError(null);

    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const resp = await fetch(`${backendUrl}/admin/orders`, {
      headers: { Authorization: `Bearer ${authToken}` },
    });

    if (!resp.ok) {
      setError("Unable to load admin orders. Check your token.");
      setLoading(false);
      return;
    }

    const data = (await resp.json()) as AdminOrder[];
    setOrders(data);
    setLoading(false);
  };

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }

    fetchOrders(token);
  }, [token]);

  useEffect(() => {
    if (!token) return;

    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const socket: Socket = io(backendUrl, {
      path: "/ws/socket.io",
      transports: ["websocket"],
      auth: { token },
    });

    socket.on("new_order_admin", (payload: { order_id: string; customer_name: string; total: number }) => {
      setAdminAlert(
        `New order ${payload.order_id} from ${payload.customer_name} ($${payload.total.toFixed(2)})`
      );
      fetchOrders(token);
    });

    return () => {
      socket.disconnect();
    };
  }, [token]);

  const handleStatusChange = async (orderId: string, newStatus: string) => {
    if (!token) return;

    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const resp = await fetch(`${backendUrl}/admin/orders/${orderId}/status`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ new_status: newStatus }),
    });

    if (!resp.ok) {
      setError("Failed to update order status.");
      return;
    }

    const updated = (await resp.json()) as AdminOrder;
    setOrders((prev) => prev.map((order) => (order.id === updated.id ? updated : order)));
  };

  const handleTokenSave = () => {
    if (typeof window !== "undefined") {
      localStorage.setItem("sliceiq:admin_token", token);
    }
    if (token) {
      fetchOrders(token);
    }
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Admin Orders</h1>
          <p className="text-sm text-neutral-500">Manage order status in real time.</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={onlyActive}
            onChange={(event) => setOnlyActive(event.target.checked)}
          />
          Show active only
        </label>
      </div>

      <div className="rounded-xl border border-neutral-200 bg-white p-4">
        <div className="text-sm font-semibold">Admin Token</div>
        <p className="text-xs text-neutral-500">Paste a Clerk admin JWT to authenticate.</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            type="password"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            className="w-full flex-1 rounded-lg border border-neutral-300 px-3 py-2 text-sm"
            placeholder="Bearer token"
          />
          <button
            type="button"
            onClick={handleTokenSave}
            className="rounded-full bg-orange-500 px-4 py-2 text-sm font-semibold text-white"
          >
            Load Orders
          </button>
        </div>
      </div>

      {adminAlert && (
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-700">
          {adminAlert}
        </div>
      )}

      {loading && <div className="text-sm text-neutral-500">Loading orders...</div>}
      {error && <div className="text-sm text-red-600">{error}</div>}

      {!loading && filteredOrders.length === 0 && (
        <div className="rounded-xl border border-neutral-200 p-6 text-center text-sm text-neutral-500">
          No orders found.
        </div>
      )}

      {!loading && filteredOrders.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-100 text-xs uppercase text-neutral-500">
              <tr>
                <th className="px-4 py-3">Order ID</th>
                <th className="px-4 py-3">Customer</th>
                <th className="px-4 py-3">Total</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Order Time</th>
              </tr>
            </thead>
            <tbody>
              {filteredOrders.map((order) => (
                <tr key={order.id} className="border-t border-neutral-200">
                  <td className="px-4 py-3 text-xs text-neutral-500">{order.id}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium">{order.user.full_name}</div>
                    <div className="text-xs text-neutral-500">{order.user.email}</div>
                  </td>
                  <td className="px-4 py-3 font-semibold">
                    ${Number(order.total_amount).toFixed(2)}
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={order.status}
                      onChange={(event) => handleStatusChange(order.id, event.target.value)}
                      className="rounded-lg border border-neutral-300 px-2 py-1 text-sm"
                    >
                      {STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {status}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-3 text-xs text-neutral-500">
                    {new Date(order.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
