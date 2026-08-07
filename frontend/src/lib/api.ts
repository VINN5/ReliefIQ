const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type SignUpPayload = {
  full_name: string;
  organisation: string;
  email: string;
  password: string;
};

type SignInPayload = {
  email: string;
  password: string;
};

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const data = await res.json();
    // FastAPI validation errors come back as detail: [{ msg, loc, ... }]
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg: string }) => d.msg).join(" ");
    }
    if (typeof data.detail === "string") return data.detail;
  } catch {
    // response wasn't JSON — fall through to generic message
  }
  return "Something went wrong. Please try again.";
}

export async function signUp(payload: SignUpPayload) {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export async function signIn(payload: SignInPayload) {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/signin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json() as Promise<{ access_token: string; token_type: string }>;
}

const TOKEN_KEY = "reliefiq_token";

export function saveToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  if (!token) throw new ApiError("Not signed in.", 401);
  return { Authorization: `Bearer ${token}` };
}

export type UserRole = "field_staff" | "manager" | "admin";

export async function getCurrentUser() {
  const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) clearToken();
    throw new ApiError(await parseErrorDetail(res), res.status);
  }
  return res.json() as Promise<{
    id: string;
    full_name: string;
    organisation: string;
    email: string;
    role: UserRole;
  }>;
}

export type DocumentStatus =
  | "uploading"
  | "extracting"
  | "requires_ocr"
  | "extracted"
  | "chunking"
  | "chunked"
  | "embedding"
  | "indexing"
  | "ready"
  | "failed";

export type DocumentResponse = {
  id: string;
  title: string;
  doc_type: string | null;
  status: DocumentStatus;
  access_level: "standard" | "restricted";
  version: number;
  supersedes_id: string | null;
  is_superseded: boolean;
  created_at: string;
};

