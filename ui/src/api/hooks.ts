import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { api } from "./client";
import type * as T from "./types";

/** List endpoints return {items,total}; tolerate bare arrays too. */
export function asList<X>(data: T.List<X> | X[] | undefined | null): T.List<X> {
  if (!data) return { items: [], total: 0 };
  if (Array.isArray(data)) return { items: data, total: data.length };
  return { items: data.items ?? [], total: data.total ?? data.items?.length ?? 0 };
}

type Params = Record<string, string | number | boolean | undefined | null>;

function useList<X>(key: QueryKey, path: string, params?: Params, opts?: { enabled?: boolean; refetchInterval?: number }) {
  return useQuery({
    queryKey: [...key, params ?? {}],
    queryFn: async () => asList(await api.get<T.List<X> | X[]>(path, { limit: 200, ...params })),
    enabled: opts?.enabled,
    refetchInterval: opts?.refetchInterval,
  });
}

function useOne<X>(key: QueryKey, path: string, enabled = true, refetchInterval?: number) {
  return useQuery({ queryKey: key, queryFn: () => api.get<X>(path), enabled, refetchInterval });
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: QueryKey[]) => keys.forEach((k) => qc.invalidateQueries({ queryKey: k }));
}

// ---- Setup / auth ----
export const useSetupStatus = () =>
  useQuery({ queryKey: ["setup"], queryFn: () => api.public.get<T.SetupStatus>("/setup/status"), staleTime: 30_000 });

export const useMe = (enabled: boolean) =>
  useQuery({ queryKey: ["me"], queryFn: () => api.get<T.User>("/auth/me"), enabled, retry: false, staleTime: 60_000 });

// ---- Dashboard ----
export const useDashboard = (range: string) =>
  useQuery({
    queryKey: ["dashboard", range],
    queryFn: () => api.get<T.DashboardSummary>("/dashboard/summary", { range }),
    refetchInterval: 30_000,
  });

// ---- Alerts ----
export const useAlerts = (params?: Params) => useList<T.Alert>(["alerts"], "/alerts", params);
export const useAlert = (id?: string) => useOne<T.Alert>(["alerts", "one", id], `/alerts/${id}`, !!id);
export function useTriageAlert() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.post<T.Run>(`/alerts/${id}/triage`),
    onSuccess: () => inv(["alerts"], ["runs"]),
  });
}

// ---- Cases ----
export const useCases = (params?: Params) => useList<T.Case>(["cases"], "/cases", params);
export const useCase = (id?: string) => useOne<T.CaseDetail>(["cases", "one", id], `/cases/${id}`, !!id);
export function useUpdateCase(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (body: Partial<{ status: T.CaseStatus; severity: T.Severity; assignee_id: string | null; title: string }>) =>
      api.patch<T.CaseDetail>(`/cases/${id}`, body),
    onSuccess: () => inv(["cases"]),
  });
}
export function useAddComment(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (body: string) => api.post<T.Comment>(`/cases/${id}/comments`, { body }),
    onSuccess: () => inv(["cases", "one", id]),
  });
}
export function useRunCaseWorkflow(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (workflow_id: string) => api.post<T.Run>(`/cases/${id}/run`, { workflow_id }),
    onSuccess: () => inv(["cases", "one", id], ["runs"]),
  });
}

// ---- Actions ----
export const useActions = (params?: Params) => useList<T.Action>(["actions"], "/actions", params, { refetchInterval: 20_000 });
export const useActionCatalog = () =>
  useQuery({
    queryKey: ["actions", "catalog"],
    queryFn: async () => asList(await api.get<T.List<T.ActionCatalogItem> | T.ActionCatalogItem[]>("/actions/catalog")).items,
    staleTime: 300_000,
  });
export function useActionOp() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, op, body }: { id: string; op: "approve" | "reject" | "execute" | "rollback"; body?: unknown }) =>
      api.post<T.Action>(`/actions/${id}/${op}`, body),
    onSuccess: () => inv(["actions"], ["cases"], ["dashboard"]),
  });
}

// ---- Agents ----
export const useAgents = () =>
  useQuery({
    queryKey: ["agents"],
    queryFn: async () => asList(await api.get<T.List<T.Agent> | T.Agent[]>("/agents")).items,
    refetchInterval: 15_000,
  });
export const useAgent = (id?: string) => useOne<T.AgentDetail>(["agents", "one", id], `/agents/${id}`, !!id);
export const useAgentPrompt = (id?: string, enabled = true) =>
  useOne<T.AgentPrompt>(["agents", "prompt", id], `/agents/${id}/prompt`, !!id && enabled);
export function useUpdateAgent(id: string) {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (body: T.AgentPatch) => api.patch<T.AgentDetail>(`/agents/${id}`, body),
    onSuccess: () => inv(["agents"]),
  });
}

// ---- Skills ----
export const useSkills = () =>
  useQuery({
    queryKey: ["skills"],
    queryFn: async () => asList(await api.get<T.List<T.Skill> | T.Skill[]>("/skills")).items,
  });
export const useSkill = (id?: string) => useOne<T.Skill>(["skills", "one", id], `/skills/${id}`, !!id);
export function useSaveSkill() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, create, body }: { id: string; create?: boolean; body: Partial<T.Skill> }) =>
      create ? api.post<T.Skill>("/skills", { id, ...body }) : api.put<T.Skill>(`/skills/${id}`, body),
    onSuccess: () => inv(["skills"]),
  });
}

