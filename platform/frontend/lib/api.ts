// Thin fetch wrapper. All calls go through Next's /api/* rewrite
// (see next.config.js), which proxies to the FastAPI backend — the
// browser never talks to :8001 directly.

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

// ---- Chat ----

export type Agent = {
  id: string;
  name: string;
  description: string;
  available: boolean;
  unavailable_reason?: string;
};

export function getAgents() {
  return request<{ agents: Agent[] }>("/api/agents");
}

export type ChatMessage = { role: "user" | "assistant"; content: string };

export function sendChat(agent_id: string, messages: ChatMessage[]) {
  return request<{ role: string; content: string }>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ agent_id, messages }),
  });
}

// ---- Admin: tools ----

export type ToolInfo = { name: string; registered: boolean };

export function getTools() {
  return request<{ tools: ToolInfo[] }>("/api/admin/tools");
}

export function registerTool(name: string) {
  return request(`/api/admin/tools/${name}/register`, { method: "POST" });
}

export function unregisterTool(name: string) {
  return request(`/api/admin/tools/${name}/unregister`, { method: "POST" });
}

// ---- Admin: RAG documents ----

export type RagDocument = {
  doc_id: number;
  title: string;
  source_path: string | null;
  added_at: string;
};

export function getRagDocuments() {
  return request<{ documents: RagDocument[] }>("/api/admin/rag");
}

export function addRagDocument(title: string, content: string) {
  return request<{ doc_id: number; indexed: boolean }>("/api/admin/rag", {
    method: "POST",
    body: JSON.stringify({ title, content }),
  });
}

export function removeRagDocument(docId: number) {
  return request(`/api/admin/rag/${docId}`, { method: "DELETE" });
}

// ---- Tickets ----

export type Ticket = {
  ticket_id: number;
  graph_name: string;
  run_id: string;
  node_name: string | null;
  status: "open" | "investigating" | "resolved";
  failure_type: string;
  description: string;
  checkpoint_state: string;
  resolution_notes: string | null;
  created_at: string;
  resolved_at: string | null;
};

export function getTickets(status?: string) {
  const q = status ? `?status=${status}` : "";
  return request<{ tickets: Ticket[] }>(`/api/tickets${q}`);
}

export function getTicket(id: number) {
  return request<Ticket>(`/api/tickets/${id}`);
}

export function markInvestigating(id: number) {
  return request(`/api/tickets/${id}/investigate`, { method: "POST" });
}

export function resolveTicket(id: number, notes: string, resolvedBy: string) {
  return request(`/api/tickets/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ resolution_notes: notes, resolved_by: resolvedBy }),
  });
}

// ---- HITL ----

export type HitlRequest = {
  hitl_id: number;
  graph_name: string;
  run_id: string;
  node_name: string | null;
  status: "pending" | "approved" | "rejected";
  reason: string;
  summary: string;
  checkpoint_state: string;
  decision_payload: string | null;
  decided_by: string | null;
  created_at: string;
  decided_at: string | null;
};

export function getHitlRequests(status: string = "pending") {
  return request<{ requests: HitlRequest[] }>(`/api/hitl?status=${status}`);
}

export function getHitlRequest(id: number) {
  return request<HitlRequest>(`/api/hitl/${id}`);
}

export function decideHitl(
  id: number,
  approved: boolean,
  decidedBy: string,
  payload: Record<string, unknown> = {}
) {
  return request(`/api/hitl/${id}/decide`, {
    method: "POST",
    body: JSON.stringify({ approved, decided_by: decidedBy, payload }),
  });
}
