import type {
  AnalysisResponse,
  AssistantResponse,
  AuditEvent,
  CaseRecord,
  Candidate,
  Camera,
  CameraObservation,
  CameraStatus,
  CaseNote,
  DuplicateMatch,
  Entity,
  Evidence,
  GraphResponse,
  HealthPayload,
  MapResponse,
  Relationship,
  ReportRecord,
  SavedGraphView,
  SavedSearch,
  SearchResponseData,
  SignalResponse,
  TokenResponse,
  TimelineResponse,
  User,
  UserCreate,
} from "./types";

const apiBase = (import.meta.env.VITE_API_URL as string | undefined) ?? "/api/v1";

export function apiUrl(path: string): string {
  return `${apiBase}${path}`;
}
const tokenKey = "signal-atlas-token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getStoredToken(): string | null {
  return window.localStorage.getItem(tokenKey);
}

export function storeToken(token: string): void {
  window.localStorage.setItem(tokenKey, token);
}

export function clearStoredToken(): void {
  window.localStorage.removeItem(tokenKey);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const response = await fetch(`${apiBase}${path}`, { ...init, headers });
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload ? String(payload.detail) : `Request failed with ${response.status}`;
    if (response.status === 401) clearStoredToken();
    throw new ApiError(detail, response.status);
  }
  return payload as T;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  });
  const result = search.toString();
  return result ? `?${result}` : "";
}

export function searchWorkspace(params: { q: string; case_id?: string; entity_type?: string; status?: string; evidence_category?: string; relationship_type?: string }): Promise<SearchResponseData> {
  return request<SearchResponseData>(`/search${query(params)}`);
}

export function getHealth(): Promise<HealthPayload> {
  return request<HealthPayload>("/health");
}

