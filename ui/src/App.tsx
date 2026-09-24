import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { ShieldBan } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { EventsProvider } from "@/lib/events";
import { useSetupStatus } from "@/api/hooks";
import { Layout } from "@/components/Layout";
import { EmptyState, Spinner } from "@/components/ui";

const Login = lazy(() => import("@/pages/Login"));
const Setup = lazy(() => import("@/pages/Setup"));
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Alerts = lazy(() => import("@/pages/Alerts"));
const Cases = lazy(() => import("@/pages/Cases"));
const CaseDetail = lazy(() => import("@/pages/CaseDetail"));
const Approvals = lazy(() => import("@/pages/Approvals"));
const Agents = lazy(() => import("@/pages/Agents"));
const AgentDetail = lazy(() => import("@/pages/AgentDetail"));
const Swarm = lazy(() => import("@/pages/Swarm"));
const Skills = lazy(() => import("@/pages/Skills"));
const Workflows = lazy(() => import("@/pages/Workflows"));
const Playground = lazy(() => import("@/pages/Playground"));
const Evals = lazy(() => import("@/pages/Evals"));
const Health = lazy(() => import("@/pages/Health"));
const Runs = lazy(() => import("@/pages/Runs"));
const RunDetail = lazy(() => import("@/pages/RunDetail"));
const Metrics = lazy(() => import("@/pages/Metrics"));
const Policy = lazy(() => import("@/pages/Policy"));
const Standards = lazy(() => import("@/pages/Standards"));
const Audit = lazy(() => import("@/pages/Audit"));
const SettingsPage = lazy(() => import("@/pages/Settings"));
const Users = lazy(() => import("@/pages/Users"));
const Roles = lazy(() => import("@/pages/Roles"));
const ApiTokens = lazy(() => import("@/pages/ApiTokens"));
const Account = lazy(() => import("@/pages/Account"));

function FullSpinner() {
  return (
    <div className="flex h-full items-center justify-center bg-bg">
      <Spinner className="h-6 w-6" />
    </div>
  );
}

function Gate({ perm, children }: { perm?: string; children: ReactNode }) {
  const { can } = useAuth();
  if (!can(perm))
    return (
      <EmptyState
        icon={<ShieldBan className="h-5 w-5" />}
        title="You don't have access to this page"
        body={`Your role is missing the ${perm} permission. Ask an administrator if you need it.`}
      />
    );
  return <>{children}</>;
}

function Protected() {
  const { token, user, loading } = useAuth();
  const loc = useLocation();
  if (!token) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  if (loading || !user) return <FullSpinner />;
  return (
    <EventsProvider token={token}>
      <Layout />
    </EventsProvider>
  );
}

export default function App() {
  const setup = useSetupStatus();
  const loc = useLocation();

  if (setup.isLoading) return <FullSpinner />;
  const needsSetup = setup.data && !setup.data.setup_complete;
  if (needsSetup && loc.pathname !== "/setup") return <Navigate to="/setup" replace />;

  const g = (perm: string, el: ReactNode) => <Gate perm={perm}>{el}</Gate>;

  return (
    <Suspense fallback={<FullSpinner />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/setup" element={needsSetup ? <Setup /> : <Navigate to="/" replace />} />
        <Route element={<Protected />}>
          <Route index element={g("dashboard:read", <Dashboard />)} />
          <Route path="alerts" element={g("alerts:read", <Alerts />)} />
          <Route path="cases" element={g("cases:read", <Cases />)} />
          <Route path="cases/:id" element={g("cases:read", <CaseDetail />)} />
          <Route path="approvals" element={g("actions:read", <Approvals />)} />
          <Route path="agents" element={g("agents:read", <Agents />)} />
          <Route path="agents/:id" element={g("agents:read", <AgentDetail />)} />
          <Route path="swarm" element={g("agents:read", <Swarm />)} />
          <Route path="skills" element={g("skills:read", <Skills />)} />
          <Route path="workflows" element={g("workflows:read", <Workflows />)} />
          <Route path="playground" element={g("playground:use", <Playground />)} />
          <Route path="evals" element={g("evals:read", <Evals />)} />
          <Route path="health" element={g("agents:read", <Health />)} />
          <Route path="runs" element={g("runs:read", <Runs />)} />
          <Route path="runs/:id" element={g("runs:read", <RunDetail />)} />
          <Route path="metrics" element={g("runs:read", <Metrics />)} />
          <Route path="policy" element={g("policy:read", <Policy />)} />
          <Route path="standards" element={g("standards:read", <Standards />)} />
          <Route path="audit" element={g("audit:read", <Audit />)} />
          <Route path="settings" element={g("settings:read", <SettingsPage />)} />
          <Route path="users" element={g("users:manage", <Users />)} />
          <Route path="roles" element={g("users:manage", <Roles />)} />
          <Route path="api-tokens" element={g("users:manage", <ApiTokens />)} />
          <Route path="account" element={<Account />} />
          <Route path="*" element={<EmptyState title="Page not found" body="That route doesn't exist." />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
