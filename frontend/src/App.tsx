import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Camera as CameraIcon,
  CheckCircle,
  CircleNotch,
  Clock,
  CloudArrowUp,
  Database,
  DotsThree,
  Eye,
  FilePdf,
  FileText,
  Funnel,
  Graph,
  Hexagon,
  LockKey,
  MagnifyingGlass,
  MapPin,
  Monitor,
  PaperPlaneTilt,
  Plus,
  Pulse,
  Robot,
  Scan,
  ShieldCheck,
  SignOut,
  Sparkle,
  UploadSimple,
  UserCircle,
  UserPlus,
  UsersThree,
  WarningCircle,
  X,
} from "@phosphor-icons/react";

import {
  ApiError,
  askAssistant,
  addCaseNote,
  approveCandidate,
  clearStoredToken,
  createCase,
  createEntity,
  extractEvidence,
  createRelationship,
  createReport,
  getAuditEvents,
  getCases,
  getCaseNotes,
  getCandidates,
  getDuplicateCandidates,
  getEntities,
  getEvidence,
  getGeo,
  getGraph,
  getHealth,
  getMe,
  getReports,
  getStoredToken,
  getTimeline,
  getUsers,
  createUser,
  downloadReport,
  login,
  logout,
  mergeEntities,
  runAnalysis,
  runSignals,
  searchWorkspace,
  synthesizeReport,
  rejectCandidate,
  storeToken,
  updateEntity,
  uploadEvidence,
} from "./api";
import GraphCanvas from "./components/GraphCanvas";
import CameraModule from "./components/CameraModule";
import PersonReferencePhotos from "./components/PersonReferencePhotos";
import { pathToView, viewToPath } from "./routes";
import type {
  AnalysisResponse,
  AssistantResponse,
  AuditEvent,
  Candidate,
  CaseNote,
  CaseRecord,
  DuplicateMatch,
  Entity,
  Evidence,
  GraphEdge,
  GraphNode,
  GraphResponse,
  HealthPayload,
  MapResponse,
  ReportRecord,
  Role,
  SearchResponseData,
  SignalResponse,
  TimelineResponse,
  User,
} from "./types";

export type View = "command" | "search" | "network" | "timeline" | "geo" | "evidence" | "review" | "cases" | "reports" | "audit" | "users" | "camera-cameras" | "camera-monitoring" | "camera-review" | "camera-event";
type Toast = { kind: "success" | "error"; message: string } | null;

type NavItem = { id: View; label: string; icon: typeof Scan; adminOnly?: boolean };

const navItems: NavItem[] = [
  { id: "command", label: "Command center", icon: Scan },
  { id: "search", label: "Search workspace", icon: MagnifyingGlass },
  { id: "network", label: "Network explorer", icon: Graph },
  { id: "timeline", label: "Timeline", icon: Clock },
  { id: "geo", label: "Geographic view", icon: MapPin },
  { id: "evidence", label: "Evidence vault", icon: Database },
  { id: "review", label: "Review queue", icon: Sparkle, adminOnly: true },
  { id: "cases", label: "Cases", icon: Hexagon },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "users", label: "User access", icon: UsersThree, adminOnly: true },
  { id: "camera-cameras", label: "Camera sources", icon: CameraIcon, adminOnly: true },
  { id: "camera-monitoring", label: "Live monitoring", icon: Monitor },
  { id: "camera-review", label: "Detection review", icon: Eye },
  { id: "audit", label: "Audit trail", icon: Pulse, adminOnly: true },
];

const demoAccounts: { role: Role; username: string; password: string; description: string }[] = [
  { role: "ANALYST", username: "analyst", password: "ChangeMe-Analyst-2026!", description: "Read-only investigation access" },
  { role: "ADMIN", username: "admin", password: "ChangeMe-Admin-2026!", description: "Data management and review" },
  { role: "AUDITOR", username: "auditor", password: "ChangeMe-Auditor-2026!", description: "History and oversight" },
];

function formatDate(value: string | null | undefined) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not recorded";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function roleLabel(role: Role | string) {
  return role === "ADMIN" ? "Administrator" : role === "ANALYST" ? "Analyst" : "Supervisor";
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function statusClass(value: string) {
  const normalized = value.toUpperCase();
  if (normalized.includes("PROCESSED") || normalized.includes("COMPLETED") || normalized.includes("ACTIVE")) return "status-positive";
  if (normalized.includes("PENDING") || normalized.includes("UPLOADED") || normalized.includes("REVIEW")) return "status-warning";
  if (normalized.includes("FAILED") || normalized.includes("ARCHIVED")) return "status-danger";
  return "status-neutral";
}

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [sessionLoading, setSessionLoading] = useState(true);
  const [loginError, setLoginError] = useState("");

  useEffect(() => {
    if (!getStoredToken()) {
      setSessionLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => clearStoredToken())
      .finally(() => setSessionLoading(false));
  }, []);

  const handleLogin = async (username: string, password: string) => {
    setLoginError("");
    try {
      const session = await login(username, password);
      storeToken(session.access_token);
      setUser(session.user);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : "Unable to sign in.");
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // A local token is still cleared if the API is already unavailable.
    }
    clearStoredToken();
    setUser(null);
  };

  if (sessionLoading) {
    return <div className="boot-screen"><div className="boot-mark"><span /><span /><span /></div><CircleNotch className="spin" size={22} /><p>Opening secure workspace</p></div>;
  }

  if (!user) {
    return <LoginScreen onLogin={handleLogin} error={loginError} />;
  }

  return <Workspace user={user} onLogout={handleLogout} />;
}

function LoginScreen({ onLogin, error }: { onLogin: (username: string, password: string) => Promise<void>; error: string }) {
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    await onLogin(username, password);
    setBusy(false);
  };

  const useAccount = (account: (typeof demoAccounts)[number]) => {
    setUsername(account.username);
    setPassword(account.password);
  };

  return (
    <div className="login-screen">
      <div className="login-atmosphere" aria-hidden="true"><div className="login-grid" /><div className="login-ring ring-a" /><div className="login-ring ring-b" /><div className="login-spark spark-a" /><div className="login-spark spark-b" /></div>
      <div className="login-layout">
        <section className="login-intro">
          <div className="brand-lockup login-brand"><div className="brand-mark" aria-hidden="true"><span /><span /><span /></div><div><p className="brand-name">Signal Atlas</p><p className="brand-subtitle">Network intelligence</p></div></div>
          <div className="login-message"><div className="eyebrow"><span className="eyebrow-line" /> Controlled intelligence workspace</div><h1>See the shape<br /><em>behind the signal.</em></h1><p>Trace relationships back to evidence. Keep observation, inference, and review distinct.</p></div>
          <div className="login-footnote"><ShieldCheck size={17} /><span>Local Windows profile · evidence-first by default</span></div>
        </section>
        <section className="login-card-wrap">
          <form className="login-card" onSubmit={submit}>
            <div className="login-card-header"><div><p className="section-kicker">Secure access</p><h2>Enter workspace</h2></div><LockKey size={22} className="accent-icon" /></div>
            <label className="field-label" htmlFor="username">Operator ID</label>
            <input id="username" className="text-input" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required />
            <label className="field-label" htmlFor="password">Passphrase</label>
            <input id="password" className="text-input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
            {error && <div className="form-error"><WarningCircle size={16} />{error}</div>}
            <button className="primary-button login-button" type="submit" disabled={busy}>{busy ? <CircleNotch className="spin" size={18} /> : <ArrowRight size={18} />}{busy ? "Authenticating" : "Open workspace"}</button>
            <div className="login-divider"><span>development profiles</span></div>
            <div className="account-list">{demoAccounts.map((account) => <button type="button" className="account-option" key={account.role} onClick={() => useAccount(account)}><span className={`role-dot ${account.role.toLowerCase()}`} /><span><strong>{roleLabel(account.role)}</strong><small>{account.description}</small></span><ArrowUpRight size={14} /></button>)}</div>
            <p className="login-note">Demo credentials are local-only. Change them in <code>.env</code> before sharing a deployment.</p>
          </form>
        </section>
      </div>
    </div>
  );
}

