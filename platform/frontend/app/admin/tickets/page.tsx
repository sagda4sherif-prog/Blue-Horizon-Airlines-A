"use client";

import { useEffect, useState } from "react";
import { getTickets, Ticket } from "@/lib/api";

export default function TicketsPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [filter, setFilter] = useState<string>("");

  useEffect(() => {
    getTickets(filter || undefined)
      .then((r) => setTickets(r.tickets))
      .catch(() => setTickets([]));
  }, [filter]);

  return (
    <div>
      <h2>Tickets</h2>
      <p className="muted">
        Unplanned failures reported by state_graph/ runs — a tool errored, a
        schema didn't validate, the model returned something the graph
        couldn't act on. Distinct from HITL: nobody was ever supposed to
        approve this, it just broke.
      </p>

      <div className="row" style={{ marginBottom: 12 }}>
        {["", "open", "investigating", "resolved"].map((s) => (
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
              <th>Node</th>
              <th>Failure type</th>
              <th>Status</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr
                key={t.ticket_id}
                style={{ cursor: "pointer" }}
                onClick={() => (window.location.href = `/admin/tickets/${t.ticket_id}`)}
              >
                <td>#{t.ticket_id}</td>
                <td>{t.graph_name}</td>
                <td className="muted">{t.node_name || "—"}</td>
                <td><code>{t.failure_type}</code></td>
                <td>
                  <span className={`badge badge-${t.status}`}>{t.status}</span>
                </td>
                <td className="muted">{new Date(t.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {tickets.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">No tickets.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
