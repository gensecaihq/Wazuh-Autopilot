import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Agent, WorkflowStep } from "@/api/types";
import { iconFor } from "./icons";

// ---------------------------------------------------------------------------
// Swarm topology: radial layout, command agents in the middle
// ---------------------------------------------------------------------------
export function SwarmGraph({ agents, height = 560, highlight }: { agents: Agent[]; height?: number; highlight?: string | null }) {
  const navigate = useNavigate();
  const [hover, setHover] = useState<string | null>(null);
  const W = 1000;
  const H = 640;
  const pos = useMemo(() => {
    const center = agents.filter((a) => a.category === "command");
    const ring = agents.filter((a) => a.category !== "command");
    const order = ["detect", "investigate", "intel", "respond", "govern"];
    ring.sort((a, b) => order.indexOf(a.category) - order.indexOf(b.category));
    const m = new Map<string, { x: number; y: number }>();
    center.forEach((a, i) => m.set(a.id, { x: W / 2 + (i - (center.length - 1) / 2) * 120, y: H / 2 }));
    const R = Math.min(W, H) / 2 - 80;
    ring.forEach((a, i) => {
      const t = (i / Math.max(1, ring.length)) * Math.PI * 2 - Math.PI / 2;
      m.set(a.id, { x: W / 2 + Math.cos(t) * R * 1.35, y: H / 2 + Math.sin(t) * R });
    });
    return m;
  }, [agents]);

  const focus = hover ?? highlight ?? null;
  const edges = agents.flatMap((a) => a.handoffs.filter((h) => pos.has(h)).map((h) => ({ from: a.id, to: h })));

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--muted) / 0.6)" />
        </marker>
        <marker id="arrowHot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--accent))" />
        </marker>
        <radialGradient id="bgGlow">
          <stop offset="0%" stopColor="rgb(var(--glow))" stopOpacity="0.12" />
          <stop offset="100%" stopColor="rgb(var(--glow))" stopOpacity="0" />
        </radialGradient>
      </defs>
      <ellipse cx={W / 2} cy={H / 2} rx={W / 2.2} ry={H / 2.3} fill="url(#bgGlow)" />
      {edges.map((e, i) => {
        const a = pos.get(e.from)!;
        const b = pos.get(e.to)!;
        const hot = focus && (e.from === focus || e.to === focus);
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len = Math.hypot(dx, dy) || 1;
        const pad = 32;
        const x1 = a.x + (dx / len) * pad;
        const y1 = a.y + (dy / len) * pad;
        const x2 = b.x - (dx / len) * (pad + 4);
        const y2 = b.y - (dy / len) * (pad + 4);
        const mx = (x1 + x2) / 2 - dy * 0.08;
        const my = (y1 + y2) / 2 + dx * 0.08;
        return (
          <path
            key={i}
            d={`M ${x1} ${y1} Q ${mx} ${my} ${x2} ${y2}`}
            fill="none"
            stroke={hot ? "rgb(var(--accent))" : "rgb(var(--muted) / 0.35)"}
            strokeWidth={hot ? 1.8 : 1.2}
            opacity={focus && !hot ? 0.35 : 1}
            markerEnd={hot ? "url(#arrowHot)" : "url(#arrow)"}
          />
        );
      })}
      {agents.map((a) => {
        const p = pos.get(a.id);
        if (!p) return null;
        const Icon = iconFor(a.icon);
        const running = a.status === "running";
        const dim = focus && focus !== a.id && !edges.some((e) => (e.from === focus && e.to === a.id) || (e.to === focus && e.from === a.id));
        return (
          <g
            key={a.id}
            transform={`translate(${p.x},${p.y})`}
            className="cursor-pointer"
            opacity={dim ? 0.4 : a.enabled ? 1 : 0.45}
            onMouseEnter={() => setHover(a.id)}
            onMouseLeave={() => setHover(null)}
            onClick={() => navigate(`/agents/${a.id}`)}
          >
            {running && (
              <circle r={30} fill="none" stroke={a.avatar_color} strokeWidth={2}>
                <animate attributeName="r" values="28;42" dur="1.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" values="0.7;0" dur="1.6s" repeatCount="indefinite" />
              </circle>
            )}
            <circle r={28} fill="rgb(var(--card))" stroke={a.avatar_color} strokeOpacity={0.55} strokeWidth={1.4} />
            <circle r={28} fill={a.avatar_color} fillOpacity={0.1} />
            <foreignObject x={-11} y={-11} width={22} height={22}>
              <Icon style={{ color: a.avatar_color, width: 22, height: 22 }} />
            </foreignObject>
            <text y={46} textAnchor="middle" fontSize={13} fill="rgb(var(--fg))">
              {a.codename}
            </text>
            <text y={62} textAnchor="middle" fontSize={10.5} fill="rgb(var(--muted))">
              {a.name.length > 30 ? a.name.slice(0, 29) + "…" : a.name}
            </text>
            <circle cx={20} cy={-20} r={5} fill={running ? "rgb(var(--accent))" : a.status === "error" ? "rgb(var(--danger))" : a.enabled ? "rgb(var(--success))" : "rgb(var(--subtle))"} stroke="rgb(var(--card))" strokeWidth={2} />
          </g>
        );
      })}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Workflow DAG: layered left-to-right layout
