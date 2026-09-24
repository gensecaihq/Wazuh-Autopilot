import { useState } from "react";
import { Pencil, Plus, UserX } from "lucide-react";
import { useDeleteUser, useRoles, useSaveUser, useUsers } from "@/api/hooks";
import type { User } from "@/api/types";
import { errorMessage } from "@/api/client";
import { Async, Badge, Card, ConfirmDialog, DataTable, Field, Modal, PageBody, PageHeader, Select, Spinner, StatusBadge, Toggle, type Column } from "@/components/ui";
import { relTime } from "@/lib/format";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";

export default function Users() {
  const q = useUsers();
  const [edit, setEdit] = useState<User | "new" | null>(null);
  const [del, setDel] = useState<User | null>(null);
  const remove = useDeleteUser();
  const toast = useToast();
  const { user: me } = useAuth();

  const cols: Column<User>[] = [
    {
      key: "name",
      header: "User",
      cell: (u) => (
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-full border border-line bg-card2 text-xs">{u.avatar_initials}</span>
          <div>
            <div>
              {u.name} {u.id === me?.id && <span className="text-xs text-subtle">(you)</span>}
            </div>
            <div className="text-xs text-muted">{u.email}</div>
          </div>
        </div>
      ),
      sort: (u) => u.name,
    },
    { key: "role", header: "Role", cell: (u) => <Badge tone={u.role === "admin" ? "accent" : "neutral"}>{u.role_label}</Badge>, sort: (u) => u.role },
    { key: "status", header: "Status", cell: (u) => <StatusBadge value={u.active ? "healthy" : "disabled"} />, sort: (u) => (u.active ? 1 : 0) },
    { key: "last", header: "Last login", cell: (u) => <span className="text-muted">{relTime(u.last_login_at)}</span>, sort: (u) => u.last_login_at ?? "" },
    {
      key: "act",
      header: "",
      cell: (u) => (
        <div className="flex justify-end gap-1">
          <button className="btn-ghost btn-sm" onClick={() => setEdit(u)}>
            <Pencil className="h-3.5 w-3.5" />
          </button>
          {u.id !== me?.id && (
            <button className="btn-ghost btn-sm hover:text-danger" onClick={() => setDel(u)}>
              <UserX className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Users"
        subtitle="People who can sign in, and what their role lets them do"
        right={
          <button className="btn-primary" onClick={() => setEdit("new")}>
            <Plus className="h-4 w-4" /> Invite user
          </button>
        }
      />
      <PageBody>
        <Card>
          <Async q={q}>{(list) => <DataTable rows={list} columns={cols} rowKey={(u) => u.id} initialSort={{ key: "name", dir: "asc" }} />}</Async>
        </Card>
      </PageBody>
      <UserModal user={edit} onClose={() => setEdit(null)} />
      <ConfirmDialog
        open={!!del}
        onClose={() => setDel(null)}
        loading={remove.isPending}
        tone="danger"
        title={`Remove ${del?.name}?`}
        body="They lose access immediately. Their audit history is kept."
        confirmLabel="Remove user"
        onConfirm={() =>
          del &&
          remove.mutate(del.id, {
            onSuccess: () => {
              toast.success("User removed");
              setDel(null);
            },
            onError: (e) => toast.error("Couldn't remove user", errorMessage(e)),
          })
        }
      />
    </div>
  );
}

function UserModal({ user, onClose }: { user: User | "new" | null; onClose: () => void }) {
  const roles = useRoles();
  const save = useSaveUser();
  const toast = useToast();
  const isNew = user === "new";
  const u = user && user !== "new" ? user : null;
  const [f, setF] = useState({ name: "", email: "", role: "analyst", password: "", active: true });
  const [key, setKey] = useState<string | null>(null);
  const k = user === null ? null : isNew ? "new" : u?.id ?? null;
  if (k !== key) {
    setKey(k);
    setF({ name: u?.name ?? "", email: u?.email ?? "", role: u?.role ?? "analyst", password: "", active: u?.active ?? true });
  }
  const valid = f.name.trim() && (!isNew || (/\S+@\S+\.\S+/.test(f.email) && f.password.length >= 10)) && (!f.password || f.password.length >= 10);
  const role = roles.data?.find((r) => r.id === f.role);
  return (
    <Modal
      open={!!user}
      onClose={onClose}
      title={isNew ? "Invite user" : `Edit ${u?.name}`}
      footer={
        <>
          <button className="btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            className="btn-primary"
            disabled={!valid || save.isPending}
            onClick={() => {
              const body: Record<string, unknown> = isNew ? { name: f.name.trim(), email: f.email.trim(), role: f.role, password: f.password } : { name: f.name.trim(), role: f.role, active: f.active };
              if (!isNew && f.password) body.password = f.password;
              save.mutate(
                { id: u?.id, body },
                {
                  onSuccess: () => {
                    toast.success(isNew ? "User created" : "User updated");
                    onClose();
                  },
                  onError: (e) => toast.error("Save failed", errorMessage(e)),
                },
              );
            }}
          >
            {save.isPending && <Spinner className="text-black" />} {isNew ? "Create user" : "Save"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Full name">
          <input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        </Field>
        <Field label="Email">
          <input className="input" type="email" disabled={!isNew} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        </Field>
        <Field label="Role" hint={role?.description}>
          <Select value={f.role} onChange={(v) => setF({ ...f, role: v })} options={(roles.data ?? [{ id: "analyst", label: "SOC Analyst" }]).map((r) => ({ value: r.id, label: r.label }))} />
        </Field>
        <Field label={isNew ? "Initial password" : "Reset password (optional)"} hint="At least 10 characters.">
          <input className="input" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        </Field>
        {!isNew && <Toggle checked={f.active} onChange={(v) => setF({ ...f, active: v })} label={f.active ? "Active" : "Deactivated"} />}
      </div>
    </Modal>
  );
}
