import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  Archive,
  ArrowRight,
  ArrowsOut,
  Camera as CameraIcon,
  CheckCircle,
  CircleNotch,
  Clock,
  Database,
  Eye,
  FileText,
  Image as ImageIcon,
  LockKey,
  MagnifyingGlass,
  MapPin,
  Monitor,
  Pause,
  PencilSimple,
  Play,
  Plus,
  Radio,
  Scan,
  ShieldCheck,
  Stop,
  UserCircle,
  UserPlus,
  WarningCircle,
  WifiHigh,
  WifiSlash,
  X,
} from "@phosphor-icons/react";

import {
  apiUrl,
  archiveCamera,
  createCamera,
  getCameraObservations,
  getCameras,
  getCameraStatus,
  getStoredToken,
  latestFrameUrl,
  observationFrameUrl,
  reviewObservation,
  searchWorkspace,
  startCamera,
  stopCamera,
  updateCamera,
} from "../api";
import type { Camera, CameraObservation, CameraStatus, Entity, SearchResult } from "../types";

type CameraPage = "cameras" | "monitoring" | "review" | "event";
type Role = "ADMIN" | "ANALYST" | "AUDITOR";

type CameraModuleProps = {
  page: CameraPage;
  userRole: Role;
  onNavigate: (page: CameraPage) => void;
  initialEventId?: string | null;
};

type CameraForm = {
  camera_name: string;
  source_type: string;
  source_uri: string;
  location_name: string;
  timezone: string;
  description: string;
};

const emptyForm: CameraForm = {
  camera_name: "",
  source_type: "WEBCAM",
  source_uri: "0",
  location_name: "",
  timezone: "Asia/Kolkata",
  description: "",
};

function formatDateTime(value: string | null | undefined) {
  if (!value) return "No frame recorded";
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date(value));
}

function statusTone(status: string) {
  const normalized = status.toUpperCase();
  if (normalized === "LIVE" || normalized === "ACTIVE") return "status-positive";
  if (normalized === "OFFLINE" || normalized === "ERROR" || normalized === "ARCHIVED") return "status-danger";
  if (normalized === "STARTING" || normalized === "PENDING_REVIEW") return "status-warning";
  return "status-neutral";
}

function sourceLabel(sourceType: string) {
  return sourceType === "VIDEO_FILE" ? "Video file" : sourceType === "WEBCAM" ? "Webcam" : sourceType === "RTSP" ? "RTSP stream" : "HTTP stream";
}

