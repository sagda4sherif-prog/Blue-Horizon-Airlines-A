"use client";

import { useEffect, useState } from "react";
import {
  getTools,
  getRagDocuments,
  getTickets,
  getHitlRequests,
  ToolInfo,
  RagDocument,
  Ticket,
  HitlRequest,
} from "@/lib/api";

export default function AdminOverview() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [docs, setDocs] = useState<RagDocument[]>([]);
  const [openTickets, setOpenTickets] = useState<Ticket[]>([]);
  const [pendingHitl, setPendingHitl] = useState<HitlRequest[]>([]);

  useEffect(() => {
    getTools().then((r) => setTools(r.tools)).catch(() => {});
    getRagDocuments().then((r) => setDocs(r.documents)).catch(() => {});
    getTickets("open").then((r) => setOpenTickets(r.tickets)).catch(() => {});
    getHitlRequests("pending").then((r) => setPendingHitl(r.requests)).catch(() => {});
  }, []);

  const registeredCount = tools.filter((t) => t.registered).length;

  return (
    <div>
      <h2>Overview</h2>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <div className="card">
          <div className="muted">Registered tools</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>
            {registeredCount} / {tools.length}
          </div>
          <a href="/admin/tools" className="muted">Manage →</a>
        </div>

        <div className="card">
          <div className="muted">RAG documents</div>
          <div style={{ fontSize: 28, fontWeight: 700 }}>{docs.length}</div>
          <a href="/admin/rag" className="muted">Manage →</a>
        </div>

        <div className="card">
          <div className="muted">Open tickets</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: openTickets.length ? "#c0392b" : undefined }}>
            {openTickets.length}
          </div>
          <a href="/admin/tickets" className="muted">Review →</a>
        </div>

        <div className="card">
          <div className="muted">Pending HITL</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: pendingHitl.length ? "#b7791f" : undefined }}>
            {pendingHitl.length}
          </div>
          <a href="/admin/hitl" className="muted">Review →</a>
        </div>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <strong>What's live vs. pending on this admin surface</strong>
        <ul className="muted" style={{ lineHeight: 1.8 }}>
          <li>Agent Tools — fully live: register/unregister here reaches the running MCP server immediately.</li>
          <li>RAG Documents — durably saved here; retrieval-side indexing lights up once the RAG pipeline exposes add/remove.</li>
          <li>Tickets &amp; HITL — fully live CRUD; entries are created by state_graph/ runs (see platform/API_CONTRACT.md). Seeded demo data is included so this screen isn't empty before those graphs exist.</li>
        </ul>
      </div>
    </div>
  );
}
