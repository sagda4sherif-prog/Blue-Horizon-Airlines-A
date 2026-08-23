"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getTicket, markInvestigating, resolveTicket, Ticket } from "@/lib/api";

export default function TicketDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [notes, setNotes] = useState("");
  const [resolvedBy, setResolvedBy] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getTicket(id)
      .then((t) => setTicket(t))
      .catch((e) => setError(e.message));
  }

  useEffect(load, [id]);

  async function handleInvestigate() {
    setBusy(true);
    try {
      await markInvestigating(id);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function handleResolve() {
    if (!notes.trim() || !resolvedBy.trim()) {
      setError("Add resolution notes and your name before resolving.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await resolveTicket(id, notes, resolvedBy);
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!ticket) return <p className="muted">Loading…</p>;

  const state =
    typeof ticket.checkpoint_state === "string"
      ? ticket.checkpoint_state
      : JSON.stringify(ticket.checkpoint_state, null, 2);

  return (
    <div>
      <a href="/admin/tickets" className="muted">← Back to tickets</a>
      <h2>
        Ticket #{ticket.ticket_id}{" "}
        <span className={`badge badge-${ticket.status}`}>{ticket.status}</span>
      </h2>

      {error && <div className="card" style={{ color: "#c0392b" }}>{error}</div>}

      <div className="card">
        <table>
          <tbody>
            <tr><th>Graph</th><td>{ticket.graph_name}</td></tr>
            <tr><th>Run ID</th><td><code>{ticket.run_id}</code></td></tr>
            <tr><th>Node</th><td>{ticket.node_name || "—"}</td></tr>
            <tr><th>Failure type</th><td><code>{ticket.failure_type}</code></td></tr>
            <tr><th>Description</th><td>{ticket.description}</td></tr>
            <tr><th>Created</th><td>{new Date(ticket.created_at).toLocaleString()}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <strong>Checkpoint state at failure</strong>
        <pre className="state">{state}</pre>
      </div>

      {ticket.status !== "resolved" ? (
        <div className="card">
          <strong>Resolve</strong>
          <p className="muted">
            Resolving here flips the ticket's status. Actually resuming the
            run from this checkpoint is state_graph/'s job — it should poll
            or react to this status change and re-invoke the graph.
          </p>

          {ticket.status === "open" && (
            <button className="secondary" disabled={busy} onClick={handleInvestigate}>
              Mark investigating
            </button>
          )}

          <div style={{ marginTop: 12 }}>
            <input
              placeholder="Your name"
              value={resolvedBy}
              onChange={(e) => setResolvedBy(e.target.value)}
              style={{ marginBottom: 8 }}
            />
            <textarea
              placeholder="Resolution notes — what was wrong, what you did"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div style={{ marginTop: 8 }}>
              <button disabled={busy} onClick={handleResolve}>
                Resolve &amp; allow resume
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="card">
          <strong>Resolution</strong>
          <p>{ticket.resolution_notes}</p>
          <p className="muted">
            Resolved by {ticket.resolved_by} on{" "}
            {ticket.resolved_at && new Date(ticket.resolved_at).toLocaleString()}
          </p>
        </div>
      )}
    </div>
  );
}
