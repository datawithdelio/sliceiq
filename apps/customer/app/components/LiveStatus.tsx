"use client";

import { useSocketUpdates } from "../providers/SocketProvider";

export function LiveStatus() {
  const { latestOrderUpdate } = useSocketUpdates();

  if (!latestOrderUpdate) {
    return (
      <div className="text-sm text-neutral-500">
        Live Status: No recent updates
      </div>
    );
  }

  return (
    <div className="text-sm">
      Live Status:{" "}
      <span className="font-semibold">
        {latestOrderUpdate.status}
      </span>{" "}
      <span className="text-neutral-500">
        ({latestOrderUpdate.order_id})
      </span>
    </div>
  );
}
