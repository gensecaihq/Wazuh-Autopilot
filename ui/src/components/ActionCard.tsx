import { useState } from "react";
import { Link } from "react-router-dom";
import { Ban, Check, CheckCircle2, CircleHelp, CircleX, Play, RotateCcw, Timer, Zap } from "lucide-react";
import type { Action } from "@/api/types";
import { useActionOp } from "@/api/hooks";
import { errorMessage } from "@/api/client";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { fmtPct, relTime } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Badge, ConfirmDialog, JsonView, riskTone, StatusBadge } from "./ui";

type Op = "approve" | "reject" | "execute" | "rollback";

export function ActionCard({ a, compact }: { a: Action; compact?: boolean }) {
  const { can } = useAuth();
  const op = useActionOp();
  const toast = useToast();
  const [pending, setPending] = useState<Op | null>(null);
  const [showDetail, setShowDetail] = useState(false);

  const run = (kind: Op, text: string) => {
    const body = kind === "reject" ? { reason: text } : kind === "approve" ? { note: text || undefined } : undefined;
    op.mutate(
      { id: a.id, op: kind, body },
      {
        onSuccess: (res) => {
          toast.success(`Action ${kind === "execute" ? "executed" : kind === "rollback" ? "rolled back" : kind + "d"}`, `${res.label} → ${res.target} is now ${res.status.replace("_", " ")}`);
          setPending(null);
        },
        onError: (e) => {
          toast.error(`Couldn't ${kind} action`, errorMessage(e));
          setPending(null);
        },
      },
    );
  };

  const canApprove = a.status === "proposed" && can("actions:approve");
  const canExecute = a.status === "approved" && can("actions:execute");
  const canRollback = ["executed", "verified"].includes(a.status) && can("actions:execute");
  const v = a.verification;

  return (
    <div className={cn("rounded-xl border border-line bg-card2/40 p-4", a.status === "proposed" && "border-accent/30")}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[15px]">{a.label}</span>
            <span className="rounded-md border border-line bg-deep px-1.5 py-0.5 font-mono text-xs">{a.target}</span>
            <Badge tone={riskTone[a.risk] ?? "neutral"}>{a.risk} risk</Badge>
            <StatusBadge value={a.status} />
            {a.auto_approved && (
              <Badge tone="info">
                <Zap className="h-3 w-3" /> auto
              </Badge>
            )}
          </div>
          <div className="mt-1 text-xs text-muted">
            {!compact && (
              <>
                <Link to={`/cases/${a.case_id}`} className="text-accent hover:underline">
                  {a.case_number}
                </Link>{" "}
                ·{" "}
              </>
            )}
            proposed by <span className="text-fg/80">{a.proposed_by}</span> · {relTime(a.created_at)} · confidence {fmtPct(a.confidence, 0, true)} · {a.autonomy}
            {a.status === "proposed" && a.expires_at && (
              <span className="ml-1 inline-flex items-center gap-1 text-warn">
                <Timer className="h-3 w-3" /> expires {relTime(a.expires_at)}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canApprove && (
            <>
              <button className="btn-secondary btn-sm" onClick={() => setPending("reject")}>
                <Ban className="h-3.5 w-3.5" /> Reject
              </button>
              <button className="btn-success btn-sm" onClick={() => setPending("approve")}>
                <Check className="h-3.5 w-3.5" /> Approve
              </button>
            </>
          )}
          {canExecute && (
            <button className="btn-primary btn-sm" onClick={() => setPending("execute")}>
              <Play className="h-3.5 w-3.5" /> Execute
            </button>
          )}
          {canRollback && (
            <button className="btn-secondary btn-sm" onClick={() => setPending("rollback")}>
              <RotateCcw className="h-3.5 w-3.5" /> Roll back
            </button>
          )}
        </div>
      </div>
      {a.rationale && <p className="mt-3 text-sm leading-relaxed text-fg/85">{a.rationale}</p>}
      {(a.approved_by || a.executed_at || v) && (
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
          {a.approved_by && (
            <span>
              Approved by {a.approved_by.name} {relTime(a.approved_at)}
            </span>
          )}
          {a.executed_at && (
            <span>
              Executed {relTime(a.executed_at)}
              {a.executed_by ? ` by ${typeof a.executed_by === "string" ? a.executed_by : a.executed_by.name}` : ""}
            </span>
          )}
          {v && (
            <span className="inline-flex items-center gap-1">
              {v.verified === true && <CheckCircle2 className="h-3.5 w-3.5 text-success" />}
              {v.verified === false && <CircleX className="h-3.5 w-3.5 text-danger" />}
              {v.verified === null && <CircleHelp className="h-3.5 w-3.5 text-warn" />}
              {v.verified === true ? "Verified on host" : v.verified === false ? "Verification failed" : "Unverified"}
              {v.note && <span className="text-subtle">· {v.note}</span>}
            </span>
          )}
        </div>
      )}
      {!compact && (Object.keys(a.params ?? {}).length > 0 || Object.keys(a.result ?? {}).length > 0) && (
        <div className="mt-3">
          <button className="text-xs text-muted hover:text-fg" onClick={() => setShowDetail(!showDetail)}>
            {showDetail ? "Hide" : "Show"} parameters & result
          </button>
          {showDetail && (
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              <JsonView value={a.params} />
              <JsonView value={a.result} />
            </div>
          )}
        </div>
      )}

      <ConfirmDialog
        open={pending === "approve"}
        onClose={() => setPending(null)}
        onConfirm={(t) => run("approve", t)}
        loading={op.isPending}
        title={`Approve ${a.label}?`}
        tone="success"
        confirmLabel="Approve"
        requireReason={undefined}
        body={
          <>
            Tier 1 approval for <span className="font-mono text-fg">{a.target}</span>. Depending on the autonomy policy the platform may execute it right away.
          </>
        }
      />
      <ConfirmDialog
        open={pending === "reject"}
        onClose={() => setPending(null)}
        onConfirm={(t) => run("reject", t)}
        loading={op.isPending}
        title={`Reject ${a.label}?`}
        tone="danger"
        confirmLabel="Reject"
        requireReason="Reason (recorded in the audit log and fed back to the agent)"
      />
      <ConfirmDialog
        open={pending === "execute"}
        onClose={() => setPending(null)}
        onConfirm={(t) => run("execute", t)}
        loading={op.isPending}
        title={`Execute ${a.label}?`}
        confirmLabel="Execute now"
        body={
          <>
            Runs <span className="font-mono text-fg">{a.type}</span> against <span className="font-mono text-fg">{a.target}</span> through the Wazuh MCP server, then runs
            the verification check.
          </>
        }
      />
      <ConfirmDialog
        open={pending === "rollback"}
        onClose={() => setPending(null)}
        onConfirm={(t) => run("rollback", t)}
        loading={op.isPending}
        title={`Roll back ${a.label}?`}
        tone="danger"
        confirmLabel="Roll back"
        body="Runs the rollback tool for this action (e.g. unblock the IP, unisolate the host)."
      />
    </div>
  );
}
