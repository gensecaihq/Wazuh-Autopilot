import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { API_BASE } from "@/api/client";
import type { SseEvent, SseType } from "@/api/types";

const TYPES: SseType[] = [
  "run.started",
  "run.step",
  "run.finished",
  "case.created",
  "case.updated",
  "action.created",
  "action.updated",
  "alert.ingested",
  "agent.status",
];

const INVALIDATE: Record<SseType, string[][]> = {
  "run.started": [["runs"], ["agents"]],
  "run.step": [],
  "run.finished": [["runs"], ["agents"], ["cases"], ["dashboard"]],
  "case.created": [["cases"], ["dashboard"]],
  "case.updated": [["cases"]],
  "action.created": [["actions"], ["cases"], ["dashboard"]],
  "action.updated": [["actions"], ["cases"], ["dashboard"]],
  "alert.ingested": [["alerts"], ["dashboard"]],
  "agent.status": [["agents"]],
};

type Listener = (e: SseEvent) => void;
interface Ctx {
  events: SseEvent[];
  connected: boolean;
  subscribe: (fn: Listener) => () => void;
}

const EventsCtx = createContext<Ctx>({ events: [], connected: false, subscribe: () => () => {} });

export function EventsProvider({ token, children }: { token: string | null; children: ReactNode }) {
  const qc = useQueryClient();
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const listeners = useRef(new Set<Listener>());
  const pending = useRef(new Set<string>());
  const flushTimer = useRef<number | null>(null);

  useEffect(() => {
    if (!token || typeof EventSource === "undefined") return;
    let es: EventSource | null = null;
    let retry: number | null = null;
    let closed = false;

    const scheduleInvalidate = (keys: string[][]) => {
      keys.forEach((k) => pending.current.add(JSON.stringify(k)));
      if (flushTimer.current) return;
      flushTimer.current = window.setTimeout(() => {
        pending.current.forEach((k) => qc.invalidateQueries({ queryKey: JSON.parse(k) as string[] }));
        pending.current.clear();
        flushTimer.current = null;
      }, 800);
    };

    const connect = () => {
      es = new EventSource(`${API_BASE}/events/stream?token=${encodeURIComponent(token)}`);
      es.onopen = () => setConnected(true);
      es.onerror = () => {
        setConnected(false);
        es?.close();
        if (!closed) retry = window.setTimeout(connect, 5000);
      };
      for (const type of TYPES) {
        es.addEventListener(type, (msg) => {
          let data: Record<string, unknown> = {};
          try {
            data = JSON.parse((msg as MessageEvent<string>).data) as Record<string, unknown>;
          } catch {
            /* ignore */
          }
          const ev: SseEvent = { type, data, at: Date.now() };
          setEvents((prev) => [ev, ...prev].slice(0, 200));
          listeners.current.forEach((l) => l(ev));
          scheduleInvalidate(INVALIDATE[type]);
          const rid = typeof data.run_id === "string" ? data.run_id : typeof data.id === "string" ? data.id : null;
          if (type.startsWith("run.") && rid) scheduleInvalidate([["runs", "one", rid]]);
        });
      }
    };
    connect();
    return () => {
      closed = true;
      es?.close();
      if (retry) clearTimeout(retry);
      setConnected(false);
    };
  }, [token, qc]);

  const subscribe = (fn: Listener) => {
    listeners.current.add(fn);
    return () => {
      listeners.current.delete(fn);
    };
  };

  return <EventsCtx.Provider value={{ events, connected, subscribe }}>{children}</EventsCtx.Provider>;
}

export const useEvents = () => useContext(EventsCtx);
