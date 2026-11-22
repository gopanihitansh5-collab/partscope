"use client";

import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

type State = "checking" | "online" | "degraded" | "offline";

export function ApiStatus() {
  const [state, setState] = useState<State>("checking");
  const [detail, setDetail] = useState("Checking API");

  useEffect(() => {
    let active = true;
    async function check() {
      try {
        const response = await fetch(`${API_BASE}/api/v1/health/ready`, { cache: "no-store" });
        if (!active) return;
        if (response.ok) {
          setState("online");
          setDetail("API and models ready");
        } else {
          setState("degraded");
          setDetail("API up, artifacts missing");
        }
      } catch {
        if (!active) return;
        setState("offline");
        setDetail("API unreachable");
      }
    }
    check();
    const timer = setInterval(check, 30_000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  const dot: Record<State, string> = {
    checking: "bg-ink-400",
    online: "bg-emerald-400",
    degraded: "bg-amber-400",
    offline: "bg-rose-500",
  };

  return (
    <div className="flex items-center gap-2 text-xs text-ink-400">
      <span className={`h-2 w-2 rounded-full ${dot[state]} ${state === "checking" ? "animate-pulse" : ""}`} />
      <span>{detail}</span>
    </div>
  );
}
