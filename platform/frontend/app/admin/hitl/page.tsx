"use client";

import { useEffect, useState } from "react";
import { getHitlRequests, HitlRequest } from "@/lib/api";

export default function HitlPage() {
  const [requests, setRequests] = useState<HitlRequest[]>([]);
  const [filter, setFilter] = useState("pending");

  useEffect(() => {
    getHitlRequests(filter)
      .then((r) => setRequests(r.requests))
      .catch(() => setRequests([]));
  }, [filter]);

  return (
    <div>
      <h2>Human-in-the-Loop Queue</h2>
      <p className="muted">
        Expected pauses — a decision the graph isn't allowed to make alone
        (amount above a threshold, an action against policy, low confidence).
        The run only resumes once you act here.
      </p>

      <div className="row" style={{ marginBottom: 12 }}>
        {["pending", "approved", "rejected", ""].map((s) => (
          <button
            key={s}
            className={filter === s ? "" : "secondary"}
            onClick={() => setFilter(s)}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Graph</th>
              <th>Reason</th>
              <th>Summary</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {requests.map((r) => (
              <tr
                key={r.hitl_id}
                style={{ cursor: "pointer" }}
                onClick={() => (window.location.href = `/admin/hitl/${r.hitl_id}`)}
              >
                <td>#{r.hitl_id}</td>
                <td>{r.graph_name}</td>
                <td><code>{r.reason}</code></td>
                <td>{r.summary}</td>
                <td>
                  <span className={`badge badge-${r.status}`}>{r.status}</span>
                </td>
                <td className="muted">{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {requests.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">Nothing here.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
