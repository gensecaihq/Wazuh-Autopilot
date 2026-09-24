import { useSearchParams } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { useStandard, useStandards } from "@/api/hooks";
import { Async, Card, DataTable, Drawer, PageBody, PageHeader, ProgressBar, Spinner } from "@/components/ui";

export default function Standards() {
  const q = useStandards();
  const [sp, setSp] = useSearchParams();
  const open = sp.get("open");
  return (
    <div>
      <PageHeader title="Standards" subtitle="Industry frameworks the swarm's agents and skills are grounded in, and how much of each they cover" />
      <PageBody>
        <Async q={q}>
          {(list) => (
            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
              {list.map((s) => (
                <button key={s.id} onClick={() => setSp({ open: s.id })} className="card p-5 text-left transition hover:border-subtle/60">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="text-[15px]">{s.name}</div>
                      <div className="text-xs text-muted">{s.publisher}</div>
                    </div>
                    <span className="text-2xl font-light">{Math.round(s.coverage_pct)}%</span>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-muted">{s.description}</p>
                  <ProgressBar value={s.coverage_pct} className="mt-4" tone={s.coverage_pct >= 70 ? "success" : "accent"} />
                  <div className="mt-2 flex justify-between text-[11px] text-subtle">
                    <span>{s.controls_mapped} controls mapped</span>
                    <span>
                      {s.agents.length} agents · {s.skills.length} skills
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Async>
      </PageBody>
      <StandardDrawer id={open} onClose={() => setSp({})} />
    </div>
  );
}

function StandardDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const q = useStandard(id ?? undefined);
  const s = q.data;
  return (
    <Drawer open={!!id} onClose={onClose} width="max-w-3xl" title={s?.name ?? "Standard"} subtitle={s ? `${s.publisher} · ${Math.round(s.coverage_pct)}% coverage` : undefined}>
      {q.isLoading && <Spinner />}
      {s && (
        <div className="space-y-4">
          <p className="text-sm text-muted">{s.description}</p>
          {s.url && (
            <a href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
              Reference <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          <Card>
            <DataTable
              rows={s.controls}
              rowKey={(c) => c.id}
              dense
              columns={[
                { key: "id", header: "Control", cell: (c) => <span className="whitespace-nowrap font-mono text-xs text-accent">{c.id}</span>, sort: (c) => c.id },
                { key: "title", header: "Title", cell: (c) => c.title },
                {
                  key: "cov",
                  header: "Covered by",
                  cell: (c) =>
                    c.covered_by.length ? (
                      <div className="flex flex-wrap gap-1">
                        {c.covered_by.map((x) => (
                          <span key={x} className="chip">
                            {x}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-warn">gap</span>
                    ),
                  sort: (c) => c.covered_by.length,
                },
                { key: "ev", header: "Evidence", cell: (c) => c.evidence_count, sort: (c) => c.evidence_count },
              ]}
            />
          </Card>
        </div>
      )}
    </Drawer>
  );
}
