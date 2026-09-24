import { useState } from "react";
import { ClipboardCheck, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { useActions, usePolicy } from "@/api/hooks";
import { Async, Card, EmptyState, PageBody, PageHeader, Select, Tabs } from "@/components/ui";
import { ActionCard } from "@/components/ActionCard";
import { AUTONOMY_LEVELS } from "@/lib/providers";

type Tab = "queue" | "approved" | "history";
const HISTORY = ["", "executed", "verified", "failed", "rejected", "rolled_back", "expired"];

export default function Approvals() {
  const [tab, setTab] = useState<Tab>("queue");
  const [hist, setHist] = useState("");
  const proposed = useActions({ status: "proposed" });
  const approved = useActions({ status: "approved" });
  const history = useActions({ status: hist || undefined });
  const policy = usePolicy();
  const level = AUTONOMY_LEVELS.find((a) => a.id === policy.data?.autonomy_level);

  const q = tab === "queue" ? proposed : tab === "approved" ? approved : history;

  return (
    <div>
      <PageHeader
        title="Approvals"
        subtitle="Response actions proposed by the swarm. Two-tier: approve, then execute."
        right={
          level && (
            <Link to="/policy" className="btn-secondary">
              <ShieldCheck className="h-4 w-4 text-accent" /> Autonomy: {level.label} ({level.tag})
            </Link>
          )
        }
      />
      <div className="px-4 md:px-6">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "queue", label: "Awaiting approval", count: proposed.data?.total },
            { value: "approved", label: "Ready to execute", count: approved.data?.total },
            { value: "history", label: "History" },
          ]}
        />
      </div>
      <PageBody>
        {tab === "history" && (
          <div className="flex justify-end">
            <Select className="w-48" value={hist} onChange={setHist} options={HISTORY.map((s) => ({ value: s, label: s ? s.replace("_", " ") : "All outcomes" }))} />
          </div>
        )}
        <Async
          q={q}
          isEmpty={(d) => !d.items.filter((a) => tab !== "history" || !["proposed", "approved"].includes(a.status) || !!hist).length}
          empty={
            <Card>
              <EmptyState
                icon={<ClipboardCheck className="h-5 w-5" />}
                title={tab === "queue" ? "Nothing awaiting approval" : tab === "approved" ? "Nothing waiting to execute" : "No history yet"}
                body={tab === "queue" ? "When the response planner proposes an action, it lands here for Tier 1 approval." : undefined}
              />
            </Card>
          }
        >
          {(d) => (
            <div className="space-y-3">
              {d.items
                .filter((a) => tab !== "history" || !!hist || !["proposed", "approved"].includes(a.status))
                .map((a) => (
                  <ActionCard key={a.id} a={a} />
                ))}
            </div>
          )}
        </Async>
      </PageBody>
    </div>
  );
}
