import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Pencil, Plus, Save, Search, Sparkles } from "lucide-react";
import { useSaveSkill, useSkill, useSkills } from "@/api/hooks";
import type { Skill, SkillCategory } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Async, Badge, Drawer, Field, Markdown, Modal, PageBody, PageHeader, Segmented, Select, Spinner } from "@/components/ui";
import { relTime, titleCase } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";

const CATS: ("all" | SkillCategory)[] = ["all", "detection", "investigation", "response", "intel", "vulnerability", "compliance", "reporting", "safety"];

export default function Skills() {
  const q = useSkills();
  const [sp, setSp] = useSearchParams();
  const [cat, setCat] = useState<"all" | SkillCategory>("all");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const { can } = useAuth();
  const open = sp.get("open");

  const filtered = useMemo(
    () =>
      (q.data ?? []).filter(
        (s) => (cat === "all" || s.category === cat) && (!search || `${s.name} ${s.description} ${s.id}`.toLowerCase().includes(search.toLowerCase())),
      ),
    [q.data, cat, search],
  );

  return (
    <div>
      <PageHeader
        title="Skills Library"
        subtitle="SKILL.md playbooks agents load on demand, each mapped to industry standards"
        right={
          can("skills:write") && (
            <button className="btn-primary" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" /> New skill
            </button>
          )
        }
      />
      <PageBody>
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-full max-w-xs">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
            <input className="input pl-9" placeholder="Search skills…" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div className="scrollbar-thin max-w-full overflow-x-auto">
            <Segmented size="sm" value={cat} onChange={setCat} options={CATS.map((c) => ({ value: c, label: c === "all" ? "All" : titleCase(c) }))} />
          </div>
        </div>
        <Async q={q}>
          {() => (
            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
              {filtered.map((s) => (
                <button key={s.id} onClick={() => setSp({ open: s.id })} className="card p-4 text-left transition hover:border-subtle/60">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-accent" />
                      <span className="text-[15px]">{s.name}</span>
                    </div>
                    <Badge>{s.category}</Badge>
                  </div>
                  <p className="mt-2 line-clamp-2 text-sm text-muted">{s.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1">
                    {s.standards.slice(0, 3).map((st) => (
                      <span key={st.id} className="rounded-md border border-info/25 bg-info/5 px-1.5 py-0.5 text-[10.5px] text-info">
                        {st.name}
                      </span>
                    ))}
                  </div>
                  <div className="mt-3 flex items-center justify-between border-t border-line/70 pt-2.5 text-[11px] text-subtle">
                    <span>used by {s.used_by.length} agent{s.used_by.length === 1 ? "" : "s"}</span>
                    <span>{s.builtin ? "built-in" : "custom"} · {relTime(s.updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </Async>
      </PageBody>
      <SkillDrawer id={open} onClose={() => setSp({})} />
      <CreateSkill open={creating} onClose={() => setCreating(false)} />
    </div>
  );
}

function SkillDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const q = useSkill(id ?? undefined);
  const save = useSaveSkill();
  const { can } = useAuth();
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const [body, setBody] = useState("");
  const [desc, setDesc] = useState("");
  useEffect(() => {
    setEditing(false);
    if (q.data) {
      setBody(q.data.body_md ?? "");
      setDesc(q.data.description);
    }
  }, [q.data]);
  const s = q.data;
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      width="max-w-3xl"
      title={s?.name ?? "Skill"}
      subtitle={s ? `${s.id} · ${s.category}` : undefined}
      footer={
        s && can("skills:write") ? (
          editing ? (
            <>
              <button className="btn-secondary" onClick={() => setEditing(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={save.isPending}
                onClick={() =>
                  save.mutate(
                    { id: s.id, body: { description: desc, body_md: body } },
                    { onSuccess: () => { toast.success("Skill saved"); setEditing(false); q.refetch(); }, onError: (e) => toast.error("Save failed", errorMessage(e)) },
                  )
                }
              >
                {save.isPending ? <Spinner className="text-black" /> : <Save className="h-4 w-4" />} Save
              </button>
            </>
          ) : (
            <button className="btn-secondary" onClick={() => setEditing(true)}>
              <Pencil className="h-4 w-4" /> Edit
            </button>
          )
        ) : undefined
      }
    >
      {q.isLoading && <Spinner />}
      {s && (
        <div className="space-y-4">
          {editing ? (
            <>
              <Field label="Description (shown to agents when choosing a skill)">
                <textarea className="textarea" rows={2} value={desc} onChange={(e) => setDesc(e.target.value)} />
              </Field>
              <Field label="SKILL.md instructions (markdown)">
                <textarea className="textarea min-h-[50vh] font-mono text-[12.5px]" value={body} onChange={(e) => setBody(e.target.value)} />
              </Field>
            </>
          ) : (
            <>
              <p className="text-sm text-muted">{s.description}</p>
              <div className="flex flex-wrap gap-1.5">
                {s.standards.map((st) => (
                  <span key={st.id} className="rounded-md border border-info/25 bg-info/5 px-2 py-0.5 text-xs text-info">
                    {st.name}
                  </span>
                ))}
              </div>
              {s.tools.length > 0 && (
                <div>
                  <div className="label">Tools referenced</div>
                  <div className="flex flex-wrap gap-1">
                    {s.tools.map((t) => (
                      <span key={t} className="chip font-mono">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div>
                <div className="label">Used by</div>
                <div className="flex flex-wrap gap-1">
                  {s.used_by.map((a) => (
                    <span key={a} className="chip">
                      {a}
                    </span>
                  ))}
                  {!s.used_by.length && <span className="text-sm text-muted">No agents yet</span>}
                </div>
              </div>
              <div className="rounded-xl border border-line bg-deep/50 p-5">
                <Markdown>{s.body_md}</Markdown>
              </div>
            </>
          )}
        </div>
      )}
    </Drawer>
  );
}

function CreateSkill({ open, onClose }: { open: boolean; onClose: () => void }) {
  const save = useSaveSkill();
  const toast = useToast();
  const [f, setF] = useState({ id: "", name: "", description: "", category: "investigation" as SkillCategory, body_md: "# Skill\n\n## When to use\n\n## Procedure\n\n1. \n" });
  const valid = /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(f.id) && f.name && f.description;
  return (
    <Modal
      open={open}
      onClose={onClose}
      width="max-w-2xl"
      title="New skill"
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={!valid || save.isPending}
            onClick={() =>
              save.mutate(
                { id: f.id, create: true, body: { name: f.name, description: f.description, category: f.category, body_md: f.body_md, standards: [] } as Partial<Skill> },
                { onSuccess: () => { toast.success("Skill created"); onClose(); }, onError: (e) => toast.error("Create failed", errorMessage(e)) },
              )
            }
          >
            Create
          </button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="ID" hint="lowercase-with-hyphens, matches the SKILL.md name">
          <input className="input font-mono" value={f.id} onChange={(e) => setF({ ...f, id: e.target.value })} placeholder="ransomware-response" />
        </Field>
        <Field label="Name">
          <input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        </Field>
        <Field label="Category">
          <Select value={f.category} onChange={(v) => setF({ ...f, category: v as SkillCategory })} options={CATS.filter((c) => c !== "all").map((c) => ({ value: c, label: titleCase(c) }))} />
        </Field>
        <Field label="Description" className="sm:col-span-2">
          <input className="input" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
        </Field>
        <Field label="Instructions (markdown)" className="sm:col-span-2">
          <textarea className="textarea min-h-[220px] font-mono text-[12.5px]" value={f.body_md} onChange={(e) => setF({ ...f, body_md: e.target.value })} />
        </Field>
      </div>
    </Modal>
  );
}
