"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getHitlRequest, decideHitl, HitlRequest } from "@/lib/api";

export default function HitlDetailPage() {
  const params = useParams();
  const id = Number(params.id);

  const [request, setRequest] = useState<HitlRequest | null>(null);
  const [decidedBy, setDecidedBy] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    getHitlRequest(id)
      .then((r) => setRequest(r))
      .catch((e) => setError(e.message));
  }

  useEffect(load, [id]);

  async function handleDecide(approved: boolean) {
    if (!decidedBy.trim()) {
      setError("Enter your name before deciding.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await decideHitl(id, approved, decidedBy, notes ? { notes } : {});
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!request) return <p className="muted">Loading…</p>;

  const state =
    typeof request.checkpoint_state === "string"
      ? request.checkpoint_state
      : JSON.stringify(request.checkpoint_state, null, 2);

  return (
    <div>
      <a href="/admin/hitl" className="muted">← Back to HITL queue</a>
      <h2>
        HITL Request #{request.hitl_id}{" "}
        <span className={`badge badge-${request.status}`}>{request.status}</span>
      </h2>

      {error && <div className="card" style={{ color: "#c0392b" }}>{error}</div>}

      <div className="card">
        <table>
          <tbody>
            <tr><th>Graph</th><td>{request.graph_name}</td></tr>
            <tr><th>Run ID</th><td><code>{request.run_id}</code></td></tr>
            <tr><th>Node</th><td>{request.node_name || "—"}</td></tr>
            <tr><th>Reason it needs a human</th><td><code>{request.reason}</code></td></tr>
            <tr><th>Decision needed</th><td>{request.summary}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <strong>Checkpoint state at pause</strong>
        <pre className="state">{state}</pre>
      </div>

      {request.status === "pending" ? (
        <div className="card">
          <strong>Decide</strong>
          <p className="muted">
            The graph is paused and will only continue after this is
            recorded — it reads this decision back on resume instead of
            proceeding as if nothing happened.
          </p>

          <input
            placeholder="Your name"
            value={decidedBy}
            onChange={(e) => setDecidedBy(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <textarea
            placeholder="Notes (optional)"
            rows={2}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />

          <div className="row" style={{ marginTop: 10 }}>
            <button disabled={busy} onClick={() => handleDecide(true)}>
              Approve
            </button>
            <button className="danger" disabled={busy} onClick={() => handleDecide(false)}>
              Reject
            </button>
          </div>
        </div>
      ) : (
        <div className="card">
          <strong>Decision</strong>
          <p>
            <span className={`badge badge-${request.status}`}>{request.status}</span>
            {" "}by {request.decided_by} on{" "}
            {request.decided_at && new Date(request.decided_at).toLocaleString()}
          </p>
          {request.decision_payload && (
            <pre className="state">{request.decision_payload}</pre>
          )}
        </div>
      )}
    </div>
  );
}
