"use client";

import { useEffect, useRef, useState } from "react";
import { Agent, ChatMessage, getAgents, sendChat } from "@/lib/api";

export default function ChatPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeAgent, setActiveAgent] = useState<string>("operations");
  const [messagesByAgent, setMessagesByAgent] = useState<
    Record<string, ChatMessage[]>
  >({});
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getAgents()
      .then((res) => setAgents(res.agents))
      .catch(() => setAgents([]));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messagesByAgent, activeAgent]);

  const messages = messagesByAgent[activeAgent] || [];

  async function handleSend() {
    if (!input.trim() || sending) return;

    const agent = agents.find((a) => a.id === activeAgent);

    if (agent && !agent.available) {
      setError(agent.unavailable_reason || "This agent isn't available yet.");
      return;
    }

    setError(null);

    const nextMessages: ChatMessage[] = [
      ...messages,
      { role: "user", content: input },
    ];

    setMessagesByAgent((prev) => ({ ...prev, [activeAgent]: nextMessages }));
    setInput("");
    setSending(true);

    try {
      const reply = await sendChat(activeAgent, nextMessages);

      setMessagesByAgent((prev) => ({
        ...prev,
        [activeAgent]: [
          ...nextMessages,
          { role: "assistant", content: reply.content },
        ],
      }));
    } catch (e: any) {
      setError(e.message || "Something went wrong.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chat-shell">
      <aside className="agent-list">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className={
              "agent-item" +
              (agent.id === activeAgent ? " active" : "") +
              (!agent.available ? " disabled" : "")
            }
            onClick={() => agent.available && setActiveAgent(agent.id)}
            title={agent.available ? undefined : agent.unavailable_reason}
          >
            <div style={{ fontWeight: 600, fontSize: 14 }}>{agent.name}</div>
            <div className="muted">{agent.description}</div>
            {!agent.available && (
              <div className="muted" style={{ marginTop: 4 }}>
                Coming soon
              </div>
            )}
          </div>
        ))}
      </aside>

      <div className="chat-area">
        <div className="chat-messages">
          {messages.length === 0 && (
            <p className="muted">
              Ask this agent something to get started.
            </p>
          )}

          {messages.map((m, i) => (
            <div key={i} className={`msg ${m.role}`}>
              {m.content}
            </div>
          ))}

          {sending && <div className="msg assistant">Thinking…</div>}

          {error && (
            <div className="msg assistant" style={{ color: "#c0392b" }}>
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <div className="chat-input">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about a flight, disruption, or policy…"
            disabled={sending}
          />
          <button onClick={handleSend} disabled={sending}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
