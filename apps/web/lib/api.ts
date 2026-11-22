export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export type Synthetic = { synthetic_data?: boolean };

export type Category = { id: number; name: string; slug: string; criticality: string };
export type Manufacturer = { id: number; name: string; country?: string | null };
export type Equipment = { id: number; name: string; kind: string };

export type PartSummary = {
  id: number;
  part_number: string;
  name: string;
  description?: string | null;
  manufacturer?: Manufacturer | null;
  category?: Category | null;
  price: number;
  currency: string;
  status: string;
  criticality: string;
  is_synthetic: boolean;
};

export type Specification = {
  id: number;
  name: string;
  value: string;
  unit?: string | null;
  source_document_id?: number | null;
};

export type Compatibility = {
  id: number;
  relationship: string;
  confidence: number;
  source: string;
  source_document_id?: number | null;
  notes?: string | null;
  related_part?: PartSummary | null;
};

export type InventoryRow = {
  location: string;
  region: string;
  quantity: number;
  snapshot_date: string;
};

export type PartDetail = PartSummary & {
  specifications: Specification[];
  compatibilities: Compatibility[];
  equipment_models: Equipment[];
  inventory: InventoryRow[];
  superseded_by?: PartSummary | null;
};

export type SearchResponse = {
  total: number;
  items: PartSummary[];
  query?: string | null;
  synthetic_data: boolean;
};

export type GraphStep = {
  part_id: number;
  part_number: string;
  name: string;
  relationship: string;
  confidence: number;
};

export type RankedCandidate = {
  part_id: number;
  part_number: string;
  name: string;
  category?: string | null;
  score: number;
  relationship: string;
  confidence: number;
  source: string;
  source_document_id?: number | null;
  evidence: GraphStep[];
  warnings: string[];
};

export type CompatibilityRank = {
  source_part_id: number;
  source_part_number: string;
  candidates: RankedCandidate[];
  algorithm: string;
  graph_nodes: number;
  graph_edges: number;
  synthetic_data: boolean;
};

export type Citation = {
  document_id: number;
  document_title: string;
  page: number;
  section?: string | null;
  chunk_id: number;
  score: number;
};

export type RetrievedChunk = {
  chunk_id: number;
  document_id: number;
  document_title: string;
  doc_type: string;
  page: number;
  section?: string | null;
  text: string;
  score: number;
  vector_score: number;
  entity_score: number;
  graph_score: number;
  source: string;
};

export type AnswerResponse = {
  query: string;
  answer: string;
  citations: Citation[];
  confidence: number;
  grounded: boolean;
  insufficient_evidence: boolean;
  warnings: string[];
  chunks: RetrievedChunk[];
};

export type ForecastDriver = { feature: string; impact: number; direction: string };

export type Forecast = {
  part_id: number;
  part_number: string;
  part_name: string;
  horizon_days: number;
  expected_demand: number;
  lower_bound: number;
  upper_bound: number;
  current_stock: number;
  predicted_stock: number;
  shortage_probability: number;
  reorder_quantity: number;
  risk_level: string;
  model_name: string;
  model_version: string;
  metrics: Record<string, unknown> & { model?: Record<string, number> };
  drivers: ForecastDriver[];
  data_freshness?: string | null;
  warnings: string[];
  synthetic_data: boolean;
};

export type OverviewItem = {
  part_id: number;
  part_number: string;
  name: string;
  category?: string | null;
  criticality: string;
  expected_30d_demand: number;
  current_stock: number;
  shortage_risk: number;
  risk_level: string;
};

export type OverviewResponse = {
  method: string;
  as_of: string;
  items: OverviewItem[];
  synthetic_data: boolean;
};

export type VisionCandidate = {
  label: string;
  part_id?: number | null;
  part_number?: string | null;
  category?: string | null;
  score: number;
  rank: number;
};

export type VisionIdentify = {
  model_name: string;
  model_version: string;
  runtime: string;
  precision: string;
  image_hash: string;
  latency_ms: number;
  top_candidates: VisionCandidate[];
  confidence: number;
  low_confidence: boolean;
  review_required: boolean;
  warnings: string[];
  synthetic_data: boolean;
};

export type UploadResponse = {
  image_id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  width: number;
  height: number;
  message: string;
};

export type TraceEvent = {
  node: string;
  status: string;
  detail?: string | null;
  latency_ms?: number | null;
  at: string;
};

export type ToolRun = {
  id: number;
  tool_name: string;
  status: string;
  latency_ms?: number | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  error?: string | null;
  created_at: string;
};

export type AgentAlternative = {
  part_id: number;
  part_number: string;
  name: string;
  category?: string | null;
  score: number;
  relationship: string;
  confidence: number;
  source: string;
  evidence_path: GraphStep[];
  citations: Citation[];
  forecast?: Forecast | null;
  evidence_complete: boolean;
  warnings: string[];
};

