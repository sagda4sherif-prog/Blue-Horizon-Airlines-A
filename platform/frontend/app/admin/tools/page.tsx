"use client";

import { useEffect, useState } from "react";
import { getTools, registerTool, unregisterTool, ToolInfo } from "@/lib/api";

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    getTools()
      .then((r) => setTools(r.tools))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function toggle(tool: ToolInfo) {
    setBusy(tool.name);
    setError(null);

    try {
      if (tool.registered) {
        await unregisterTool(tool.name);
      } else {
        await registerTool(tool.name);
      }
      load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <h2>Agent Tools</h2>
      <p className="muted">
        Registering or unregistering a tool here calls the live MCP server's
        tool_registry directly (mcp.add_tool / mcp.remove_tool) — the change
        takes effect immediately, no server restart.
      </p>

      {error && <div className="card" style={{ color: "#c0392b" }}>{error}</div>}

      <div className="card">
        {loading ? (
          <p className="muted">Loading…</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Tool</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tools.map((tool) => (
                <tr key={tool.name}>
                  <td><code>{tool.name}</code></td>
                  <td>
                    <span
                      className={`badge ${tool.registered ? "badge-approved" : "badge-open"}`}
                    >
                      {tool.registered ? "Registered" : "Unregistered"}
                    </span>
                  </td>
                  <td>
                    <button
                      className={tool.registered ? "danger" : ""}
                      disabled={busy === tool.name}
                      onClick={() => toggle(tool)}
                    >
                      {tool.registered ? "Unregister" : "Register"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