export async function uploadDocument(file: File, restricted: boolean = false): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  // FormData values are always strings — the backend's Form(bool) field
  // parses "true"/"false" (and "1"/"0") correctly via FastAPI/Starlette's
  // bool coercion, so this doesn't need any special encoding.
  formData.append("restricted", String(restricted));

  const res = await fetch(`${API_BASE_URL}/documents/upload`, {
    method: "POST",
    headers: authHeaders(), // no Content-Type — fetch sets the multipart boundary itself
    body: formData,
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

// Uploads a new version of an existing document. Omitting `restricted`
// inherits the old version's access level — pass true/false to override it.
export async function replaceDocument(
  documentId: string,
  file: File,
  restricted?: boolean
): Promise<DocumentResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (restricted !== undefined) formData.append("restricted", String(restricted));

  const res = await fetch(`${API_BASE_URL}/documents/${documentId}/replace`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export async function listDocuments(): Promise<DocumentResponse[]> {
  const res = await fetch(`${API_BASE_URL}/documents`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export type Citation = {
  number: number;
  document_title: string;
  page_number: number | null;
};

export type AnswerResponse = {
  question: string;
  answer: string;
  confidence: "high" | "medium" | "low";
  citations: Citation[];
  provider_used: string | null;
  needs_escalation: boolean;
  escalation_reason: string | null;
  escalation_contacts: string[];
  conversation_id: string;
};

// conversationId omitted -> backend starts a new conversation and
// returns its id in the response. Pass that id back in on the next
// call to continue the same thread instead of starting a new one.
export async function askQuestion(
  question: string,
  options: { topK?: number; conversationId?: string } = {}
): Promise<AnswerResponse> {
  const res = await fetch(`${API_BASE_URL}/query/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({
      question,
      top_k: options.topK ?? 5,
      conversation_id: options.conversationId ?? null,
    }),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

// --- Gap detection ---

export type CoverageStatus = "covered" | "partial" | "gap";

export type GapItem = {
  requirement: string;
  status: CoverageStatus;
  explanation: string;
  matched_documents: string[];
};

export type GapAnalysisResponse = {
  items: GapItem[];
  covered_count: number;
  partial_count: number;
  gap_count: number;
  total_requirements: number;
  summary: string;
  truncated: boolean;
};

// Exactly one of `file` or `text` should be provided — matches the
// backend's validation in gap_detection.py.
export async function analyzeGapDetection(input: { file?: File; text?: string }): Promise<GapAnalysisResponse> {
  const formData = new FormData();
  if (input.file) formData.append("file", input.file);
  if (input.text) formData.append("text", input.text);

  const res = await fetch(`${API_BASE_URL}/gap-detection/analyze`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

// --- Query history ---

export type QueryHistoryItem = {
  id: string;
  question: string;
  answer: string;
  confidence: "high" | "medium" | "low";
  provider_used: string | null;
  citations: Citation[];
  needs_escalation: boolean;
  escalation_reason: string | null;
  escalation_contacts: string[];
  created_at: string;
};

export async function getQueryHistory(limit = 20, offset = 0): Promise<QueryHistoryItem[]> {
  const res = await fetch(`${API_BASE_URL}/query/history?limit=${limit}&offset=${offset}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

// --- Conversations (chat sidebar + thread) ---

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ConversationMessage = {
  id: string;
  question: string;
  answer: string;
  confidence: "high" | "medium" | "low";
  provider_used: string | null;
  citations: Citation[];
  needs_escalation: boolean;
  escalation_reason: string | null;
  escalation_contacts: string[];
  created_at: string;
};

export async function listConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE_URL}/conversations`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export async function getConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
  const res = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  // 204 No Content has no body to parse — only attempt error parsing on failure.
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
}

// --- Admin: audit log viewer ---

export type AuditLogEntry = {
  id: string;
  action: string;
  user_id: string | null;
  user_email: string | null;
  organisation: string | null;
  resource_type: string | null;
  resource_id: string | null;
  detail: string | null;
  ip_address: string | null;
  created_at: string;
};

export type AuditLogPage = {
  items: AuditLogEntry[];
  total: number;
  limit: number;
  offset: number;
};

export async function getAuditLogs(params: {
  limit?: number;
  offset?: number;
  action?: string;
  userEmail?: string;
}): Promise<AuditLogPage> {
  const search = new URLSearchParams();
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  if (params.action) search.set("action", params.action);
  if (params.userEmail) search.set("user_email", params.userEmail);

  const res = await fetch(`${API_BASE_URL}/admin/audit-logs?${search.toString()}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export async function getAuditLogActions(): Promise<string[]> {
  const res = await fetch(`${API_BASE_URL}/admin/audit-logs/actions`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

// --- Conflict detection ---

export type ConflictItem = {
  target_excerpt: string;
  target_page: number | null;
  other_document_title: string;
  other_excerpt: string;
  other_page: number | null;
  confidence: number;
  explanation: string;
};

export type ConflictAnalysisResponse = {
  document_title: string;
  items: ConflictItem[];
  chunks_checked: number;
  comparisons_made: number;
  potential_conflicts_count: number;
  truncated: boolean;
  summary: string;
};

export async function analyzeConflicts(documentId: string): Promise<ConflictAnalysisResponse> {
  const res = await fetch(`${API_BASE_URL}/conflict-detection/analyze/${documentId}`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

// --- Spreadsheet analysis ---

export type SpreadsheetTable = {
  id: string;
  sheet_name: string;
  headers: string[];
  rows: (string | number | null)[][];
  row_count: number;
};

export type SheetComparison = {
  sheet_name: string;
  columns_added: string[];
  columns_removed: string[];
  rows_added: (string | number | null)[][];
  rows_removed: (string | number | null)[][];
  old_row_count: number;
  new_row_count: number;
  headers: string[];
  truncated: boolean;
};

export type SpreadsheetComparisonResponse = {
  old_document_title: string;
  new_document_title: string;
  sheets_added: string[];
  sheets_removed: string[];
  sheet_comparisons: SheetComparison[];
  summary: string;
};

export async function getSpreadsheetTables(documentId: string): Promise<SpreadsheetTable[]> {
  const res = await fetch(`${API_BASE_URL}/spreadsheets/${documentId}/tables`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}

export async function compareSpreadsheets(documentId: string): Promise<SpreadsheetComparisonResponse> {
  const res = await fetch(`${API_BASE_URL}/spreadsheets/${documentId}/compare`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new ApiError(await parseErrorDetail(res), res.status);
  return res.json();
}