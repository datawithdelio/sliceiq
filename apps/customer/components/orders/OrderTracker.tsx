"use client";

import { Bike, ClipboardCheck, CookingPot, PartyPopper } from "lucide-react";
import { motion } from "framer-motion";

export type OrderStatus =
  | "pending"
  | "processing"
  | "out_for_delivery"
  | "delivered";

type Step = {
  key: OrderStatus;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const steps: Step[] = [
  { key: "pending", label: "Order Placed", icon: ClipboardCheck },
  { key: "processing", label: "Preparing", icon: CookingPot },
  { key: "out_for_delivery", label: "On the Way", icon: Bike },
  { key: "delivered", label: "Enjoy your Pizza!", icon: PartyPopper },
];

const statusIndex = (status: OrderStatus) =>
  Math.max(0, steps.findIndex((step) => step.key === status));

export function OrderTracker({ status }: { status: OrderStatus }) {
  const activeIndex = statusIndex(status);

  return (
    <div className="w-full">
      <div className="hidden sm:flex items-center gap-4">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isActive = index === activeIndex;
          const isCompleted = index < activeIndex;

          return (
            <div key={step.key} className="relative flex-1">
              <div
                className={
                  "flex items-center gap-3 rounded-xl border px-4 py-3 " +
                  (isActive
                    ? "border-orange-500 bg-orange-50"
                    : isCompleted
                    ? "border-orange-300 text-orange-600"
                    : "border-neutral-200 text-neutral-400")
                }
              >
                <div className="relative">
                  {isActive && (
                    <motion.span
                      layoutId="order-tracker-active"
                      className="absolute -inset-2 rounded-full bg-orange-200/60"
                      transition={{ type: "spring", stiffness: 220, damping: 20 }}
                    />
                  )}
                  <Icon className="relative h-5 w-5" />
                </div>
                <div className="text-sm font-semibold">{step.label}</div>
              </div>
              {index < steps.length - 1 && (
                <div
                  className={
                    "absolute right-[-14px] top-1/2 hidden h-0.5 w-7 -translate-y-1/2 sm:block " +
                    (index < activeIndex ? "bg-orange-300" : "bg-neutral-200")
                  }
                />
              )}
            </div>
          );
        })}
      </div>

      <div className="flex flex-col gap-3 sm:hidden">
        {steps.map((step, index) => {
          const Icon = step.icon;
          const isActive = index === activeIndex;
          const isCompleted = index < activeIndex;

          return (
            <div
              key={step.key}
              className={
                "relative flex items-center gap-3 rounded-xl border px-4 py-3 " +
                (isActive
                  ? "border-orange-500 bg-orange-50"
                  : isCompleted
                  ? "border-orange-300 text-orange-600"
                  : "border-neutral-200 text-neutral-400")
              }
            >
              {isActive && (
                <motion.span
                  layoutId="order-tracker-active-mobile"
                  className="absolute inset-0 rounded-xl bg-orange-100/60"
                  transition={{ type: "spring", stiffness: 220, damping: 20 }}
                />
              )}
              <Icon className="relative h-5 w-5" />
              <div className="relative text-sm font-semibold">{step.label}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