// ---- Standards ----
export const useStandards = () =>
  useQuery({
    queryKey: ["standards"],
    queryFn: async () => asList(await api.get<T.List<T.Standard> | T.Standard[]>("/standards")).items,
    staleTime: 120_000,
  });
export const useStandard = (id?: string) => useOne<T.StandardDetail>(["standards", "one", id], `/standards/${id}`, !!id);

// ---- Workflows ----
export const useWorkflows = () =>
  useQuery({
    queryKey: ["workflows"],
    queryFn: async () => asList(await api.get<T.List<T.Workflow> | T.Workflow[]>("/workflows")).items,
  });
export function useSaveWorkflow() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<T.Workflow> }) => api.put<T.Workflow>(`/workflows/${id}`, body),
    onSuccess: () => inv(["workflows"]),
  });
}
export function useRunWorkflow() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: Record<string, unknown> }) => api.post<T.Run>(`/workflows/${id}/run`, { input }),
    onSuccess: () => inv(["runs"], ["workflows"]),
  });
}

// ---- Runs ----
export const useRuns = (params?: Params) => useList<T.RunSummary>(["runs"], "/runs", params, { refetchInterval: 15_000 });
export const useRun = (id?: string, live = false) =>
  useOne<T.Run>(["runs", "one", id], `/runs/${id}`, !!id, live ? 2500 : undefined);
export function useRunOp() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, op }: { id: string; op: "cancel" | "replay" }) => api.post<T.Run>(`/runs/${id}/${op}`),
    onSuccess: () => inv(["runs"]),
  });
}

// ---- Evals ----
export const useEvalSuites = () =>
  useQuery({
    queryKey: ["evals", "suites"],
    queryFn: async () => asList(await api.get<T.List<T.EvalSuite> | T.EvalSuite[]>("/evals/suites")).items,
  });
export const useEvalSuite = (id?: string) => useOne<T.EvalSuiteDetail>(["evals", "suite", id], `/evals/suites/${id}`, !!id);
export const useEvalRuns = (suite_id?: string) =>
  useList<T.EvalRun>(["evals", "runs"], "/evals/runs", { suite_id }, { refetchInterval: 5000 });
export function useRunEval() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (id: string) => api.post<T.EvalRun>(`/evals/suites/${id}/run`),
    onSuccess: () => inv(["evals"]),
  });
}

// ---- Governance ----
export const usePolicy = () => useOne<T.Policy>(["policy"], "/policy");
export function useSavePolicy() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (p: T.Policy) => api.put<T.Policy>("/policy", p), onSuccess: () => inv(["policy"]) });
}
export const useAudit = (params?: Params) => useList<T.AuditEntry>(["audit"], "/audit", params);

// ---- Settings ----
export const useSettings = () => useOne<T.Settings>(["settings"], "/settings");
export function useSaveSettings() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (s: Partial<T.Settings>) => api.put<T.Settings>("/settings", s),
    onSuccess: () => inv(["settings"], ["health"]),
  });
}
export const useProviders = () =>
  useQuery({
    queryKey: ["providers"],
    queryFn: async () => asList(await api.get<T.List<T.ProviderInfo> | T.ProviderInfo[]>("/settings/providers")).items,
    staleTime: 600_000,
  });

// ---- Users / RBAC ----
export const useUsers = () =>
  useQuery({ queryKey: ["users"], queryFn: async () => asList(await api.get<T.List<T.User> | T.User[]>("/users")).items });
export const useRoles = () =>
  useQuery({
    queryKey: ["roles"],
    queryFn: async () => asList(await api.get<T.List<T.Role> | T.Role[]>("/roles")).items,
    staleTime: 600_000,
  });
export function useSaveUser() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      id ? api.patch<T.User>(`/users/${id}`, body) : api.post<T.User>("/users", body),
    onSuccess: () => inv(["users"]),
  });
}
export function useDeleteUser() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api.del(`/users/${id}`), onSuccess: () => inv(["users"]) });
}
export const useApiTokens = () =>
  useQuery({
    queryKey: ["api-tokens"],
    queryFn: async () => asList(await api.get<T.List<T.ApiToken> | T.ApiToken[]>("/api-tokens")).items,
  });
export function useCreateToken() {
  const inv = useInvalidate();
  return useMutation({
    mutationFn: (b: { name: string; role: string; expires_days: number }) => api.post<T.ApiToken>("/api-tokens", b),
    onSuccess: () => inv(["api-tokens"]),
  });
}
export function useDeleteToken() {
  const inv = useInvalidate();
  return useMutation({ mutationFn: (id: string) => api.del(`/api-tokens/${id}`), onSuccess: () => inv(["api-tokens"]) });
}

// ---- Health & metrics ----
export const useSystemHealth = () => useOne<T.SystemHealth>(["health"], "/system/health", true, 15_000);
export const useTimeseries = (metric: T.MetricName, range: string, agent_id?: string) =>
  useQuery({
    queryKey: ["metrics", metric, range, agent_id],
    queryFn: () => api.get<T.Timeseries>("/metrics/timeseries", { metric, range, agent_id }),
    refetchInterval: 30_000,
  });
