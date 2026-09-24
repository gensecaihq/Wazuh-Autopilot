import { useState } from "react";
import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { useApiTokens, useCreateToken, useDeleteToken, useRoles } from "@/api/hooks";
import type { ApiToken } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Async, Card, ConfirmDialog, DataTable, EmptyState, Field, Modal, PageBody, PageHeader, Select, Spinner, type Column } from "@/components/ui";
import { fmtDateTime, relTime } from "@/lib/format";
import { useToast } from "@/lib/toast";

export default function ApiTokens() {
  const q = useApiTokens();
  const roles = useRoles();
  const create = useCreateToken();
  const del = useDeleteToken();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ name: "", role: "analyst", expires_days: 90 });
  const [created, setCreated] = useState<ApiToken | null>(null);
  const [revoke, setRevoke] = useState<ApiToken | null>(null);

  const cols: Column<ApiToken>[] = [
    { key: "name", header: "Name", cell: (t) => t.name, sort: (t) => t.name },
    { key: "prefix", header: "Token", cell: (t) => <span className="font-mono text-xs text-muted">{t.prefix}…</span> },
    { key: "role", header: "Role", cell: (t) => roles.data?.find((r) => r.id === t.role)?.label ?? t.role },
    { key: "created", header: "Created", cell: (t) => <span className="text-muted">{relTime(t.created_at)}</span>, sort: (t) => t.created_at },
    { key: "exp", header: "Expires", cell: (t) => <span className="text-muted">{t.expires_at ? fmtDateTime(t.expires_at) : "never"}</span>, sort: (t) => t.expires_at ?? "" },
    {
      key: "x",
      header: "",
      cell: (t) => (
        <button className="btn-ghost btn-sm hover:text-danger" onClick={() => setRevoke(t)}>
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="API Tokens"
        subtitle="Service credentials for SOAR, SIEM forwarders and CI, scoped by role"
        right={
          <button className="btn-primary" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> New token
          </button>
        }
      />
      <PageBody>
        <Card>
          <Async q={q} isEmpty={(d) => !d.length} empty={<EmptyState icon={<KeyRound className="h-5 w-5" />} title="No API tokens" body="Create one for integrations such as the Wazuh webhook forwarder." />}>
            {(list) => <DataTable rows={list} columns={cols} rowKey={(t) => t.id} />}
          </Async>
        </Card>
      </PageBody>
      <Modal
        open={open}
        onClose={() => {
          setOpen(false);
          setCreated(null);
        }}
        title={created ? "Token created" : "New API token"}
        footer={
          created ? (
            <button className="btn-primary" onClick={() => { setOpen(false); setCreated(null); }}>
              Done
            </button>
          ) : (
            <>
              <button className="btn-secondary" onClick={() => setOpen(false)}>
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={!f.name.trim() || create.isPending}
                onClick={() =>
                  create.mutate(
                    { ...f, name: f.name.trim() },
                    { onSuccess: (t) => { setCreated(t); setF({ name: "", role: "analyst", expires_days: 90 }); }, onError: (e) => toast.error("Couldn't create token", errorMessage(e)) },
                  )
                }
              >
                {create.isPending && <Spinner className="text-black" />} Create
              </button>
            </>
          )
        }
      >
        {created ? (
          <div className="space-y-3">
            <p className="text-sm text-muted">Copy this token now. It won't be shown again.</p>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-deep p-3">
              <code className="flex-1 break-all font-mono text-xs">{created.token}</code>
              <button
                className="btn-ghost btn-sm"
                onClick={() => {
                  navigator.clipboard?.writeText(created.token ?? "").then(() => toast.success("Copied"), () => toast.error("Copy failed"));
                }}
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Field label="Name">
              <input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="wazuh-webhook-forwarder" />
            </Field>
            <Field label="Role">
              <Select value={f.role} onChange={(v) => setF({ ...f, role: v })} options={(roles.data ?? []).map((r) => ({ value: r.id, label: r.label }))} />
            </Field>
            <Field label="Expires in (days)" hint="0 = never (not recommended)">
              <input className="input w-32" type="number" min={0} value={f.expires_days} onChange={(e) => setF({ ...f, expires_days: Number(e.target.value) })} />
            </Field>
          </div>
        )}
      </Modal>
      <ConfirmDialog
        open={!!revoke}
        onClose={() => setRevoke(null)}
        tone="danger"
        loading={del.isPending}
        title={`Revoke ${revoke?.name}?`}
        body="Integrations using this token stop working immediately."
        confirmLabel="Revoke"
        onConfirm={() => revoke && del.mutate(revoke.id, { onSuccess: () => { toast.success("Token revoked"); setRevoke(null); }, onError: (e) => toast.error("Revoke failed", errorMessage(e)) })}
      />
    </div>
  );
}
