import { useState } from "react";
import { api, errorMessage } from "@/api/client";
import { Card, Field, Kv, PageBody, PageHeader, Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/lib/toast";
import { relTime } from "@/lib/format";

export default function Account() {
  const { user } = useAuth();
  const toast = useToast();
  const [f, setF] = useState({ current: "", next: "", confirm: "" });
  const [busy, setBusy] = useState(false);
  const valid = f.current && f.next.length >= 10 && f.next === f.confirm;
  if (!user) return null;
  return (
    <div>
      <PageHeader title="Account" subtitle="Your profile and password" />
      <PageBody className="max-w-3xl">
        <Card className="p-5">
          <Kv k="Name" v={user.name} />
          <Kv k="Email" v={user.email} />
          <Kv k="Role" v={user.role_label} />
          <Kv k="Last login" v={relTime(user.last_login_at)} />
          <Kv k="Permissions" v={<span className="text-xs text-muted">{user.permissions.length} granted</span>} />
        </Card>
        <Card className="space-y-4 p-5">
          <h3 className="text-[15px]">Change password</h3>
          <Field label="Current password">
            <input className="input" type="password" value={f.current} onChange={(e) => setF({ ...f, current: e.target.value })} />
          </Field>
          <Field label="New password" hint="At least 10 characters.">
            <input className="input" type="password" value={f.next} onChange={(e) => setF({ ...f, next: e.target.value })} />
          </Field>
          <Field label="Confirm new password">
            <input className="input" type="password" value={f.confirm} onChange={(e) => setF({ ...f, confirm: e.target.value })} />
          </Field>
          <button
            className="btn-primary"
            disabled={!valid || busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api.post("/auth/change-password", { current_password: f.current, new_password: f.next });
                toast.success("Password changed");
                setF({ current: "", next: "", confirm: "" });
              } catch (e) {
                toast.error("Couldn't change password", errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy && <Spinner className="text-black" />} Update password
          </button>
        </Card>
      </PageBody>
    </div>
  );
}