// ---------------------------------------------------------------------------
export function DagGraph({ steps, agents, entry, mode }: { steps: WorkflowStep[]; agents: Map<string, Agent>; entry?: string; mode: "swarm" | "graph" }) {
  const layout = useMemo(() => {
    const byId = new Map(steps.map((s) => [s.id, s]));
    const indeg = new Map(steps.map((s) => [s.id, 0]));
    steps.forEach((s) => s.next.forEach((n) => byId.has(n) && indeg.set(n, (indeg.get(n) ?? 0) + 1)));
    const level = new Map<string, number>();
    const roots = steps.filter((s) => (indeg.get(s.id) ?? 0) === 0 || s.agent_id === entry);
    const queue = (roots.length ? roots : steps.slice(0, 1)).map((s) => s.id);
    queue.forEach((id) => level.set(id, 0));
    let guard = 0;
    while (queue.length && guard++ < 500) {
      const id = queue.shift()!;
      const l = level.get(id) ?? 0;
      for (const n of byId.get(id)?.next ?? []) {
        if (!byId.has(n)) continue;
        if (!level.has(n) || (level.get(n)! < l + 1 && l + 1 < steps.length)) {
          level.set(n, l + 1);
          queue.push(n);
        }
      }
    }
    steps.forEach((s) => !level.has(s.id) && level.set(s.id, 0));
    const cols = new Map<number, string[]>();
    steps.forEach((s) => {
      const l = level.get(s.id)!;
      cols.set(l, [...(cols.get(l) ?? []), s.id]);
    });
    const colW = 210;
    const rowH = 96;
    const maxRows = Math.max(1, ...[...cols.values()].map((c) => c.length));
    const pos = new Map<string, { x: number; y: number }>();
    [...cols.entries()].forEach(([l, ids]) => {
      ids.forEach((id, i) => {
        pos.set(id, { x: 20 + l * colW, y: 20 + (i + (maxRows - ids.length) / 2) * rowH });
      });
    });
    const width = 20 + (Math.max(0, ...cols.keys()) + 1) * colW;
    const height = 20 + maxRows * rowH;
    return { pos, width, height, byId };
  }, [steps, entry, mode]);

  const NW = 170;
  const NH = 58;
  return (
    <div className="scrollbar-thin overflow-x-auto">
      <svg width={layout.width} height={layout.height} className="min-w-full">
        <defs>
          <marker id="dagArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="rgb(var(--accent) / .7)" />
          </marker>
        </defs>
        {steps.flatMap((s) =>
          s.next
            .filter((n) => layout.pos.has(n))
            .map((n) => {
              const a = layout.pos.get(s.id)!;
              const b = layout.pos.get(n)!;
              const back = b.x <= a.x;
              const x1 = a.x + NW;
              const y1 = a.y + NH / 2;
              const x2 = b.x;
              const y2 = b.y + NH / 2;
              const d = back
                ? `M ${a.x + NW / 2} ${a.y + NH} C ${a.x + NW / 2} ${a.y + NH + 40}, ${b.x + NW / 2} ${b.y + NH + 40}, ${b.x + NW / 2} ${b.y + NH + 2}`
                : `M ${x1} ${y1} C ${x1 + 40} ${y1}, ${x2 - 40} ${y2}, ${x2 - 2} ${y2}`;
              return <path key={`${s.id}-${n}`} d={d} fill="none" stroke="rgb(var(--accent) / .45)" strokeWidth={1.4} strokeDasharray={mode === "swarm" ? "4 4" : undefined} markerEnd="url(#dagArrow)" />;
            }),
        )}
        {steps.map((s) => {
          const p = layout.pos.get(s.id)!;
          const ag = agents.get(s.agent_id);
          const Icon = iconFor(ag?.icon);
          const color = ag?.avatar_color ?? "rgb(var(--accent))";
          const isEntry = s.agent_id === entry;
          return (
            <g key={s.id} transform={`translate(${p.x},${p.y})`}>
              <rect width={NW} height={NH} rx={12} fill="rgb(var(--card2))" stroke={isEntry ? "rgb(var(--accent))" : "rgb(var(--line))"} strokeWidth={isEntry ? 1.5 : 1} />
              <rect x={10} y={14} width={30} height={30} rx={8} fill={color} fillOpacity={0.12} stroke={color} strokeOpacity={0.35} />
              <foreignObject x={17} y={21} width={16} height={16}>
                <Icon style={{ color, width: 16, height: 16 }} />
              </foreignObject>
              <text x={50} y={26} fontSize={12.5} fill="rgb(var(--fg))">
                {s.label.length > 17 ? s.label.slice(0, 16) + "…" : s.label}
              </text>
              <text x={50} y={43} fontSize={10.5} fill="rgb(var(--muted))">
                {(ag?.codename ?? s.agent_id).slice(0, 18)}
                {s.condition ? " · if" : ""}
              </text>
              {isEntry && (
                <text x={NW - 10} y={14} fontSize={9} textAnchor="end" fill="rgb(var(--accent))">
                  ENTRY
                </text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
