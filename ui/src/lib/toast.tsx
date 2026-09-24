import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { cn } from "./cn";

type Kind = "success" | "error" | "info";
interface Toast {
  id: number;
  kind: Kind;
  title: string;
  body?: string;
}

const Ctx = createContext<(kind: Kind, title: string, body?: string) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: Kind, title: string, body?: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, kind, title, body }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="card pointer-events-auto flex items-start gap-3 bg-card2 p-3 shadow-2xl shadow-black/40"
            role="status"
          >
            {t.kind === "success" && <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
            {t.kind === "error" && <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-danger" />}
            {t.kind === "info" && <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />}
            <div className="min-w-0 flex-1">
              <div className={cn("text-sm font-medium")}>{t.title}</div>
              {t.body && <div className="mt-0.5 break-words text-xs text-muted">{t.body}</div>}
            </div>
            <button className="text-subtle hover:text-fg" onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  const push = useContext(Ctx);
  return {
    success: (title: string, body?: string) => push("success", title, body),
    error: (title: string, body?: string) => push("error", title, body),
    info: (title: string, body?: string) => push("info", title, body),
  };
}
