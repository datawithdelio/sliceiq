"use client";

import { useAuth, useUser } from "@clerk/nextjs";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { io, Socket } from "socket.io-client";
import { Toaster, toast } from "sonner";

type OrderUpdate = {
  order_id: string;
  status: string;
  message?: string;
};

type SocketContextValue = {
  latestOrderUpdate: OrderUpdate | null;
  isConnected: boolean;
};

const SocketContext = createContext<SocketContextValue>({
  latestOrderUpdate: null,
  isConnected: false,
});

export function useSocketUpdates(): SocketContextValue {
  return useContext(SocketContext);
}

export const useSocket = useSocketUpdates;

export function SocketProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded: userLoaded } = useUser();
  const { getToken, isLoaded: authLoaded } = useAuth();
  const [latestOrderUpdate, setLatestOrderUpdate] = useState<OrderUpdate | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!userLoaded || !authLoaded) return undefined;

    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    let socket: Socket | null = null;
    let cancelled = false;

    (async () => {
      const token = await getToken();
      if (!token || cancelled) return;

      socket = io(backendUrl, {
        path: "/ws/socket.io",
        transports: ["websocket"],
        auth: { token },
      });

      socket.on("connect", () => {
        setIsConnected(true);
      });

      socket.on("disconnect", () => {
        setIsConnected(false);
      });

      socket.on("order_status_update", (data: OrderUpdate) => {
        setLatestOrderUpdate(data);
        const message = data.message || `Order ${data.order_id} is now ${data.status}`;
        toast(message);
      });

      socket.on("connect_error", (err) => {
        setIsConnected(false);
        console.error("Socket connection error", err);
      });
    })();

    return () => {
      cancelled = true;
      if (socket) socket.disconnect();
    };
  }, [authLoaded, getToken, userLoaded]);

  const value = useMemo(
    () => ({ latestOrderUpdate, isConnected }),
    [latestOrderUpdate, isConnected]
  );

  return (
    <SocketContext.Provider value={value}>
      {children}
      <Toaster richColors />
    </SocketContext.Provider>
  );
}
