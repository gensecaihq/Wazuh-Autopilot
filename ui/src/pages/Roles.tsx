import { Fragment } from "react";
import { Check, Minus } from "lucide-react";
import { useRoles } from "@/api/hooks";
import { Async, Card, PageBody, PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";

const ALL = "dashboard:read alerts:read alerts:ingest cases:read cases:write actions:read actions:propose actions:approve actions:execute agents:read agents:write skills:read skills:write workflows:read workflows:write workflows:run runs:read runs:debug playground:use evals:read evals:run standards:read policy:read policy:write settings:read settings:write users:manage audit:read".split(" ");

export default function Roles() {
  const q = useRoles();
  return (
    <div>
      <PageHeader title="Roles & RBAC" subtitle="What each role can see and do. Roles are built in. Assign them under Users." />
      <PageBody>
        <Async q={q}>
          {(roles) => {
            const perms = Array.from(new Set([...ALL, ...roles.flatMap((r) => r.permissions.filter((p) => p !== "*"))]));
            const groups = Array.from(new Set(perms.map((p) => p.split(":")[0])));
            const has = (rp: string[], p: string) => rp.includes("*") || rp.includes(p);
            return (
              <>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                  {roles.map((r) => (
                    <Card key={r.id} className="p-4">
                      <div className="text-sm">{r.label}</div>
                      <div className="font-mono text-[11px] text-subtle">{r.id}</div>
                      <p className="mt-2 text-xs text-muted">{r.description}</p>
                      <div className="mt-3 text-[11px] text-accent">{r.permissions.includes("*") ? "all permissions" : `${r.permissions.length} permissions`}</div>
                    </Card>
                  ))}
                </div>
                <Card>
                  <div className="scrollbar-thin overflow-x-auto">
                    <table className="w-full min-w-[760px]">
                      <thead className="sticky top-0 bg-card">
                        <tr className="border-b border-line">
                          <th className="th">Permission</th>
                          {roles.map((r) => (
                            <th key={r.id} className="th text-center">
                              {r.label}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {groups.map((g) => (
                          <Fragment key={g}>
                            <tr className="bg-card2/40">
                              <td colSpan={roles.length + 1} className="px-3 py-1.5 text-[11px] uppercase tracking-wide text-subtle">
                                {g}
                              </td>
                            </tr>
                            {perms
                              .filter((p) => p.startsWith(`${g}:`))
                              .map((p) => (
                                <tr key={p} className="border-b border-line/50">
                                  <td className="td font-mono text-xs">{p}</td>
                                  {roles.map((r) => (
                                    <td key={r.id} className="td text-center">
                                      {has(r.permissions, p) ? <Check className="mx-auto h-4 w-4 text-success" /> : <Minus className={cn("mx-auto h-4 w-4 text-line")} />}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                          </Fragment>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </>
            );
          }}
        </Async>
      </PageBody>
    </div>
  );
}