export type AgentResponse = {
  summary: string;
  source_part?: { part_id: number; part_number: string; name: string; category?: string | null } | null;
  vision?: VisionIdentify | null;
  alternatives: AgentAlternative[];
  documentation: {
    answer?: string | null;
    citations: Citation[];
    grounded: boolean;
    insufficient_evidence: boolean;
    confidence: number;
  };
  confidence: number;
  insufficient_evidence: boolean;
  evidence_complete: boolean;
  warnings: string[];
  plan: string[];
  intent?: string | null;
  synthetic_data: boolean;
};

export type AgentRun = {
  run_id: string;
  query: string;
  status: string;
  intent?: string | null;
  response?: AgentResponse | null;
  trace: TraceEvent[];
  error?: string | null;
  latency_ms?: number | null;
  created_at: string;
  finished_at?: string | null;
};

export type AgentRunDetail = AgentRun & { tool_runs: ToolRun[] };

export type DocumentSummary = {
  id: number;
  title: string;
  doc_type: string;
  category?: string | null;
  source: string;
  approved: boolean;
  chunks: number;
  created_at: string;
};

export type ModelVersion = {
  id: number;
  name: string;
  version: string;
  task: string;
  runtime: string;
  precision: string;
  artifact_uri?: string | null;
  metrics: Record<string, unknown>;
  approved: boolean;
  created_at: string;
};

export type AuditEvent = {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type AdminStats = {
  catalog: Record<string, number>;
  graph: { nodes: Record<string, number>; edges: Record<string, number> };
  artifacts: Record<string, { present: boolean; path: string }>;
  synthetic_data: boolean;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function searchParts(params: {
  query?: string;
  category?: string;
  manufacturer?: string;
  status?: string;
  criticality?: string;
  in_stock_only?: boolean;
  limit?: number;
  offset?: number;
}) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "" && value !== false) search.set(key, String(value));
  });
  return request<SearchResponse>(`/api/v1/parts?${search.toString()}`);
}

export const getPart = (id: number | string) => request<PartDetail>(`/api/v1/parts/${id}`);
export const getCategories = () => request<Category[]>("/api/v1/categories");
export const getManufacturers = () => request<Manufacturer[]>("/api/v1/manufacturers");
export const rankCompatibilities = (partId: number, limit = 8) =>
  request<CompatibilityRank>("/api/v1/compatibility/rank", {
    method: "POST",
    body: JSON.stringify({ part_id: partId, limit }),
  });

export const askDocuments = (query: string, partId?: number, topK = 6) =>
  request<AnswerResponse>("/api/v1/retrieval/answer", {
    method: "POST",
    body: JSON.stringify({ query, part_id: partId, top_k: topK }),
  });

export const getForecast = (partId: number, horizonDays = 30) =>
  request<Forecast>(`/api/v1/forecast/parts/${partId}?horizon_days=${horizonDays}`);
export const getForecastOverview = (limit = 10) =>
  request<OverviewResponse>(`/api/v1/forecast/overview?limit=${limit}`);

export const uploadImage = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<UploadResponse>("/api/v1/vision/upload", { method: "POST", body: form });
};

export const identifyImage = async (file: File) => {
  const form = new FormData();
  form.append("file", file);
  return request<VisionIdentify>("/api/v1/vision/identify", { method: "POST", body: form });
};

export const runAgent = (payload: {
  query: string;
  part_id?: number | null;
  image_id?: string | null;
  include_forecast?: boolean;
  include_retrieval?: boolean;
  include_compatibility?: boolean;
}) =>
  request<AgentRun>("/api/v1/agent/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getRun = (runId: string) => request<AgentRunDetail>(`/api/v1/agent/runs/${runId}`);
export const listRuns = (limit = 10) => request<AgentRun[]>(`/api/v1/agent/runs?limit=${limit}`);
export const sendFeedback = (runId: string, rating: number, comment?: string) =>
  request<{ status: string }>(`/api/v1/agent/runs/${runId}/feedback`, {
    method: "POST",
    body: JSON.stringify({ rating, comment }),
  });

export const listDocuments = (category?: string) => {
  const suffix = category ? `?category=${encodeURIComponent(category)}` : "";
  return request<DocumentSummary[]>(`/api/v1/documents${suffix}`);
};
export const getDocument = (id: number) => request<Record<string, unknown>>(`/api/v1/documents/${id}`);
export const indexDocuments = () =>
  request<{ documents: number; chunks: number; vocab_size: number; artifact_path: string; latency_ms: number }>(
    "/api/v1/documents/index",
    { method: "POST", body: JSON.stringify({ rebuild: true }) },
  );

export const getModels = () => request<ModelVersion[]>("/api/v1/admin/models");
export const getAudit = (limit = 100) => request<AuditEvent[]>(`/api/v1/admin/audit?limit=${limit}`);
export const getImports = () => request<Record<string, unknown>[]>("/api/v1/admin/imports");
export const getAdminStats = () => request<AdminStats>("/api/v1/admin/stats");
export const importParts = (rows: Record<string, unknown>[]) =>
  request<{
    accepted: number;
    rejected: number;
    errors: Record<string, unknown>[];
    created_ids: number[];
  }>(
    "/api/v1/parts/import",
    { method: "POST", body: JSON.stringify(rows) },
  );
