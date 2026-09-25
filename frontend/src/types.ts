export type Role = "ADMIN" | "ANALYST" | "AUDITOR";

export type User = {
  id: string;
  username: string;
  display_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type UserCreate = {
  username: string;
  display_name: string;
  password: string;
  role: Role;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
};

export type HealthPayload = {
  status: "ok" | "degraded";
  service: string;
  version: string;
  environment: string;
  timestamp: string;
  database: { status: "ok" | "error"; dialect: string; detail?: string };
  neo4j: string;
  ollama: string;
};

export type Entity = {
  id: string;
  name: string;
  normalized_name: string;
  entity_type: string;
  aliases: string[];
  status: string;
  record_state: string;
  notes: string;
  metadata: Record<string, unknown>;
  case_id: string | null;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
};

export type DuplicateMatch = {
  entity_id: string;
  name: string;
  entity_type: string;
  score: number;
  signals: string[];
  recommendation: string;
};

export type Relationship = {
  id: string;
  source_id: string;
  target_id: string;
  relationship_type: string;
  timestamp: string | null;
  start_time: string | null;
  end_time: string | null;
  evidence_id: string | null;
  case_id: string | null;
  confidence: number;
  notes: string;
  record_state: string;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
};

export type CaseNote = {
  id: string;
  case_id: string;
  user_id: string | null;
  body: string;
  created_at: string;
};

export type SavedSearch = {
  id: string;
  name: string;
  owner_id: string;
  case_id: string | null;
  query: string;
  filters: Record<string, unknown>;
  created_at: string;
};

export type SavedGraphView = {
  id: string;
  name: string;
  owner_id: string;
  case_id: string | null;
  center_id: string | null;
  depth: number;
  filters: Record<string, unknown>;
  created_at: string;
};

export type CaseRecord = {
  id: string;
  case_number: string;
  title: string;
  description: string;
  status: string;
  priority: string;
  created_by_id: string | null;
  created_at: string;
  updated_at: string;
};

export type Evidence = {
  id: string;
  title: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  category: string;
  status: string;
  extracted_text: string;
  metadata: Record<string, unknown>;
  case_id: string | null;
  uploaded_by_id: string | null;
  created_at: string;
  processed_at: string | null;
};

export type Candidate = {
  id: string;
  evidence_id: string;
  candidate_type: string;
  value: string;
  normalized_value: string;
  confidence: number;
  source_span: string;
  status: string;
  entity_id: string | null;
  created_at: string;
};

export type GraphNode = {
  id: string;
  name: string;
  entity_type: string;
  status: string;
  record_state: string;
  degree: number;
  aliases: string[];
  case_id: string | null;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  relationship_type: string;
  confidence: number;
  timestamp: string | null;
  evidence_id: string | null;
  case_id: string | null;
  record_state: string;
};

export type GraphResponse = { nodes: GraphNode[]; edges: GraphEdge[]; depth: number; center_id: string | null };

export type AnalysisMetric = {
  entity_id: string;
  name: string;
  value: number;
  rank: number;
  explanation: string;
};

export type AnalysisResponse = {
  run_id: string;
  algorithm: string;
  metrics: AnalysisMetric[];
  communities: { community_id: number; entity_ids: string[]; size: number; label: string }[];
  component_count: number;
  explanation: string;
  created_at: string;
};

export type TimelinePoint = {
  date: string;
  relationship_count: number;
  disappearance_count: number;
  cumulative_relationships: number;
  entity_count: number;
  event_count: number;
};

export type TimelineResponse = {
  points: TimelinePoint[];
  start_date: string | null;
  end_date: string | null;
  explanation: string;
};

export type MapPoint = {
  entity_id: string;
  name: string;
  entity_type: string;
  latitude: number;
  longitude: number;
  address: string | null;
  relationship_count: number;
  case_id: string | null;
};

export type MapResponse = {
  points: MapPoint[];
  total_relationships: number;
  explanation: string;
};

export type SearchResult = {
  result_type: string;
  id: string;
  title: string;
  subtitle: string;
  entity_type: string | null;
  case_id: string | null;
  status: string | null;
};

export type SearchResponseData = {
  query: string;
  results: SearchResult[];
  total: number;
  explanation: string;
};

export type PatternSignal = {
  signal_type: string;
  title: string;
  severity: string;
  explanation: string;
  entity_ids: string[];
  relationship_ids: string[];
  evidence_ids: string[];
  requires_review: boolean;
};

export type SignalResponse = {
  run_id: string;
  signals: PatternSignal[];
  baseline: Record<string, unknown>;
  explanation: string;
  created_at: string;
};

export type AuditEvent = {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: Record<string, unknown>;
  created_at: string;
};

export type AssistantResponse = {
  answer: string;
  citations: Record<string, unknown>[];
  retrieved_entities: Record<string, unknown>[];
  grounded: boolean;
  disclaimer: string;
};

export type ReportRecord = {
  id: string;
  case_id: string | null;
  title: string;
  summary: string;
  content: Record<string, unknown>;
  version: number;
  created_by_id: string | null;
  created_at: string;
};