export function login(username: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<User> {
  return request<User>("/auth/me");
}

export function getUsers(): Promise<User[]> {
  return request<User[]>("/auth/users");
}

export function createUser(payload: UserCreate): Promise<User> {
  return request<User>("/auth/users", { method: "POST", body: JSON.stringify(payload) });
}

export function getEntities(params: { q?: string; entity_type?: string; status?: string; limit?: number } = {}): Promise<Entity[]> {
  return request<Entity[]>(`/entities${query(params)}`);
}

export function createEntity(payload: {
  name: string;
  entity_type: string;
  aliases?: string[];
  status?: string;
  notes?: string;
  case_id?: string | null;
}): Promise<Entity> {
  return request<Entity>("/entities", { method: "POST", body: JSON.stringify(payload) });
}

export function updateEntity(entityId: string, payload: { name?: string; status?: string; notes?: string; aliases?: string[] }): Promise<Entity> {
  return request<Entity>(`/entities/${entityId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function getDuplicateCandidates(entityId: string): Promise<DuplicateMatch[]> {
  return request<DuplicateMatch[]>(`/entities/${entityId}/duplicates`);
}

export function mergeEntities(sourceId: string, targetId: string, reason: string): Promise<{ entity: Entity; archived_entity_id: string }> {
  return request(`/entities/${sourceId}/merge`, { method: "POST", body: JSON.stringify({ target_entity_id: targetId, reason, confirm: true }) });
}

export function archiveEntity(entityId: string): Promise<void> {
  return request<void>(`/entities/${entityId}`, { method: "DELETE" });
}

export function getGeo(params: { case_id?: string; start_date?: string; end_date?: string } = {}): Promise<MapResponse> {
  return request<MapResponse>(`/analytics/geo${query(params)}`);
}

export function getTimeline(params: { case_id?: string; start_date?: string; end_date?: string } = {}): Promise<TimelineResponse> {
  return request<TimelineResponse>(`/analytics/timeline${query(params)}`);
}

export function runSignals(params: { case_id?: string; threshold_multiplier?: number } = {}): Promise<SignalResponse> {
  return request<SignalResponse>(`/analytics/signals${query(params)}`, { method: "POST" });
}

export function getCameras(params: { location?: string; status?: string } = {}): Promise<Camera[]> {
  return request<Camera[]>(`/cameras${query(params)}`);
}

export function createCamera(payload: {
  camera_name: string;
  source_type: string;
  source_uri: string;
  location_name?: string;
  timezone?: string;
  description?: string;
  enabled?: boolean;
  metadata?: Record<string, unknown>;
}): Promise<Camera> {
  return request<Camera>("/cameras", { method: "POST", body: JSON.stringify(payload) });
}

export function updateCamera(cameraId: string, payload: Partial<{
  camera_name: string;
  source_type: string;
  source_uri: string;
  location_name: string;
  timezone: string;
  description: string;
  enabled: boolean;
  metadata: Record<string, unknown>;
}>): Promise<Camera> {
  return request<Camera>(`/cameras/${cameraId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export function archiveCamera(cameraId: string): Promise<void> {
  return request<void>(`/cameras/${cameraId}`, { method: "DELETE" });
}

export function startCamera(cameraId: string): Promise<CameraStatus> {
  return request<CameraStatus>(`/cameras/${cameraId}/start`, { method: "POST" });
}

export function stopCamera(cameraId: string): Promise<CameraStatus> {
  return request<CameraStatus>(`/cameras/${cameraId}/stop`, { method: "POST" });
}

export function getCameraStatus(cameraId: string): Promise<CameraStatus> {
  return request<CameraStatus>(`/cameras/${cameraId}/status`);
}

export function getCameraObservations(params: { camera_id?: string; status?: string; case_id?: string; limit?: number } = {}): Promise<CameraObservation[]> {
  return request<CameraObservation[]>(`/cameras/observations/all${query(params)}`);
}

export function reviewObservation(observationId: string, payload: { decision: "VERIFY" | "REJECT" | "ASSOCIATE"; associated_person_id?: string; notes?: string }): Promise<CameraObservation> {
  return request<CameraObservation>(`/cameras/observations/${observationId}/review`, { method: "POST", body: JSON.stringify(payload) });
}

export function latestFrameUrl(cameraId: string, token: string, annotated = true): string {
  return apiUrl(`/cameras/${cameraId}/latest-frame?token=${encodeURIComponent(token)}&annotated=${annotated ? "1" : "0"}&t=${Date.now()}`);
}

export function observationFrameUrl(observationId: string, token: string): string {
  return apiUrl(`/cameras/observations/${observationId}/annotated-frame?token=${encodeURIComponent(token)}&t=${Date.now()}`);
}

export function getReferencePhotos(entityId: string): Promise<Array<{ id: string; entity_id: string; evidence_id: string; label: string; notes: string; created_at: string }>> {
  return request(`/cameras/entities/${entityId}/reference-photos`);
}

export function uploadReferencePhoto(entityId: string, file: File, label: string, notes: string): Promise<{ id: string; entity_id: string; evidence_id: string; label: string; notes: string; created_at: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("label", label);
  form.append("notes", notes);
  return request(`/cameras/entities/${entityId}/reference-photo`, { method: "POST", body: form });
}

export function referencePhotoUrl(entityId: string, photoId: string, token: string): string {
  return apiUrl(`/cameras/entities/${entityId}/reference-photos/${photoId}/image?token=${encodeURIComponent(token)}&t=${Date.now()}`);
}

export function getCandidates(params: { evidence_id?: string; status?: string; candidate_type?: string } = {}): Promise<Candidate[]> {
  return request<Candidate[]>(`/extractions/candidates${query(params)}`);
}

export function extractEvidence(evidenceId: string): Promise<Candidate[]> {
  return request<Candidate[]>(`/evidence/${evidenceId}/extract`, { method: "POST" });
}

export function approveCandidate(candidateId: string): Promise<{ candidate: Candidate; entity_id?: string; relationship_id?: string }> {
  return request(`/extractions/candidates/${candidateId}/approve`, { method: "POST" });
}

export function rejectCandidate(candidateId: string): Promise<void> {
  return request<void>(`/extractions/candidates/${candidateId}/reject`, { method: "POST" });
}

export function getGraph(params: { center_id?: string; depth?: number; relationship_types?: string; entity_types?: string; case_id?: string; start_date?: string; end_date?: string } = {}): Promise<GraphResponse> {
  return request<GraphResponse>(`/graph${query(params)}`);
}

export function getRelationships(params: { case_id?: string; source_id?: string; target_id?: string; relationship_type?: string } = {}): Promise<Relationship[]> {
  return request<Relationship[]>(`/relationships${query(params)}`);
}

export function createRelationship(payload: {
  source_id: string;
  target_id: string;
  relationship_type: string;
  timestamp?: string;
  evidence_id?: string | null;
  case_id?: string | null;
  confidence?: number;
  notes?: string;
}): Promise<Relationship> {
  return request<Relationship>("/relationships", { method: "POST", body: JSON.stringify(payload) });
}

export function getCaseNotes(caseId: string): Promise<CaseNote[]> {
  return request<CaseNote[]>(`/cases/${caseId}/notes`);
}

export function addCaseNote(caseId: string, body: string): Promise<CaseNote> {
  return request<CaseNote>(`/cases/${caseId}/notes`, { method: "POST", body: JSON.stringify({ body }) });
}

export function getSavedSearches(): Promise<SavedSearch[]> {
  return request<SavedSearch[]>("/cases/saved-searches");
}

export function getSavedViews(): Promise<SavedGraphView[]> {
  return request<SavedGraphView[]>("/cases/saved-views");
}

export function getCases(): Promise<CaseRecord[]> {
  return request<CaseRecord[]>("/cases");
}

export function createCase(payload: { case_number: string; title: string; description?: string; priority?: string }): Promise<CaseRecord> {
  return request<CaseRecord>("/cases", { method: "POST", body: JSON.stringify(payload) });
}

export function getEvidence(params: { case_id?: string; category?: string } = {}): Promise<Evidence[]> {
  return request<Evidence[]>(`/evidence${query(params)}`);
}

export function uploadEvidence(formData: FormData): Promise<Evidence> {
  return request<Evidence>("/evidence", { method: "POST", body: formData });
}

export function runAnalysis(params: { case_id?: string; algorithm?: string; center_id?: string } = {}): Promise<AnalysisResponse> {
  return request<AnalysisResponse>(`/analytics/network${query(params)}`, { method: "POST" });
}

export function getAuditEvents(): Promise<AuditEvent[]> {
  return request<AuditEvent[]>("/audit");
}

export function askAssistant(question: string, caseId?: string): Promise<AssistantResponse> {
  return request<AssistantResponse>("/assistant/query", { method: "POST", body: JSON.stringify({ question, case_id: caseId ?? null }) });
}

export async function downloadReport(reportId: string, format: "html" | "md" = "md"): Promise<void> {
  const headers = new Headers({ Accept: "text/plain" });
  const token = getStoredToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${apiBase}/reports/${reportId}/export?format=${format}`, { headers });
  if (!response.ok) throw new ApiError("Report export failed", response.status);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${reportId}.${format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function synthesizeReport(caseId: string, title = "Multi-agent intelligence synthesis"): Promise<ReportRecord> {
  return request<ReportRecord>("/reports/synthesize", { method: "POST", body: JSON.stringify({ case_id: caseId, title }) });
}

export function getReports(caseId?: string): Promise<ReportRecord[]> {
  return request<ReportRecord[]>(`/reports${query({ case_id: caseId })}`);
}

export function createReport(payload: { case_id?: string | null; title: string; summary?: string }): Promise<ReportRecord> {
  return request<ReportRecord>("/reports", { method: "POST", body: JSON.stringify(payload) });
}