function Workspace({ user, onLogout }: { user: User; onLogout: () => Promise<void> }) {
  const initialRoute = useMemo(() => pathToView(window.location.pathname), []);
  const [activeView, setActiveView] = useState<View>(initialRoute.view);
  const [cameraEventId, setCameraEventId] = useState<string | null>(initialRoute.eventId);
  const navigate = useCallback((next: View) => {
    setActiveView(next);
    setCameraEventId(null);
    const path = viewToPath(next);
    if (window.location.pathname !== path) window.history.pushState({}, "", path);
  }, []);
  useEffect(() => {
    const onPop = () => {
      const route = pathToView(window.location.pathname);
      setActiveView(route.view);
      setCameraEventId(route.eventId);
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [graph, setGraph] = useState<GraphResponse>({ nodes: [], edges: [], depth: 2, center_id: null });
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [geo, setGeo] = useState<MapResponse | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResponseData | null>(null);
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [reports, setReports] = useState<ReportRecord[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<GraphEdge | null>(null);
  const [search, setSearch] = useState("");
  const [depth, setDepth] = useState(2);
  const [relationshipFilter, setRelationshipFilter] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [signals, setSignals] = useState<SignalResponse | null>(null);
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantResult, setAssistantResult] = useState<AssistantResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast>(null);

  const notify = (kind: "success" | "error", message: string) => {
    setToast({ kind, message });
    window.setTimeout(() => setToast(null), 4200);
  };

  const loadGraph = async (nextSearch = search, nextDepth = depth, sourceEntities?: Entity[]) => {
    // Refresh the entity list before resolving a search match. React state
    // updates are asynchronous, so a newly created entity may not be in the
    // closure that handled the create callback yet.
    const availableEntities = sourceEntities ?? await getEntities({ limit: 150 });
    if (!sourceEntities) setEntities(availableEntities);
    const normalizedSearch = nextSearch.trim().toLowerCase();
    const match = normalizedSearch
      ? availableEntities.find((entity) => entity.name.toLowerCase() === normalizedSearch || entity.aliases.some((alias) => alias.toLowerCase() === normalizedSearch)) ?? availableEntities.find((entity) => entity.name.toLowerCase().includes(normalizedSearch))
      : undefined;
    const result = await getGraph({ center_id: match?.id, depth: nextDepth, relationship_types: relationshipFilter || undefined, entity_types: entityTypeFilter || undefined, start_date: startDate ? new Date(startDate).toISOString() : undefined, end_date: endDate ? new Date(endDate).toISOString() : undefined });
    setGraph(result);
    setSelectedNode(null);
    setSelectedEdge(null);
    return result;
  };

  const refresh = async () => {
    setLoading(true);
    try {
      const [healthResult, entityResult, caseResult, evidenceResult, reportResult, timelineResult, geoResult] = await Promise.all([getHealth(), getEntities({ limit: 150 }), getCases(), getEvidence(), getReports(), getTimeline(), getGeo()]);
      setHealth(healthResult);
      setEntities(entityResult);
      setCases(caseResult);
      setEvidence(evidenceResult);
      setReports(reportResult);
      setTimeline(timelineResult);
      setGeo(geoResult);
      if (user.role === "ADMIN") setCandidates(await getCandidates({ status: "PENDING" }));
      await loadGraph("", depth, entityResult);
      if (user.role === "ADMIN" || user.role === "AUDITOR") setAudit(await getAuditEvents());
      if (user.role === "ADMIN") setUsers(await getUsers());
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Workspace data could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const runGraphRefresh = async (event?: FormEvent) => {
    event?.preventDefault();
    setBusy(true);
    try {
      await loadGraph(search, depth);
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Graph could not be refreshed.");
    } finally {
      setBusy(false);
    }
  };

  const executeAnalysis = async (algorithm: string) => {
    setBusy(true);
    try {
      const result = await runAnalysis({ algorithm, center_id: selectedNode?.id });
      setAnalysis(result);
      notify("success", `${algorithm} analysis completed.`);
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Analysis could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const executeSignalScan = async () => {
    setBusy(true);
    try {
      setSignals(await runSignals({ case_id: cases[0]?.id }));
      notify("success", "Analytical signal scan completed.");
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Signal scan could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const submitAssistant = async (event: FormEvent) => {
    event.preventDefault();
    if (!assistantQuestion.trim()) return;
    setBusy(true);
    try {
      setAssistantResult(await askAssistant(assistantQuestion));
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "The assistant could not answer.");
    } finally {
      setBusy(false);
    }
  };

  const activeTitle = navItems.find((item) => item.id === activeView)?.label ?? "Command center";
  const canEdit = user.role === "ADMIN";

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div className="brand-lockup"><div className="brand-mark" aria-hidden="true"><span /><span /><span /></div><div><p className="brand-name">Signal Atlas</p><p className="brand-subtitle">Network intelligence</p></div></div>
        <div className="workspace-label">Workspace</div>
        <nav className="primary-nav" aria-label="Primary navigation">
          {navItems.filter((item) => !item.adminOnly || user.role === "ADMIN" || user.role === "AUDITOR").map((item) => { const Icon = item.icon; return <button className={`nav-item ${activeView === item.id ? "active" : ""}`} key={item.id} type="button" onClick={() => navigate(item.id)}><Icon size={18} weight={activeView === item.id ? "fill" : "regular"} /><span>{item.label}</span>{activeView === item.id && <span className="nav-indicator" />}</button>; })}
        </nav>
        <div className="sidebar-spacer" />
        <div className="integrity-card"><div className="integrity-icon"><ShieldCheck size={18} /></div><div><p>Evidence chain</p><strong>{evidence.length} sources indexed</strong></div><span className="status-dot" /></div>
        <div className="profile-row"><div className="avatar">{initials(user.display_name)}</div><div className="profile-copy"><strong>{user.display_name}</strong><span>{roleLabel(user.role)} · local session</span></div><button className="sidebar-logout" type="button" onClick={() => void onLogout()} aria-label="Sign out"><SignOut size={16} /></button></div>
      </aside>
      <main className="main-canvas">
        <header className="topbar"><div><p className="breadcrumb">Workspace <span>/</span> {activeTitle}</p><h1>{activeTitle}</h1></div><div className="topbar-actions"><div className={`connection-pill ${health?.status === "ok" ? "online" : "offline"}`}><span className="connection-dot" />{health?.status === "ok" ? "API connected" : "API offline"}</div><button className="icon-button" type="button" onClick={() => void refresh()} aria-label="Refresh workspace"><DotsThree size={21} /></button><div className="top-avatar">{initials(user.display_name)}</div></div></header>
        {loading && <div className="loading-strip"><CircleNotch className="spin" size={15} />Syncing local workspace</div>}
        {activeView === "command" && <CommandCenter user={user} health={health} entities={entities} evidence={evidence} graph={graph} onNavigate={setActiveView} assistantQuestion={assistantQuestion} setAssistantQuestion={setAssistantQuestion} assistantResult={assistantResult} onAsk={submitAssistant} busy={busy} signals={signals} onRunSignals={executeSignalScan} />}
        {activeView === "search" && <SearchWorkspace cases={cases} result={searchResults} onSearch={async (params) => { setBusy(true); try { setSearchResults(await searchWorkspace(params)); } catch (error) { notify("error", error instanceof Error ? error.message : "Search failed."); } finally { setBusy(false); } }} busy={busy} />}
        {activeView === "timeline" && <TimelineView timeline={timeline} cases={cases} onRefresh={async (caseId) => setTimeline(await getTimeline({ case_id: caseId || undefined }))} />}
        {activeView === "geo" && <GeoView geo={geo} cases={cases} onRefresh={async (caseId) => setGeo(await getGeo({ case_id: caseId || undefined }))} />}
        {activeView === "network" && <NetworkView entities={entities} evidence={evidence} graph={graph} search={search} setSearch={setSearch} depth={depth} setDepth={setDepth} relationshipFilter={relationshipFilter} setRelationshipFilter={setRelationshipFilter} entityTypeFilter={entityTypeFilter} setEntityTypeFilter={setEntityTypeFilter} startDate={startDate} setStartDate={setStartDate} endDate={endDate} setEndDate={setEndDate} selectedNode={selectedNode} setSelectedNode={setSelectedNode} selectedEdge={selectedEdge} setSelectedEdge={setSelectedEdge} onRefresh={runGraphRefresh} onAnalyze={executeAnalysis} analysis={analysis} canEdit={canEdit} onEntityCreated={async (entity) => { setEntities((current) => [entity, ...current]); const duplicates = await getDuplicateCandidates(entity.id); notify("success", duplicates.length ? `Entity created. ${duplicates.length} possible duplicate(s) need review.` : "Entity created and audit logged."); await loadGraph(entity.name, depth); }} onEntityUpdated={async (entity) => { setEntities((current) => current.map((item) => item.id === entity.id ? entity : item)); notify("success", "Entity updated and audit logged."); await loadGraph(entity.name, depth); }} onEntityArchived={async (entityId) => { setEntities((current) => current.filter((item) => item.id !== entityId)); notify("success", "Entity archived and audit logged."); await loadGraph(search, depth); }} onEntityMerged={async (sourceId, targetId) => { const result = await mergeEntities(sourceId, targetId, "Investigator reviewed duplicate candidate"); setEntities((current) => [result.entity, ...current.filter((item) => item.id !== sourceId && item.id !== targetId)]); notify("success", "Entities merged with relationship reconciliation."); await loadGraph(search, depth); }} onRelationshipCreated={async () => { notify("success", "Relationship created and audit logged."); await loadGraph(search, depth); }} busy={busy} />}
        {activeView === "evidence" && <EvidenceView evidence={evidence} cases={cases} canEdit={canEdit} onUploaded={async (item) => { setEvidence((current) => [item, ...current]); notify("success", "Evidence stored with a traceable record."); }} onExtract={async (evidenceId) => { const created = await extractEvidence(evidenceId); setCandidates((current) => [...created, ...current]); notify("success", `${created.length} candidate fact(s) added to review.`); }} onError={notify} busy={busy} setBusy={setBusy} />}
        {activeView === "review" && user.role === "ADMIN" && <ReviewQueueView candidates={candidates} onApprove={async (candidateId) => { await approveCandidate(candidateId); setCandidates((current) => current.filter((item) => item.id !== candidateId)); notify("success", "Candidate approved and added to trusted records."); }} onReject={async (candidateId) => { await rejectCandidate(candidateId); setCandidates((current) => current.filter((item) => item.id !== candidateId)); notify("success", "Candidate rejected."); }} onError={notify} busy={busy} setBusy={setBusy} />}
        {activeView === "cases" && <CasesView cases={cases} canEdit={canEdit} onCreated={async (item) => { setCases((current) => [item, ...current]); notify("success", "Case created."); }} onError={notify} busy={busy} setBusy={setBusy} />}
        {activeView === "reports" && <ReportsView reports={reports} cases={cases} canEdit={canEdit} onCreated={async (item) => { setReports((current) => [item, ...current]); notify("success", "Report generated from stored records."); }} onError={notify} busy={busy} setBusy={setBusy} onSynthesize={async (caseId) => { const item = await synthesizeReport(caseId); setReports((current) => [item, ...current]); notify("success", "Multi-agent synthesis report generated."); }} onDownload={async (reportId) => { await downloadReport(reportId); notify("success", "Report export downloaded."); }} />}
        {activeView === "users" && user.role === "ADMIN" && <UserAccessView users={users} onCreated={async (item) => { setUsers((current) => [...current, item]); notify("success", "User access created."); }} onError={notify} busy={busy} setBusy={setBusy} />}
        {(activeView === "camera-cameras" || activeView === "camera-monitoring" || activeView === "camera-review" || activeView === "camera-event") && <CameraModule page={activeView === "camera-cameras" ? "cameras" : activeView === "camera-monitoring" ? "monitoring" : activeView === "camera-event" ? "event" : "review"} userRole={user.role} initialEventId={cameraEventId} onNavigate={(page) => navigate(page === "cameras" ? "camera-cameras" : page === "monitoring" ? "camera-monitoring" : page === "event" ? "camera-event" : "camera-review")} />}
        {activeView === "audit" && (user.role === "ADMIN" || user.role === "AUDITOR") && <AuditView events={audit} onRefresh={async () => setAudit(await getAuditEvents())} />}
        <footer className="app-footer"><span>Signal Atlas / local Windows workspace</span><span>Role: {roleLabel(user.role)} · every mutation is audit logged</span></footer>
      </main>
      {toast && <div className={`toast ${toast.kind}`} role="status">{toast.kind === "success" ? <CheckCircle size={17} weight="fill" /> : <WarningCircle size={17} />}{toast.message}<button type="button" onClick={() => setToast(null)} aria-label="Dismiss"><X size={14} /></button></div>}
    </div>
  );
}

type CommandCenterProps = {
  user: User;
  health: HealthPayload | null;
  entities: Entity[];
  evidence: Evidence[];
  graph: GraphResponse;
  onNavigate: (view: View) => void;
  assistantQuestion: string;
  setAssistantQuestion: (value: string) => void;
  assistantResult: AssistantResponse | null;
  onAsk: (event: FormEvent) => Promise<void>;
  busy: boolean;
  signals: SignalResponse | null;
  onRunSignals: () => Promise<void>;
};

function CommandCenter({ user, health, entities, evidence, graph, onNavigate, assistantQuestion, setAssistantQuestion, assistantResult, onAsk, busy, signals, onRunSignals }: CommandCenterProps) {
  const topEntities = [...entities].sort((a, b) => b.name.localeCompare(a.name)).slice(0, 4);
  return <>
    <section className="hero-strip"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-line" /> Live investigation surface</div><h2>Make the unknown<br /><em>legible.</em></h2><p>Trace relationships back to evidence. Keep observation, inference, and review distinct.</p></div><div className="hero-orbit" aria-hidden="true"><div className="orbit orbit-one" /><div className="orbit orbit-two" /><div className="orbit-core"><Hexagon size={38} weight="duotone" /></div><span className="orbit-node node-one" /><span className="orbit-node node-two" /><span className="orbit-node node-three" /></div><div className="hero-meta"><span>Signed in as</span><strong>{roleLabel(user.role)}</strong><small>{user.username} · local session</small></div></section>
    <section className="metric-grid"><article className="metric-card"><div className="metric-label"><span className="metric-index">01</span> Indexed entities</div><div className="metric-value-row"><strong>{entities.length}</strong><UserCircle size={22} className="muted-icon" /></div><p>Active records across the current workspace.</p></article><article className="metric-card"><div className="metric-label"><span className="metric-index">02</span> Source material</div><div className="metric-value-row"><strong>{evidence.length}</strong><Database size={22} className="muted-icon" /></div><p>Evidence items with explicit processing status.</p></article><article className="metric-card"><div className="metric-label"><span className="metric-index">03</span> Network surface</div><div className="metric-value-row"><strong>{graph.edges.length}</strong><Graph size={22} className="muted-icon" /></div><p>Relationships available in the current graph view.</p></article></section>
    <section className="workspace-grid command-grid"><article className="panel network-preview"><div className="panel-heading"><div><p className="section-kicker">Network preview</p><h3>Relationships in view</h3></div><button className="text-button" type="button" onClick={() => onNavigate("network")}>Open explorer <ArrowUpRight size={15} /></button></div>{graph.nodes.length ? <GraphCanvas graph={graph} selectedNodeId={null} selectedEdgeId={null} onSelectNode={() => undefined} onSelectEdge={() => undefined} /> : <div className="empty-state"><Graph size={25} /><strong>No active graph yet</strong><span>Create an entity or load a synthetic case to begin mapping relationships.</span><button className="secondary-button" type="button" onClick={() => onNavigate("network")}>Open network tools <ArrowRight size={15} /></button></div>}</article><article className="panel assistant-panel"><div className="panel-heading"><div><p className="section-kicker">Grounded assistant</p><h3>Ask the evidence</h3></div><Sparkle size={21} className="accent-icon" /></div><p className="panel-intro">The assistant answers from stored graph and source records, then returns citations.</p><form className="assistant-form" onSubmit={onAsk}><textarea value={assistantQuestion} onChange={(event) => setAssistantQuestion(event.target.value)} placeholder="What connects an entity?" rows={3} /><button className="primary-button" type="submit" disabled={busy || !assistantQuestion.trim()}>{busy ? <CircleNotch className="spin" size={16} /> : <PaperPlaneTilt size={16} />} Ask workspace</button></form>{assistantResult && <div className={`assistant-answer ${assistantResult.grounded ? "grounded" : "ungrounded"}`}><div className="answer-label">{assistantResult.grounded ? <><CheckCircle size={14} /> Grounded in stored records</> : <><WarningCircle size={14} /> Insufficient stored context</>}</div><p>{assistantResult.answer}</p>{assistantResult.citations.length > 0 && <div className="citation-list">{assistantResult.citations.slice(0, 3).map((citation, index) => <span key={index}>{String(citation.evidence_title ?? citation.relationship_id ?? "Source reference")}</span>)}</div>}</div>}</article></section>
    <section className="lower-grid"><article className="panel"><div className="panel-heading"><div><p className="section-kicker">Entity register</p><h3>Recently indexed</h3></div><button className="text-button" type="button" onClick={() => onNavigate("network")}>View all <ArrowUpRight size={15} /></button></div><div className="entity-register">{topEntities.length ? topEntities.map((entity) => <div className="register-row" key={entity.id}><div className={`entity-avatar type-${entity.entity_type.toLowerCase()}`}>{initials(entity.name)}</div><div><strong>{entity.name}</strong><span>{entity.entity_type} · {entity.status}</span></div><ArrowUpRight size={15} className="muted-icon" /></div>) : <div className="inline-empty">No entities have been added yet.</div>}</div></article><article className="panel"><div className="panel-heading"><div><p className="section-kicker">Evidence ledger</p><h3>Recent source material</h3></div><button className="text-button" type="button" onClick={() => onNavigate("evidence")}>Open vault <ArrowUpRight size={15} /></button></div><div className="entity-register">{evidence.slice(0, 4).map((item) => <div className="register-row" key={item.id}><div className="file-avatar"><FileText size={17} /></div><div><strong>{item.title}</strong><span>{item.category} · {formatDate(item.created_at)}</span></div><span className={`status-chip ${statusClass(item.status)}`}>{item.status}</span></div>)}{!evidence.length && <div className="inline-empty">No source material has been indexed yet.</div>}</div></article></section><section className="panel signals-panel"><div className="panel-heading"><div><p className="section-kicker">Pattern detection</p><h3>Review signals</h3></div><button className="secondary-button compact" type="button" onClick={() => void onRunSignals()} disabled={busy}>{busy ? <CircleNotch className="spin" size={14} /> : <Pulse size={14} />} Run scan</button></div>{signals ? <>{signals.signals.length ? <div className="signal-list">{signals.signals.slice(0, 4).map((signal) => <div className="signal-row" key={`${signal.signal_type}-${signal.title}`}><div className={`signal-marker ${signal.severity.toLowerCase()}`}><WarningCircle size={15} /></div><div><strong>{signal.title}</strong><span>{signal.explanation}</span><small>{signal.evidence_ids.length} evidence reference(s) · requires review</small></div></div>)}</div> : <div className="inline-empty">No threshold-crossing signals for the current baseline.</div>}<p className="timeline-explanation">{signals.explanation}</p></> : <div className="empty-state signal-empty"><Pulse size={25} /><strong>No scan recorded</strong><span>Run a scan to surface measurable changes for analyst review.</span></div>}</section>
  </>;
}

function SearchWorkspace({ cases, result, onSearch, busy }: { cases: CaseRecord[]; result: SearchResponseData | null; onSearch: (params: { q: string; case_id?: string; entity_type?: string; status?: string; evidence_category?: string; relationship_type?: string }) => Promise<void>; busy: boolean }) {
  const [query, setQuery] = useState("");
  const [caseId, setCaseId] = useState("");
  const [entityType, setEntityType] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const submit = (event: FormEvent) => { event.preventDefault(); if (query.trim()) void onSearch({ q: query.trim(), case_id: caseId || undefined, entity_type: entityType || undefined, status: status || undefined, evidence_category: category || undefined }); };
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Investigation workspace</p><h2>Search records</h2><p className="toolbar-description">Search entities, cases, and source material together, then open the relevant graph or evidence context.</p></div><div className="toolbar-stat"><MagnifyingGlass size={17} /><strong>{result?.total ?? 0}</strong><span>matching records</span></div></section><form className="panel search-workspace-form" onSubmit={submit}><div className="search-workspace-input"><MagnifyingGlass size={19} /><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search a person, phone, vehicle, case, FIR, or source..." /><button className="primary-button compact" type="submit" disabled={busy || !query.trim()}>{busy ? <CircleNotch className="spin" size={15} /> : <ArrowRight size={15} />} Search</button></div><div className="search-filters"><select className="text-input" value={caseId} onChange={(event) => setCaseId(event.target.value)}><option value="">All cases</option>{cases.map((item) => <option value={item.id} key={item.id}>{item.case_number}</option>)}</select><select className="text-input" value={entityType} onChange={(event) => setEntityType(event.target.value)}><option value="">All entity types</option><option value="PERSON">People</option><option value="PHONE">Phones</option><option value="VEHICLE">Vehicles</option><option value="LOCATION">Locations</option><option value="ORGANIZATION">Organizations</option></select><select className="text-input" value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option><option value="UNKNOWN">Unknown</option><option value="RELEVANT">Relevant</option><option value="ATTENTION">Attention</option></select><select className="text-input" value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All evidence sources</option><option value="FIR">FIR</option><option value="CDR">CDR</option><option value="POLICE_REPORT">Police report</option><option value="INTELLIGENCE_REPORT">Intelligence report</option></select></div></form><section className="panel search-results-panel"><div className="panel-heading"><div><p className="section-kicker">Result set</p><h3>{result ? `${result.total} records` : "Ready to search"}</h3></div>{result && <span className="table-count">Query: {result.query}</span>}</div>{result?.results.length ? <div className="search-result-list">{result.results.map((item) => <button className="search-result" type="button" key={`${item.result_type}-${item.id}`}><div className={`result-type type-${item.result_type.toLowerCase()}`}>{item.result_type.slice(0, 1)}</div><div><strong>{item.title}</strong><span>{item.subtitle}</span></div><div className="result-meta">{item.entity_type && <span>{item.entity_type}</span>}{item.status && <span className={`status-chip ${statusClass(item.status)}`}>{item.status}</span>}<ArrowUpRight size={15} /></div></button>)}</div> : result ? <div className="empty-state"><MagnifyingGlass size={26} /><strong>No matching records</strong><span>Try a broader name, remove a filter, or search the source text.</span></div> : <div className="empty-state"><MagnifyingGlass size={26} /><strong>Search the workspace</strong><span>Results stay grounded in stored records and source material.</span></div>}<p className="timeline-explanation">{result?.explanation ?? "Search is scoped to active records unless an archived-record view is explicitly added."}</p></section></>;
}

function GeoView({ geo, cases, onRefresh }: { geo: MapResponse | null; cases: CaseRecord[]; onRefresh: (caseId: string) => Promise<void> }) {
  const [caseId, setCaseId] = useState("");
  const points = geo?.points ?? [];
  const max = Math.max(...points.map((point) => point.relationship_count), 1);
  const project = (latitude: number, longitude: number) => ({ x: ((longitude + 180) / 360) * 100, y: ((90 - latitude) / 180) * 100 });
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Geographic analysis</p><h2>Location view</h2><p className="toolbar-description">Plot only entities with explicit coordinates. Missing locations remain unplotted rather than guessed.</p></div><div className="toolbar-actions"><select className="text-input compact-select" value={caseId} onChange={(event) => { setCaseId(event.target.value); void onRefresh(event.target.value); }}><option value="">All active cases</option>{cases.map((item) => <option value={item.id} key={item.id}>{item.case_number}</option>)}</select><button className="secondary-button" type="button" onClick={() => void onRefresh(caseId)}><MapPin size={16} /> Refresh</button></div></section><section className="geo-summary"><div><span>Plotted entities</span><strong>{points.length}</strong></div><div><span>Relationship context</span><strong>{geo?.total_relationships ?? 0}</strong></div><div><span>Coverage rule</span><strong>Explicit coordinates only</strong></div></section><section className="panel geo-panel"><div className="panel-heading"><div><p className="section-kicker">Coordinate surface</p><h3>Relevant locations</h3></div><span className="status-chip status-neutral">NO GEOCODING</span></div>{points.length ? <div className="map-canvas"><div className="map-grid" />{points.map((point) => { const position = project(point.latitude, point.longitude); const size = 10 + Math.min(point.relationship_count / max * 14, 14); return <div className="map-point" key={point.entity_id} style={{ left: `${position.x}%`, top: `${position.y}%`, width: size, height: size }} title={`${point.name} · ${point.relationship_count} links`}><span>{point.name}</span></div>; })}<div className="map-axis-x"><span>West</span><span>East</span></div><div className="map-axis-y"><span>North</span><span>South</span></div></div> : <div className="empty-state"><MapPin size={26} /><strong>No coordinates stored</strong><span>Add explicit latitude/longitude metadata to an entity to plot it here.</span></div>}<p className="timeline-explanation">{geo?.explanation ?? "Geographic data is not available."}</p></section></>;
}

function TimelineView({ timeline, cases, onRefresh }: { timeline: TimelineResponse | null; cases: CaseRecord[]; onRefresh: (caseId: string) => Promise<void> }) {
  const [caseId, setCaseId] = useState("");
  const points = timeline?.points ?? [];
  const max = Math.max(...points.map((point) => point.relationship_count), 1);
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Temporal analysis</p><h2>Network timeline</h2><p className="toolbar-description">See when observed relationships appeared, how activity accumulates, and where the graph changed.</p></div><div className="toolbar-actions"><select className="text-input compact-select" value={caseId} onChange={(event) => { setCaseId(event.target.value); void onRefresh(event.target.value); }}><option value="">All active cases</option>{cases.map((item) => <option value={item.id} key={item.id}>{item.case_number}</option>)}</select><button className="secondary-button" type="button" onClick={() => void onRefresh(caseId)}><Clock size={16} /> Refresh</button></div></section><section className="timeline-summary"><div><span>Observed window</span><strong>{timeline?.start_date && timeline.end_date ? `${timeline.start_date} → ${timeline.end_date}` : "No dated relationships"}</strong></div><div><span>Relationship events</span><strong>{points.reduce((sum, point) => sum + point.relationship_count, 0)}</strong></div><div><span>Peak day</span><strong>{points.length ? `${points.reduce((best, point) => point.relationship_count > best.relationship_count ? point : best, points[0]).date} · ${max}` : "—"}</strong></div></section><section className="panel timeline-panel"><div className="panel-heading"><div><p className="section-kicker">Observed activity</p><h3>Relationship appearance</h3></div><span className="status-chip status-neutral">DESCRIPTIVE</span></div>{points.length ? <><div className="timeline-chart">{points.map((point) => <div className="timeline-column" key={point.date}><div className="timeline-bar-wrap"><div className="timeline-bar" style={{ height: `${Math.max((point.relationship_count / max) * 100, 5)}%` }} title={`${point.relationship_count} relationships`} /></div><span>{point.date.slice(5)}</span></div>)}</div><div className="timeline-axis"><span>First observed</span><span>Cumulative links: {points.at(-1)?.cumulative_relationships ?? 0}</span><span>Latest observed</span></div></> : <div className="empty-state"><Clock size={26} /><strong>No dated relationships</strong><span>Relationships with timestamps will appear here after evidence-backed links are added.</span></div>}<p className="timeline-explanation">{timeline?.explanation ?? "Timeline data is not available."}</p></section></>;
}

type NetworkViewProps = {
  entities: Entity[];
  evidence: Evidence[];
  graph: GraphResponse;
  search: string;
  setSearch: (value: string) => void;
  depth: number;
  setDepth: (value: number) => void;
  relationshipFilter: string;
  setRelationshipFilter: (value: string) => void;
  entityTypeFilter: string;
  setEntityTypeFilter: (value: string) => void;
  startDate: string;
  setStartDate: (value: string) => void;
  endDate: string;
  setEndDate: (value: string) => void;
  selectedNode: GraphNode | null;
  setSelectedNode: (node: GraphNode | null) => void;
  selectedEdge: GraphEdge | null;
  setSelectedEdge: (edge: GraphEdge | null) => void;
  onRefresh: (event?: FormEvent) => Promise<void>;
  onAnalyze: (algorithm: string) => Promise<void>;
  analysis: AnalysisResponse | null;
  canEdit: boolean;
  onEntityCreated: (entity: Entity) => Promise<void>;
  onEntityUpdated: (entity: Entity) => Promise<void>;
  onEntityArchived: (entityId: string) => Promise<void>;
  onEntityMerged: (sourceId: string, targetId: string) => Promise<void>;
  onRelationshipCreated: () => Promise<void>;
  busy: boolean;
};

function NetworkView({ entities, evidence, graph, search, setSearch, depth, setDepth, relationshipFilter, setRelationshipFilter, entityTypeFilter, setEntityTypeFilter, startDate, setStartDate, endDate, setEndDate, selectedNode, setSelectedNode, selectedEdge, setSelectedEdge, onRefresh, onAnalyze, analysis, canEdit, onEntityCreated, onEntityUpdated, onEntityArchived, onEntityMerged, onRelationshipCreated, busy }: NetworkViewProps) {
  const [showEntityForm, setShowEntityForm] = useState(false);
  const [showRelationshipForm, setShowRelationshipForm] = useState(false);
  const [entityForm, setEntityForm] = useState({ name: "", entity_type: "PERSON", aliases: "" });
  const [relationshipForm, setRelationshipForm] = useState({ source_id: "", target_id: "", relationship_type: "ASSOCIATED_WITH", timestamp: "", evidence_id: "" });
  const [formError, setFormError] = useState("");
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({ name: "", status: "UNKNOWN", notes: "" });
  const [duplicates, setDuplicates] = useState<DuplicateMatch[]>([]);

  useEffect(() => {
    if (!selectedNode) { setDuplicates([]); return; }
    void getDuplicateCandidates(selectedNode.id).then(setDuplicates).catch(() => setDuplicates([]));
  }, [selectedNode]);

  const submitEntity = async (event: FormEvent) => {
    event.preventDefault(); setFormError("");
    try { const entity = await createEntity({ name: entityForm.name, entity_type: entityForm.entity_type, aliases: entityForm.aliases.split(",").map((item) => item.trim()).filter(Boolean) }); await onEntityCreated(entity); setEntityForm({ name: "", entity_type: "PERSON", aliases: "" }); setShowEntityForm(false); } catch (error) { setFormError(error instanceof Error ? error.message : "Entity could not be created."); }
  };
  const submitRelationship = async (event: FormEvent) => {
    event.preventDefault(); setFormError("");
    try { await createRelationship({ source_id: relationshipForm.source_id, target_id: relationshipForm.target_id, relationship_type: relationshipForm.relationship_type, timestamp: relationshipForm.timestamp ? new Date(relationshipForm.timestamp).toISOString() : undefined, evidence_id: relationshipForm.evidence_id || undefined }); await onRelationshipCreated(); setShowRelationshipForm(false); } catch (error) { setFormError(error instanceof Error ? error.message : "Relationship could not be created."); }
  };
  const selectedEntity = selectedNode ? entities.find((entity) => entity.id === selectedNode.id) : null;
  const beginEdit = (entity: Entity) => { setEditForm({ name: entity.name, status: entity.status, notes: entity.notes }); setEditing(true); };
  const saveEdit = async (event: FormEvent) => { event.preventDefault(); if (!selectedEntity) return; try { const updated = await updateEntity(selectedEntity.id, editForm); await onEntityUpdated(updated); setEditing(false); } catch (error) { setFormError(error instanceof Error ? error.message : "Entity could not be updated."); } };
  const archiveSelected = async () => { if (!selectedEntity) return; try { await onEntityArchived(selectedEntity.id); setSelectedNode(null); } catch (error) { setFormError(error instanceof Error ? error.message : "Entity could not be archived."); } };
  return <>
    <section className="workspace-toolbar"><div><p className="section-kicker">Graph workbench</p><h2>Explore the network</h2><p className="toolbar-description">Search a name, expand its neighborhood, and inspect the evidence behind each link.</p></div><div className="toolbar-actions">{canEdit && <button className="secondary-button" type="button" onClick={() => setShowEntityForm((value) => !value)}><Plus size={16} /> Entity</button>}{canEdit && <button className="secondary-button" type="button" onClick={() => setShowRelationshipForm((value) => !value)}><ShareIcon /> Relationship</button>}</div></section>
    <section className="network-toolbar panel"><form className="search-form" onSubmit={onRefresh}><MagnifyingGlass size={18} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search an entity name or alias" /><button className="primary-button compact" type="submit" disabled={busy}>{busy ? <CircleNotch className="spin" size={15} /> : <ArrowRight size={15} />} Explore</button></form><div className="filter-group"><Funnel size={15} /><label htmlFor="depth">Depth</label><select id="depth" value={depth} onChange={(event) => { const value = Number(event.target.value); setDepth(value); void onRefresh(); }}><option value={1}>1 hop</option><option value={2}>2 hops</option><option value={3}>3 hops</option><option value={4}>4 hops</option></select><select aria-label="Relationship filter" value={relationshipFilter} onChange={(event) => { setRelationshipFilter(event.target.value); void onRefresh(); }}><option value="">All links</option><option value="CALLS">Calls</option><option value="ASSOCIATED_WITH">Associated</option><option value="OWNS">Owns</option><option value="USES">Uses</option><option value="VISITED">Visited</option><option value="WORKS_FOR">Works for</option></select><select aria-label="Entity type filter" value={entityTypeFilter} onChange={(event) => { setEntityTypeFilter(event.target.value); void onRefresh(); }}><option value="">All types</option><option value="PERSON">People</option><option value="PHONE">Phones</option><option value="VEHICLE">Vehicles</option><option value="LOCATION">Locations</option><option value="ORGANIZATION">Organizations</option></select><input aria-label="Start date" type="date" value={startDate} onChange={(event) => { setStartDate(event.target.value); void onRefresh(); }} /><input aria-label="End date" type="date" value={endDate} onChange={(event) => { setEndDate(event.target.value); void onRefresh(); }} /><button className="icon-button small" type="button" onClick={() => void onRefresh()} aria-label="Refresh graph"><DotsThree size={17} /></button></div></section>
    {formError && <div className="form-error page-error"><WarningCircle size={16} />{formError}</div>}
    {showEntityForm && canEdit && <form className="panel inline-form" onSubmit={submitEntity}><div><p className="section-kicker">Manual record</p><h3>Add entity</h3></div><label className="field-label">Name<input className="text-input" value={entityForm.name} onChange={(event) => setEntityForm({ ...entityForm, name: event.target.value })} required /></label><label className="field-label">Type<select className="text-input" value={entityForm.entity_type} onChange={(event) => setEntityForm({ ...entityForm, entity_type: event.target.value })}><option>PERSON</option><option>PHONE</option><option>VEHICLE</option><option>LOCATION</option><option>ORGANIZATION</option><option>EVENT</option></select></label><label className="field-label">Aliases<input className="text-input" value={entityForm.aliases} onChange={(event) => setEntityForm({ ...entityForm, aliases: event.target.value })} placeholder="comma separated" /></label><button className="primary-button compact" type="submit">Save entity</button></form>}
    {showRelationshipForm && canEdit && <form className="panel inline-form" onSubmit={submitRelationship}><div><p className="section-kicker">Graph edge</p><h3>Link entities</h3></div><label className="field-label">Source<select className="text-input" value={relationshipForm.source_id} onChange={(event) => setRelationshipForm({ ...relationshipForm, source_id: event.target.value })} required><option value="">Select source</option>{entities.map((entity) => <option value={entity.id} key={entity.id}>{entity.name}</option>)}</select></label><label className="field-label">Relationship<input className="text-input" value={relationshipForm.relationship_type} onChange={(event) => setRelationshipForm({ ...relationshipForm, relationship_type: event.target.value })} /></label><label className="field-label">Recorded at<input className="text-input" type="datetime-local" value={relationshipForm.timestamp} onChange={(event) => setRelationshipForm({ ...relationshipForm, timestamp: event.target.value })} /></label><label className="field-label">Evidence<select className="text-input" value={relationshipForm.evidence_id} onChange={(event) => setRelationshipForm({ ...relationshipForm, evidence_id: event.target.value })}><option value="">No evidence attached</option>{evidence.map((item) => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><label className="field-label">Target<select className="text-input" value={relationshipForm.target_id} onChange={(event) => setRelationshipForm({ ...relationshipForm, target_id: event.target.value })} required><option value="">Select target</option>{entities.map((entity) => <option value={entity.id} key={entity.id}>{entity.name}</option>)}</select></label><button className="primary-button compact" type="submit">Save relationship</button></form>}
    <section className="network-layout"><article className="panel graph-panel"><GraphCanvas graph={graph} selectedNodeId={selectedNode?.id ?? null} selectedEdgeId={selectedEdge?.id ?? null} onSelectNode={setSelectedNode} onSelectEdge={setSelectedEdge} /><div className="analysis-strip"><span>Run structural analysis</span><div><button className="analysis-button" type="button" onClick={() => void onAnalyze("centrality")} disabled={busy}>Degree</button><button className="analysis-button" type="button" onClick={() => void onAnalyze("betweenness")} disabled={busy}>Betweenness</button><button className="analysis-button" type="button" onClick={() => void onAnalyze("pagerank")} disabled={busy}>PageRank</button></div></div></article><aside className="panel detail-panel">{selectedEdge ? <EdgeDetail edge={selectedEdge} entities={entities} evidence={evidence} /> : selectedEntity ? <EntityDetail entity={selectedEntity} canEdit={canEdit} editing={editing} editForm={editForm} setEditForm={setEditForm} onEdit={() => beginEdit(selectedEntity)} onSave={saveEdit} onCancel={() => setEditing(false)} onArchive={archiveSelected} duplicates={duplicates} onMerge={async (targetId) => { if (window.confirm("Merge these records? The source will be archived and its relationships reconciled.")) { await onEntityMerged(selectedEntity.id, targetId); setEditing(false); } }} /> : <div className="detail-empty"><div className="detail-empty-icon"><Graph size={25} /></div><h3>Select a node or link</h3><p>Inspect identity, status, and provenance without leaving the graph.</p><div className="detail-rule"><ShieldCheck size={16} /><span>Analytical signals remain distinct from source status.</span></div></div>}{analysis && <div className="analysis-result"><div className="analysis-result-head"><div><p className="section-kicker">Latest run</p><strong>{analysis.algorithm}</strong></div><span>{analysis.component_count} components</span></div><p>{analysis.explanation}</p>{analysis.metrics.slice(0, 3).map((metric) => <div className="metric-result" key={metric.entity_id}><span>{metric.rank}. {metric.name}</span><b>{metric.value.toFixed(3)}</b></div>)}</div>}</aside></section>
  </>;
}

function ShareIcon() { return <span className="share-glyph">↗</span>; }

function EntityDetail({ entity, canEdit, editing, editForm, setEditForm, onEdit, onSave, onCancel, onArchive, duplicates, onMerge }: { entity: Entity; canEdit: boolean; editing: boolean; editForm: { name: string; status: string; notes: string }; setEditForm: (value: { name: string; status: string; notes: string }) => void; onEdit: () => void; onSave: (event: FormEvent) => Promise<void>; onCancel: () => void; onArchive: () => Promise<void>; duplicates: DuplicateMatch[]; onMerge: (targetId: string) => Promise<void> }) {
  return <div className="detail-content"><div className="detail-identity"><div className={`entity-avatar large type-${entity.entity_type.toLowerCase()}`}>{initials(entity.name)}</div><div><p className="section-kicker">{entity.entity_type}</p><h3>{entity.name}</h3><span className={`status-chip ${statusClass(entity.status)}`}>{entity.status}</span></div></div>{editing ? <form className="edit-form" onSubmit={onSave}><label className="field-label">Name<input className="text-input" value={editForm.name} onChange={(event) => setEditForm({ ...editForm, name: event.target.value })} /></label><label className="field-label">Status<input className="text-input" value={editForm.status} onChange={(event) => setEditForm({ ...editForm, status: event.target.value })} /></label><label className="field-label">Notes<textarea className="text-input" rows={3} value={editForm.notes} onChange={(event) => setEditForm({ ...editForm, notes: event.target.value })} /></label><div className="edit-actions"><button className="primary-button compact" type="submit">Save changes</button><button className="secondary-button compact" type="button" onClick={onCancel}>Cancel</button></div></form> : <><div className="detail-stats"><div><span>Aliases</span><strong>{entity.aliases.length || "None"}</strong></div><div><span>Record state</span><strong>{entity.record_state}</strong></div></div><div className="detail-section"><span className="detail-label">Notes</span><p>{entity.notes || "No notes attached to this record."}</p></div><div className="detail-section"><span className="detail-label">Provenance</span><p>Created {formatDate(entity.created_at)} · source-backed record {entity.id}</p></div>{entity.entity_type === "PERSON" && <PersonReferencePhotos entityId={entity.id} entityName={entity.name} canEdit={canEdit} />}{duplicates.length > 0 && <div className="duplicate-box"><div className="duplicate-head"><span>Possible duplicates</span><b>{duplicates.length}</b></div>{duplicates.slice(0, 3).map((duplicate) => <div className="duplicate-row" key={duplicate.entity_id}><div><strong>{duplicate.name}</strong><span>{Math.round(duplicate.score * 100)}% · {duplicate.signals.join(", ")}</span></div>{canEdit && <button className="secondary-button compact" type="button" onClick={() => void onMerge(duplicate.entity_id)}>Merge</button>}</div>)}</div>}{canEdit && <div className="detail-actions"><button className="secondary-button compact" type="button" onClick={onEdit}>Edit record</button><button className="danger-button compact" type="button" onClick={() => void onArchive()}>Archive</button></div>}</>}</div>;
}

function EdgeDetail({ edge, entities, evidence }: { edge: GraphEdge; entities: Entity[]; evidence: Evidence[] }) {
  const source = entities.find((entity) => entity.id === edge.source);
  const target = entities.find((entity) => entity.id === edge.target);
  const sourceEvidence = evidence.find((item) => item.id === edge.evidence_id);
  return <div className="detail-content"><div className="edge-heading"><div className="edge-symbol"><ShareIcon /></div><div><p className="section-kicker">Relationship</p><h3>{edge.relationship_type.replaceAll("_", " ")}</h3></div></div><div className="edge-path"><span>{source?.name ?? edge.source}</span><ArrowRight size={16} /><span>{target?.name ?? edge.target}</span></div><div className="detail-stats"><div><span>Confidence</span><strong>{Math.round(edge.confidence * 100)}%</strong></div><div><span>State</span><strong>{edge.record_state}</strong></div></div><div className="detail-section"><span className="detail-label">Evidence reference</span><p>{sourceEvidence ? `${sourceEvidence.title} · ${sourceEvidence.status} · ${sourceEvidence.id}` : edge.evidence_id ?? "No evidence record attached. Treat this link as an unverified relationship."}</p></div>{sourceEvidence?.extracted_text && <div className="detail-section"><span className="detail-label">Source excerpt</span><p className="source-excerpt">{sourceEvidence.extracted_text.slice(0, 260)}{sourceEvidence.extracted_text.length > 260 ? "…" : ""}</p></div>}<div className="detail-section"><span className="detail-label">Recorded time</span><p>{formatDateTime(edge.timestamp)}</p></div></div>;
}

function EvidenceView({ evidence, cases, canEdit, onUploaded, onExtract, onError, busy, setBusy }: { evidence: Evidence[]; cases: CaseRecord[]; canEdit: boolean; onUploaded: (item: Evidence) => Promise<void>; onExtract: (evidenceId: string) => Promise<void>; onError: (kind: "error" | "success", message: string) => void; busy: boolean; setBusy: (value: boolean) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("OTHER");
  const [caseId, setCaseId] = useState("");
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    if (!file) { setError("Choose a source file first."); return; }
    setBusy(true);
    try { const form = new FormData(); form.append("file", file); form.append("title", title || file.name); form.append("category", category); if (caseId) form.append("case_id", caseId); const item = await uploadEvidence(form); await onUploaded(item); setFile(null); setTitle(""); setCaseId(""); } catch (reason) { const message = reason instanceof Error ? reason.message : "Upload failed."; setError(message); onError("error", message); } finally { setBusy(false); }
  };
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Evidence ledger</p><h2>Source material</h2><p className="toolbar-description">Every source keeps its file identity, processing state, and case context.</p></div><div className="toolbar-stat"><Database size={17} /><strong>{evidence.length}</strong><span>indexed items</span></div></section>{canEdit && <form className="panel upload-panel" onSubmit={submit}><div className="upload-icon"><CloudArrowUp size={24} /></div><div className="upload-copy"><p className="section-kicker">Admin intake</p><h3>Add a source file</h3><p>PDF, TXT, CSV, XLSX, and image files up to 25 MB.</p></div><label className="file-picker"><UploadSimple size={17} />{file ? file.name : "Choose file"}<input type="file" accept=".pdf,.txt,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label><label className="field-label">Title<input className="text-input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Optional descriptive title" /></label><label className="field-label">Category<select className="text-input" value={category} onChange={(event) => setCategory(event.target.value)}><option>FIR</option><option>POLICE_REPORT</option><option>CDR</option><option>FINANCIAL_TRANSACTION</option><option>SURVEILLANCE_REPORT</option><option>INTELLIGENCE_REPORT</option><option>OTHER</option></select></label><label className="field-label">Case<select className="text-input" value={caseId} onChange={(event) => setCaseId(event.target.value)}><option value="">Unassigned intake</option>{cases.map((item) => <option value={item.id} key={item.id}>{item.case_number}</option>)}</select></label><button className="primary-button compact" type="submit" disabled={busy}>{busy ? <CircleNotch className="spin" size={15} /> : <UploadSimple size={15} />} Store evidence</button>{error && <div className="form-error"><WarningCircle size={15} />{error}</div>}</form>}<section className="panel table-panel"><div className="panel-heading"><div><p className="section-kicker">Stored sources</p><h3>Evidence history</h3></div><span className="table-count">{evidence.length} records</span></div>{evidence.length ? <div className="data-table"><div className="table-row table-head"><span>Source</span><span>Category</span><span>Size</span><span>Status</span><span>Added</span></div>{evidence.map((item) => <div className="table-row" key={item.id}><div className="table-source"><div className="file-avatar"><FileText size={17} /></div><div><strong>{item.title}</strong><span>{item.original_filename} · {item.id}</span></div>{canEdit && <button className="table-action" type="button" onClick={() => void onExtract(item.id)}><Sparkle size={13} /> Extract</button>}</div><span>{item.category.replaceAll("_", " ")}</span><span>{formatBytes(item.size_bytes)}</span><span className={`status-chip ${statusClass(item.status)}`}>{item.status}</span><span>{formatDate(item.created_at)}</span></div>)}</div> : <div className="empty-state table-empty"><Database size={26} /><strong>No evidence records</strong><span>Upload a source file to begin the evidence chain.</span></div>}</section></>;
}

function ReviewQueueView({ candidates, onApprove, onReject, onError, busy, setBusy }: { candidates: Candidate[]; onApprove: (candidateId: string) => Promise<void>; onReject: (candidateId: string) => Promise<void>; onError: (kind: "error" | "success", message: string) => void; busy: boolean; setBusy: (value: boolean) => void }) {
  const [filter, setFilter] = useState("ALL");
  const visible = filter === "ALL" ? candidates : candidates.filter((candidate) => candidate.candidate_type === filter);
  const act = async (candidateId: string, action: "approve" | "reject") => { setBusy(true); try { if (action === "approve") await onApprove(candidateId); else await onReject(candidateId); } catch (error) { onError("error", error instanceof Error ? error.message : "Candidate review failed."); } finally { setBusy(false); } };
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Human-in-the-loop extraction</p><h2>Review queue</h2><p className="toolbar-description">Candidate facts stay outside the trusted graph until an administrator approves or rejects them.</p></div><div className="toolbar-stat"><Sparkle size={17} /><strong>{candidates.length}</strong><span>pending candidates</span></div></section><section className="panel review-panel"><div className="review-toolbar"><div className="review-tabs">{["ALL", "PERSON", "RELATIONSHIP", "PHONE", "VEHICLE", "LOCATION"].map((item) => <button className={filter === item ? "active" : ""} type="button" key={item} onClick={() => setFilter(item)}>{item === "ALL" ? "All candidates" : item.toLowerCase()}</button>)}</div><span className="table-count">{visible.length} shown</span></div>{visible.length ? <div className="candidate-list">{visible.map((candidate) => <article className="candidate-row" key={candidate.id}><div className="candidate-type">{candidate.candidate_type}</div><div className="candidate-main"><strong>{candidate.value}</strong><span>Evidence {candidate.evidence_id} · confidence {Math.round(candidate.confidence * 100)}%</span><small>“{candidate.source_span}”</small></div><div className="candidate-actions"><button className="primary-button compact" type="button" disabled={busy} onClick={() => void act(candidate.id, "approve")}><CheckCircle size={14} /> Approve</button><button className="secondary-button compact" type="button" disabled={busy} onClick={() => void act(candidate.id, "reject")}><X size={14} /> Reject</button></div></article>)}</div> : <div className="empty-state"><Sparkle size={26} /><strong>Review queue is clear</strong><span>Run extraction from an evidence record to create candidate facts here.</span></div>}</section></>;
}

function CasesView({ cases, canEdit, onCreated, onError, busy, setBusy }: { cases: CaseRecord[]; canEdit: boolean; onCreated: (item: CaseRecord) => Promise<void>; onError: (kind: "error" | "success", message: string) => void; busy: boolean; setBusy: (value: boolean) => void }) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ case_number: "", title: "", description: "" });
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); setBusy(true); try { const item = await createCase(form); await onCreated(item); setForm({ case_number: "", title: "", description: "" }); setShowForm(false); } catch (reason) { const message = reason instanceof Error ? reason.message : "Case could not be created."; setError(message); onError("error", message); } finally { setBusy(false); } };
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Investigation context</p><h2>Cases</h2><p className="toolbar-description">Keep entities, evidence, analysis, and reports inside a reopenable investigation.</p></div>{canEdit && <button className="primary-button" type="button" onClick={() => setShowForm((value) => !value)}><Plus size={16} /> New case</button>}</section>{showForm && canEdit && <form className="panel inline-form case-form" onSubmit={submit}><div><p className="section-kicker">Case intake</p><h3>Start an investigation</h3></div><label className="field-label">Case number<input className="text-input" value={form.case_number} onChange={(event) => setForm({ ...form, case_number: event.target.value })} placeholder="CASE-2026-001" required /></label><label className="field-label">Title<input className="text-input" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required /></label><label className="field-label wide">Description<textarea className="text-input" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={2} /></label><button className="primary-button compact" type="submit" disabled={busy}>Create case</button>{error && <div className="form-error"><WarningCircle size={15} />{error}</div>}</form>}<section className="case-grid">{cases.length ? cases.map((item) => <article className="panel case-card" key={item.id}><div className="case-card-top"><span className="case-number">{item.case_number}</span><span className={`status-chip ${statusClass(item.status)}`}>{item.status}</span></div><h3>{item.title}</h3><p>{item.description || "No case notes have been added."}</p><div className="case-card-footer"><span><UserCircle size={15} /> {item.priority.toLowerCase()} priority</span><span>{formatDate(item.updated_at)}</span></div></article>) : <div className="panel empty-state case-empty"><Hexagon size={27} /><strong>No active cases</strong><span>Create a case to give the investigation a durable context.</span></div>}</section></>;
}

function ReportsView({ reports, cases, canEdit, onCreated, onError, busy, setBusy, onSynthesize, onDownload }: { reports: ReportRecord[]; cases: CaseRecord[]; canEdit: boolean; onCreated: (item: ReportRecord) => Promise<void>; onError: (kind: "error" | "success", message: string) => void; busy: boolean; setBusy: (value: boolean) => void; onSynthesize: (caseId: string) => Promise<void>; onDownload: (reportId: string) => Promise<void> }) {
  const [title, setTitle] = useState("Network intelligence report");
  const [summary, setSummary] = useState("");
  const [caseId, setCaseId] = useState("");
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); setBusy(true); try { const item = await createReport({ title, summary, case_id: caseId || null }); await onCreated(item); setSummary(""); } catch (reason) { const message = reason instanceof Error ? reason.message : "Report could not be generated."; setError(message); onError("error", message); } finally { setBusy(false); } };
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Structured output</p><h2>Intelligence reports</h2><p className="toolbar-description">Generate a readable summary that points back to stored graph and evidence records.</p></div><div className="toolbar-actions">{cases[0] && canEdit && <button className="secondary-button" type="button" onClick={() => void onSynthesize(cases[0].id)} disabled={busy}><Robot size={16} /> Run multi-agent synthesis</button>}<div className="toolbar-stat"><FilePdf size={17} /><strong>{reports.length}</strong><span>generated reports</span></div></div></section><section className="report-layout"><form className="panel report-form" onSubmit={submit}><div className="panel-heading"><div><p className="section-kicker">Report builder</p><h3>Summarize stored context</h3></div><Sparkle size={20} className="accent-icon" /></div><label className="field-label">Report title<input className="text-input" value={title} onChange={(event) => setTitle(event.target.value)} required /></label><label className="field-label">Case<select className="text-input" value={caseId} onChange={(event) => setCaseId(event.target.value)}><option value="">All active context</option>{cases.map((item) => <option value={item.id} key={item.id}>{item.case_number} · {item.title}</option>)}</select></label><label className="field-label">Analyst note<textarea className="text-input" value={summary} onChange={(event) => setSummary(event.target.value)} rows={5} placeholder="Add context for the report..." /></label>{error && <div className="form-error"><WarningCircle size={15} />{error}</div>}<button className="primary-button" type="submit" disabled={busy || !canEdit}>{busy ? <CircleNotch className="spin" size={16} /> : <FilePdf size={16} />} Generate report</button>{!canEdit && <p className="permission-note"><LockKey size={14} /> Analysts can generate reports; source data remains read-only.</p>}</form><div className="report-list">{reports.length ? reports.map((report) => <article className="panel report-card" key={report.id}><div className="report-card-icon"><FileText size={19} /></div><div><div className="case-card-top"><span className="case-number">v{report.version}</span><span className="status-chip status-positive">STORED</span></div><h3>{report.title}</h3><p>{report.summary || "Structured report generated from the current evidence and graph context."}</p><span className="report-meta">{formatDateTime(report.created_at)} · {report.id}</span></div><button className="table-action" type="button" onClick={() => void onDownload(report.id)}><FilePdf size={13} /> Export</button></article>) : <div className="panel empty-state"><FileText size={26} /><strong>No reports yet</strong><span>Generate a report from the current stored records.</span></div>}</div></section></>;
}

function UserAccessView({ users, onCreated, onError, busy, setBusy }: { users: User[]; onCreated: (item: User) => Promise<void>; onError: (kind: "error" | "success", message: string) => void; busy: boolean; setBusy: (value: boolean) => void }) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ username: "", display_name: "", password: "", role: "ANALYST" as Role });
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); setError(""); setBusy(true); try { const item = await createUser(form); await onCreated(item); setForm({ username: "", display_name: "", password: "", role: "ANALYST" }); setShowForm(false); } catch (reason) { const message = reason instanceof Error ? reason.message : "User could not be created."; setError(message); onError("error", message); } finally { setBusy(false); } };
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Identity governance</p><h2>User access</h2><p className="toolbar-description">Create role-scoped operators. Every access change is recorded in the audit trail.</p></div><button className="primary-button" type="button" onClick={() => setShowForm((value) => !value)}><UserPlus size={16} /> Add operator</button></section>{showForm && <form className="panel inline-form user-form" onSubmit={submit}><div><p className="section-kicker">New identity</p><h3>Create access profile</h3></div><label className="field-label">Username<input className="text-input" value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} required /></label><label className="field-label">Display name<input className="text-input" value={form.display_name} onChange={(event) => setForm({ ...form, display_name: event.target.value })} required /></label><label className="field-label">Temporary passphrase<input className="text-input" type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} minLength={12} required /></label><label className="field-label">Role<select className="text-input" value={form.role} onChange={(event) => setForm({ ...form, role: event.target.value as Role })}><option value="ANALYST">Analyst</option><option value="AUDITOR">Supervisor</option><option value="ADMIN">Administrator</option></select></label><button className="primary-button compact" type="submit" disabled={busy}>Create operator</button>{error && <div className="form-error"><WarningCircle size={15} />{error}</div>}</form>}<section className="panel table-panel"><div className="panel-heading"><div><p className="section-kicker">Operator directory</p><h3>Role assignments</h3></div><span className="table-count">{users.length} accounts</span></div><div className="data-table"><div className="table-row table-head"><span>Operator</span><span>Role</span><span>State</span><span>Last login</span></div>{users.map((item) => <div className="table-row" key={item.id}><div className="table-source"><div className="avatar">{initials(item.display_name)}</div><div><strong>{item.display_name}</strong><span>{item.username} · {item.id}</span></div></div><span>{roleLabel(item.role)}</span><span className={`status-chip ${item.is_active ? "status-positive" : "status-danger"}`}>{item.is_active ? "ACTIVE" : "DISABLED"}</span><span>{formatDateTime(item.last_login_at)}</span></div>)}</div></section></>;
}