export default function CameraModule({ page, userRole, onNavigate, initialEventId }: CameraModuleProps) {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [statuses, setStatuses] = useState<Record<string, CameraStatus>>({});
  const [observations, setObservations] = useState<CameraObservation[]>([]);
  const [selectedObservationId, setSelectedObservationId] = useState<string | null>(initialEventId ?? null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [frameTick, setFrameTick] = useState(0);
  const [monitorFilter, setMonitorFilter] = useState("ALL");
  const [locationFilter, setLocationFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<CameraForm>(emptyForm);
  const [personQuery, setPersonQuery] = useState("");
  const [personResults, setPersonResults] = useState<SearchResult[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState("");
  const token = getStoredToken() ?? "";
  const canManage = userRole === "ADMIN";
  const canReview = userRole === "ADMIN" || userRole === "ANALYST";

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [cameraResult, observationResult] = await Promise.all([getCameras(), getCameraObservations({ limit: 200 })]);
      setCameras(cameraResult);
      setObservations(observationResult);
      const statusEntries = await Promise.all(cameraResult.map(async (camera) => [camera.id, await getCameraStatus(camera.id)] as const));
      setStatuses(Object.fromEntries(statusEntries));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Camera data could not be loaded.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setFrameTick((value) => value + 1), 1500);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!token) return;
    const configured = apiUrl("/cameras/ws");
    const wsUrl = configured.startsWith("http")
      ? configured.replace(/^http/, "ws")
      : `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}${configured}`;
    const socket = new WebSocket(`${wsUrl}?token=${encodeURIComponent(token)}`);
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as { event?: string; camera_id?: string; payload?: Record<string, unknown> };
        if (message.camera_id && message.payload) {
          setStatuses((current) => ({
            ...current,
            [message.camera_id as string]: { ...(current[message.camera_id as string] ?? { camera_id: message.camera_id as string, source_type: "", detection_count: 0, active_detections: 0, last_error: "", demo_mode: false }), ...message.payload } as CameraStatus,
          }));
        }
        if (message.event === "REVIEW_REQUIRED") {
          setNotice("A new visual observation is waiting for human review.");
          void load();
        }
      } catch {
        // Ignore malformed optional event frames.
      }
    };
    socket.onerror = () => setNotice("Live event channel unavailable; polling continues.");
    return () => socket.close();
  }, [token]);

  useEffect(() => {
    if (initialEventId) setSelectedObservationId(initialEventId);
  }, [initialEventId]);

  const selectedObservation = observations.find((observation) => observation.id === selectedObservationId) ?? null;
  const demoMode = Object.values(statuses).some((status) => status.demo_mode);
  const visibleCameras = useMemo(() => cameras.filter((camera) => {
    const status = statuses[camera.id]?.status ?? camera.status;
    const statusMatch = monitorFilter === "ALL" || status === monitorFilter;
    const locationMatch = !locationFilter || camera.location_name.toLowerCase().includes(locationFilter.toLowerCase());
    return statusMatch && locationMatch;
  }), [cameras, statuses, monitorFilter, locationFilter]);

  const showMessage = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 4500);
  };

  const runAction = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true);
    setError("");
    try {
      await action();
      showMessage(message);
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Camera action failed.");
    } finally {
      setBusy(false);
    }
  };

  const submitCamera = async (event: FormEvent) => {
    event.preventDefault();
    await runAction(async () => {
      if (editingId) await updateCamera(editingId, form);
      else await createCamera(form);
      setForm(emptyForm);
      setEditingId(null);
      setShowForm(false);
    }, editingId ? "Camera configuration updated." : "Camera source created.");
  };

  const editCamera = (camera: Camera) => {
    setEditingId(camera.id);
    setForm({ camera_name: camera.camera_name, source_type: camera.source_type, source_uri: camera.source_uri_masked, location_name: camera.location_name, timezone: camera.timezone, description: camera.description });
    setShowForm(true);
  };

  const searchPeople = async (event: FormEvent) => {
    event.preventDefault();
    if (!personQuery.trim()) return;
    try {
      const result = await searchWorkspace({ q: personQuery.trim() });
      setPersonResults(result.results.filter((item) => item.result_type === "ENTITY" && item.entity_type === "PERSON"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Person search failed.");
    }
  };

  const review = async (decision: "VERIFY" | "REJECT" | "ASSOCIATE") => {
    if (!selectedObservation) return;
    await runAction(async () => {
      const updated = await reviewObservation(selectedObservation.id, { decision, associated_person_id: decision === "ASSOCIATE" ? selectedPersonId : undefined, notes: decision === "ASSOCIATE" ? "Manually associated by an authorized human reviewer." : "" });
      setObservations((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSelectedPersonId("");
    }, decision === "ASSOCIATE" ? "Human association recorded. No biometric identification was performed." : `Observation ${decision.toLowerCase()}d by human reviewer.`);
  };

  const cameraStatus = (camera: Camera) => statuses[camera.id] ?? { camera_id: camera.id, status: camera.status, source_type: camera.source_type, last_frame_at: camera.last_frame_at, last_detection_at: camera.last_detection_at, detection_count: camera.detection_count, active_detections: 0, last_error: camera.last_error, demo_mode: false };

  const cameraFrame = (camera: Camera) => latestFrameUrl(camera.id, token) + `&tick=${frameTick}`;

  return (
    <div className="camera-module">
      {demoMode && <div className="demo-simulation-banner"><ShieldCheck size={18} /><div><strong>DEMO SIMULATION MODE</strong><span>Simulated events are prerecorded/timestamped. This is not biometric identification. A human reviewer must approve every association.</span></div></div>}
      {error && <div className="camera-alert error"><WarningCircle size={17} />{error}<button type="button" onClick={() => setError("")}><X size={14} /></button></div>}
      {notice && <div className="camera-alert"><Radio size={17} />{notice}<button type="button" onClick={() => setNotice("")}><X size={14} /></button></div>}
      {loading && <div className="camera-loading"><CircleNotch className="spin" size={16} /> Syncing camera sources and observations</div>}

      {page === "cameras" && <CameraSources cameras={cameras} statuses={statuses} canManage={canManage} busy={busy} showForm={showForm} editingId={editingId} form={form} setForm={setForm} onToggleForm={() => { setShowForm((value) => !value); setEditingId(null); setForm(emptyForm); }} onSubmit={submitCamera} onEdit={editCamera} onStart={(camera) => void runAction(() => startCamera(camera.id), `${camera.camera_name} started.`)} onStop={(camera) => void runAction(() => stopCamera(camera.id), `${camera.camera_name} stopped.`)} onArchive={(camera) => void runAction(() => archiveCamera(camera.id), `${camera.camera_name} archived.`)} onNavigate={onNavigate} />}
      {page === "monitoring" && <Monitoring cameras={visibleCameras} statuses={statuses} frameTick={frameTick} filter={monitorFilter} setFilter={setMonitorFilter} location={locationFilter} setLocation={setLocationFilter} canManage={canManage} busy={busy} frameUrl={cameraFrame} onStart={(camera) => void runAction(() => startCamera(camera.id), `${camera.camera_name} started.`)} onStop={(camera) => void runAction(() => stopCamera(camera.id), `${camera.camera_name} stopped.`)} onReview={() => onNavigate("review")} />}
      {(page === "review" || page === "event") && <ReviewQueue observations={observations} selected={selectedObservation} token={token} canReview={canReview} busy={busy} personQuery={personQuery} setPersonQuery={setPersonQuery} personResults={personResults} selectedPersonId={selectedPersonId} setSelectedPersonId={setSelectedPersonId} onSearchPeople={searchPeople} onSelectObservation={setSelectedObservationId} onReview={review} frameUrl={observationFrameUrl} />}

      <div className="camera-nav-footer"><button type="button" onClick={() => onNavigate("cameras")}><CameraIcon size={15} /> Camera sources</button><button type="button" onClick={() => onNavigate("monitoring")}><Monitor size={15} /> Live monitoring</button><button type="button" onClick={() => onNavigate("review")}><Eye size={15} /> Detection review</button></div>
    </div>
  );
}

function CameraSources({ cameras, statuses, canManage, busy, showForm, editingId, form, setForm, onToggleForm, onSubmit, onEdit, onStart, onStop, onArchive, onNavigate }: { cameras: Camera[]; statuses: Record<string, CameraStatus>; canManage: boolean; busy: boolean; showForm: boolean; editingId: string | null; form: CameraForm; setForm: (value: CameraForm) => void; onToggleForm: () => void; onSubmit: (event: FormEvent) => Promise<void>; onEdit: (camera: Camera) => void; onStart: (camera: Camera) => void; onStop: (camera: Camera) => void; onArchive: (camera: Camera) => void; onNavigate: (page: CameraPage) => void }) {
  return <>
    <section className="camera-page-header"><div><p className="section-kicker">Admin configuration</p><h2>Camera sources</h2><p>Configure independent sources without coupling the prototype to physical CCTV infrastructure.</p></div>{canManage && <button className="primary-button" type="button" onClick={onToggleForm}><Plus size={16} /> {editingId ? "Cancel edit" : "Add camera"}</button>}</section>
    {demoNotice()}
    {showForm && canManage && <form className="panel camera-form" onSubmit={onSubmit}><div className="panel-heading"><div><p className="section-kicker">{editingId ? "Edit source" : "New source"}</p><h3>{editingId ? "Update camera configuration" : "Add a camera source"}</h3></div><CameraIcon size={21} className="accent-icon" /></div><div className="camera-form-grid"><label className="field-label">Camera name<input className="text-input" value={form.camera_name} onChange={(event) => setForm({ ...form, camera_name: event.target.value })} required /></label><label className="field-label">Source type<select className="text-input" value={form.source_type} onChange={(event) => setForm({ ...form, source_type: event.target.value })}><option value="WEBCAM">Webcam</option><option value="VIDEO_FILE">Local video file</option><option value="HTTP_STREAM">HTTP/MJPEG stream</option><option value="RTSP">RTSP stream</option></select></label><label className="field-label">Source URI / index<input className="text-input" value={form.source_uri} onChange={(event) => setForm({ ...form, source_uri: event.target.value })} placeholder="0 or datasets/demo.mp4" required /></label><label className="field-label">Location name<input className="text-input" value={form.location_name} onChange={(event) => setForm({ ...form, location_name: event.target.value })} placeholder="Main Gate" /></label><label className="field-label">Timezone<input className="text-input" value={form.timezone} onChange={(event) => setForm({ ...form, timezone: event.target.value })} /></label><label className="field-label wide">Description<textarea className="text-input" rows={2} value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} /></label></div><div className="form-policy-note"><LockKey size={15} /><span>Source configuration is Admin-only. Detection never performs identity matching.</span></div><button className="primary-button compact" type="submit" disabled={busy}>{busy ? <CircleNotch className="spin" size={15} /> : <CheckCircle size={15} />} {editingId ? "Save changes" : "Create camera"}</button></form>}
    <section className="panel camera-table-panel"><div className="panel-heading"><div><p className="section-kicker">Source registry</p><h3>Configured cameras</h3></div><span className="table-count">{cameras.length} sources</span></div>{cameras.length ? <div className="data-table camera-table"><div className="table-row table-head"><span>Camera</span><span>Location</span><span>Status</span><span>Last frame</span><span>Detections</span><span>Actions</span></div>{cameras.map((camera) => { const status = statuses[camera.id]; return <div className="table-row" key={camera.id}><div className="camera-name-cell"><div className="camera-avatar"><CameraIcon size={17} /></div><div><strong>{camera.camera_name}</strong><span>{sourceLabel(camera.source_type)} · {camera.source_uri_masked}</span></div></div><span><MapPin size={13} /> {camera.location_name || "Unassigned"}</span><span className={`status-chip ${statusTone(status?.status ?? camera.status)}`}>{status?.status ?? camera.status}</span><span className="camera-frame-time"><Clock size={12} /> {formatDateTime(status?.last_frame_at)}</span><span>{status?.active_detections ?? 0} active / {status?.detection_count ?? camera.detection_count} total</span><div className="camera-actions">{canManage && <>{status?.status === "LIVE" ? <button type="button" onClick={() => onStop(camera)} title="Stop"><Pause size={14} /></button> : <button type="button" onClick={() => onStart(camera)} title="Start"><Play size={14} /></button>}<button type="button" onClick={() => onEdit(camera)} title="Edit"><PencilSimple size={14} /></button><button type="button" onClick={() => onArchive(camera)} title="Archive"><Archive size={14} /></button></>}<button type="button" onClick={() => onNavigate("monitoring")} title="Monitor"><Monitor size={14} /></button></div></div>; })}</div> : <div className="empty-state"><CameraIcon size={26} /><strong>No camera sources configured</strong><span>Add a webcam or local video file to begin detection monitoring.</span></div>}</section>
  </>;
}

function Monitoring({ cameras, statuses, frameTick, filter, setFilter, location, setLocation, canManage, busy, frameUrl, onStart, onStop, onReview }: { cameras: Camera[]; statuses: Record<string, CameraStatus>; frameTick: number; filter: string; setFilter: (value: string) => void; location: string; setLocation: (value: string) => void; canManage: boolean; busy: boolean; frameUrl: (camera: Camera) => string; onStart: (camera: Camera) => void; onStop: (camera: Camera) => void; onReview: () => void }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  return <>
    <section className="camera-page-header"><div><p className="section-kicker">Live observation surface</p><h2>Live monitoring</h2><p>Multiple sources run independently. Boxes indicate detected faces only, never identities.</p></div><div className="monitor-filters"><select className="text-input" value={filter} onChange={(event) => setFilter(event.target.value)}><option value="ALL">All statuses</option><option value="LIVE">Live</option><option value="OFFLINE">Offline</option><option value="STOPPED">Stopped</option></select><input className="text-input" placeholder="Filter location" value={location} onChange={(event) => setLocation(event.target.value)} /></div></section>
    {demoNotice()}
    {cameras.length ? <div className="monitor-grid">{cameras.map((camera) => { const status = statuses[camera.id]; const live = (status?.status ?? camera.status) === "LIVE"; const expanded = expandedId === camera.id; return <article className={`monitor-card panel ${expanded ? "is-expanded" : ""}`} key={camera.id}><div className="monitor-card-head"><div><strong>{camera.camera_name}</strong><span><MapPin size={12} /> {camera.location_name || "Unassigned location"}</span></div><div className="monitor-head-right"><span className={`status-chip ${statusTone(status?.status ?? camera.status)}`}>{live ? <WifiHigh size={12} /> : <WifiSlash size={12} />} {status?.status ?? camera.status}</span>{expanded && <button type="button" className="monitor-expand-close" onClick={() => setExpandedId(null)} aria-label="Close enlarged feed"><X size={15} /></button>}</div></div><div className={`monitor-frame ${live ? "monitor-frame-clickable" : ""}`} onClick={() => live && setExpandedId(expanded ? null : camera.id)}>{live ? <img src={frameUrl(camera)} alt={`${camera.camera_name} annotated live frame`} onError={(event) => { event.currentTarget.style.display = "none"; }} /> : <div className="monitor-offline"><WifiSlash size={24} /><span>{status?.last_error || "Stream is stopped or offline"}</span></div>}<span className="frame-time">{formatDateTime(status?.last_frame_at)}</span><span className="frame-label">Detection only · no identity labels</span></div><div className="monitor-card-foot"><span><Scan size={14} /> {status?.active_detections ?? 0} active face box(es)</span><span>{status?.detection_count ?? 0} total observations</span>{live && <span className="monitor-expand-hint"><ArrowsOut size={12} /> Click the frame to enlarge</span>}{canManage && <button className="secondary-button compact" type="button" disabled={busy} onClick={() => live ? onStop(camera) : onStart(camera)}>{live ? <><Pause size={13} /> Stop</> : <><Play size={13} /> Start</>}</button>}</div><button className="monitor-review-link" type="button" onClick={onReview}>Open detection review <ArrowRight size={14} /></button></article>; })}</div> : <div className="panel empty-state monitor-empty"><Monitor size={28} /><strong>No active camera sources</strong><span>Configure a camera source first, then return here to monitor frames.</span></div>}
  </>;
}

function ReviewQueue({ observations, selected, token, canReview, busy, personQuery, setPersonQuery, personResults, selectedPersonId, setSelectedPersonId, onSearchPeople, onSelectObservation, onReview, frameUrl }: { observations: CameraObservation[]; selected: CameraObservation | null; token: string; canReview: boolean; busy: boolean; personQuery: string; setPersonQuery: (value: string) => void; personResults: SearchResult[]; selectedPersonId: string; setSelectedPersonId: (value: string) => void; onSearchPeople: (event: FormEvent) => void; onSelectObservation: (id: string) => void; onReview: (decision: "VERIFY" | "REJECT" | "ASSOCIATE") => Promise<void>; frameUrl: (id: string, token: string) => string }) {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const filters = [["ALL", "All evidence"], ["PENDING_REVIEW", "Pending"], ["VERIFIED_OBSERVATION", "Verified"], ["ASSOCIATED_WITH_ENTITY", "Associated"], ["REJECTED", "Rejected"]] as const;
  const visible = statusFilter === "ALL" ? observations : observations.filter((item) => item.review_status === statusFilter);
  return <>
    <section className="camera-page-header"><div><p className="section-kicker">Human verification queue</p><h2>Detection review</h2><p>Review annotated frames, then explicitly verify, reject, or associate an observation.</p></div><div className="review-count"><strong>{observations.filter((item) => item.review_status === "PENDING_REVIEW").length}</strong><span>pending review</span></div></section>
    {demoNotice()}
    <div className="review-layout"><section className="panel observation-list"><div className="panel-heading"><div><p className="section-kicker">Observations</p><h3>Visual event ledger</h3></div><span className="table-count">{visible.length} events</span></div><div className="review-filters">{filters.map(([value, label]) => <button type="button" key={value} className={statusFilter === value ? "active" : ""} onClick={() => setStatusFilter(value)}>{label}</button>)}</div>{visible.length ? visible.map((observation) => <button type="button" className={`observation-row ${selected?.id === observation.id ? "selected" : ""}`} key={observation.id} onClick={() => onSelectObservation(observation.id)}><div className="observation-thumb"><ImageIcon size={16} /></div><div><strong>{observation.camera_name || observation.camera_id}</strong><span>{formatDateTime(observation.timestamp)} · {observation.location_name || "Unassigned"}</span><small>{observation.is_simulated ? "SIMULATED" : observation.review_status}</small></div><ArrowRight size={15} /></button>) : <div className="empty-state"><Eye size={25} /><strong>No observations</strong><span>Detected faces will appear here as evidence-backed events.</span></div>}</section><section className="panel observation-detail">{selected ? <><div className="observation-detail-head"><div><p className="section-kicker">Observation {selected.id}</p><h3>{selected.camera_name || selected.camera_id}</h3></div><span className={`status-chip ${statusTone(selected.review_status)}`}>{selected.review_status}</span></div>{selected.is_simulated && <div className="demo-event-banner"><WarningCircle size={17} /><div><strong>DEMO SIMULATION — NOT BIOMETRIC IDENTIFICATION</strong><span>{selected.simulation_label || "Simulated event"}. A human reviewer must approve any association.</span></div></div>}<div className="observation-image"><img src={frameUrl(selected.id, token)} alt="Annotated camera observation evidence" /><span>Bounding box annotation · detection only</span></div><div className="observation-meta"><div><span>Camera</span><strong>{selected.camera_name || selected.camera_id}</strong></div><div><span>Location</span><strong>{selected.location_name || "Unassigned"}</strong></div><div><span>Timestamp</span><strong>{formatDateTime(selected.timestamp)}</strong></div><div><span>Detection confidence</span><strong>{selected.detection_confidence === null ? "Not scored by binary detector" : `${Math.round(selected.detection_confidence * 100)}%`}</strong></div></div>{canReview && selected.review_status === "PENDING_REVIEW" ? <div className="review-actions"><button className="primary-button" type="button" disabled={busy} onClick={() => void onReview("VERIFY")}><CheckCircle size={15} /> Verify observation</button><button className="danger-button" type="button" disabled={busy} onClick={() => void onReview("REJECT")}><X size={15} /> Mark invalid</button></div> : <div className="review-complete-note"><CheckCircle size={16} /> This observation has a recorded human review decision.{selected.reviews[0]?.associated_person_id && <span> Associated Person: {selected.reviews[0].associated_person_id}</span>}</div>}{canReview && selected.review_status === "PENDING_REVIEW" && <div className="association-box"><div className="association-heading"><UserPlus size={17} /><div><strong>Manually associate with a Person</strong><span>This is a human record decision, not automated face matching.</span></div></div><form className="person-search" onSubmit={onSearchPeople}><MagnifyingGlass size={16} /><input value={personQuery} onChange={(event) => setPersonQuery(event.target.value)} placeholder="Search existing Person entity" /><button className="secondary-button compact" type="submit">Search</button></form>{personResults.length > 0 && <div className="person-results">{personResults.map((person) => <button type="button" className={selectedPersonId === person.id ? "selected" : ""} key={person.id} onClick={() => setSelectedPersonId(person.id)}><UserCircle size={15} /><span><strong>{person.title}</strong><small>{person.id} · {person.subtitle}</small></span></button>)}</div>}<button className="primary-button compact" type="button" disabled={busy || !selectedPersonId} onClick={() => void onReview("ASSOCIATE")}><UserPlus size={14} /> Associate selected Person</button></div>}</> : <div className="empty-state observation-empty"><Eye size={27} /><strong>Select an observation</strong><span>Annotated evidence and human review controls will appear here.</span></div>}</section></div>
  </>;
}

function demoNotice() {
  return <div className="camera-policy-note"><LockKey size={15} /><span><strong>Detection only.</strong> No face embeddings, recognition, watchlists, or automatic identity matching are used. A person association requires an explicit human decision.</span></div>;
}

function cameraStatusClass(status: string) {
  return statusTone(status);
}
