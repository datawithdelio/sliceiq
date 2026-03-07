"use client";

import { useAuth } from "@clerk/nextjs";
import { useState } from "react";

export function AuthDebug() {
  const { getToken, isSignedIn } = useAuth();
  const [result, setResult] = useState<string>("");
  const [loading, setLoading] = useState(false);

  const runCheck = async () => {
    setLoading(true);
    setResult("");
    try {
      const token = await getToken();
      if (!token) {
        setResult("No session token found. Please sign in first.");
        return;
      }

      const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${baseUrl}/protected/me`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      const text = await res.text();
      setResult(`HTTP ${res.status}: ${text}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setResult(`Request failed: ${message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-6 rounded-xl border border-zinc-300 p-4">
      <p className="mb-3 text-sm text-zinc-700">
        Signed in: {isSignedIn ? "yes" : "no"}
      </p>
      <button
        type="button"
        onClick={runCheck}
        disabled={loading || !isSignedIn}
        className="rounded-full bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {loading ? "Testing..." : "Test Protected API"}
      </button>
      {result ? (
        <pre className="mt-3 overflow-auto rounded bg-zinc-100 p-3 text-xs text-zinc-900">
          {result}
        </pre>
      ) : null}
    </div>
  );
}