function AuditView({ events, onRefresh }: { events: AuditEvent[]; onRefresh: () => Promise<void> }) {
  return <><section className="workspace-toolbar"><div><p className="section-kicker">Append-only oversight</p><h2>Audit trail</h2><p className="toolbar-description">Review who changed or investigated which record, and why the action was recorded.</p></div><button className="secondary-button" type="button" onClick={() => void onRefresh()}><Pulse size={16} /> Refresh events</button></section><section className="panel table-panel"><div className="panel-heading"><div><p className="section-kicker">Event ledger</p><h3>Recent activity</h3></div><span className="table-count">{events.length} events</span></div>{events.length ? <div className="data-table audit-table"><div className="table-row table-head"><span>Action</span><span>Resource</span><span>Actor</span><span>Recorded</span></div>{events.map((event) => <div className="table-row" key={event.id}><div><span className="action-label">{event.action.replaceAll("_", " ")}</span><small>{event.id}</small></div><span>{event.resource_type ?? "System"}{event.resource_id ? ` · ${event.resource_id}` : ""}</span><span>{event.user_id ? event.user_id.slice(0, 12) : "System"}</span><span>{formatDateTime(event.created_at)}</span></div>)}</div> : <div className="empty-state"><Pulse size={26} /><strong>No audit events</strong><span>Mutations and investigation actions will appear here.</span></div>}</section></>;
}

export default App;
