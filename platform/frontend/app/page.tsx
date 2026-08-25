"use client";

import { useEffect, useRef, useState } from "react";
import { Agent, ChatMessage, getAgents, sendChat } from "@/lib/api";

const CHAT_STORAGE_KEY = "blue-horizon-chat-history";
const ACTIVE_AGENT_STORAGE_KEY = "blue-horizon-active-agent";

export default function ChatPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeAgent, setActiveAgent] =
    useState<string>("operations");

  const [messagesByAgent, setMessagesByAgent] = useState<
    Record<string, ChatMessage[]>
  >({});

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Important:
  // Do not save anything to localStorage until the existing
  // chat history has been restored.
  const [storageLoaded, setStorageLoaded] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  // ---------------------------------------------------------
  // Load agents
  // ---------------------------------------------------------

  useEffect(() => {
    getAgents()
      .then((res) => {
        setAgents(res.agents);
      })
      .catch((err) => {
        console.error("Failed to load agents:", err);
        setAgents([]);
      });
  }, []);

  // ---------------------------------------------------------
  // Restore chat history from localStorage
  // ---------------------------------------------------------

  useEffect(() => {
    try {
      const savedMessages =
        window.localStorage.getItem(CHAT_STORAGE_KEY);

      const savedAgent =
        window.localStorage.getItem(
          ACTIVE_AGENT_STORAGE_KEY
        );

      if (savedMessages) {
        const parsed = JSON.parse(savedMessages);

        if (
          parsed !== null &&
          typeof parsed === "object" &&
          !Array.isArray(parsed)
        ) {
          setMessagesByAgent(
            parsed as Record<string, ChatMessage[]>
          );
        }
      }

      if (savedAgent) {
        setActiveAgent(savedAgent);
      }
    } catch (err) {
      console.error(
        "Failed to restore chat history:",
        err
      );
    } finally {
      // This must happen after the restore attempt.
      setStorageLoaded(true);
    }
  }, []);

  // ---------------------------------------------------------
  // Save chat history
  // ---------------------------------------------------------

  useEffect(() => {
    // Prevent the initial empty state from overwriting
    // existing localStorage data.
    if (!storageLoaded) {
      return;
    }

    try {
      window.localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(messagesByAgent)
      );
    } catch (err) {
      console.error(
        "Failed to save chat history:",
        err
      );
    }
  }, [messagesByAgent, storageLoaded]);

  // ---------------------------------------------------------
  // Save active agent
  // ---------------------------------------------------------

  useEffect(() => {
    if (!storageLoaded) {
      return;
    }

    try {
      window.localStorage.setItem(
        ACTIVE_AGENT_STORAGE_KEY,
        activeAgent
      );
    } catch (err) {
      console.error(
        "Failed to save active agent:",
        err
      );
    }
  }, [activeAgent, storageLoaded]);

  // ---------------------------------------------------------
  // Scroll to latest message
  // ---------------------------------------------------------

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messagesByAgent, activeAgent]);

  // ---------------------------------------------------------
  // Current agent messages
  // ---------------------------------------------------------

  const messages =
    messagesByAgent[activeAgent] || [];

  // ---------------------------------------------------------
  // Send message
  // ---------------------------------------------------------

  async function handleSend() {
    const trimmedInput = input.trim();

    if (!trimmedInput || sending) {
      return;
    }

    const agent = agents.find(
      (item) => item.id === activeAgent
    );

    if (agent && !agent.available) {
      setError(
        agent.unavailable_reason ||
          "This agent isn't available yet."
      );

      return;
    }

    setError(null);

    const nextMessages: ChatMessage[] = [
      ...messages,
      {
        role: "user",
        content: trimmedInput,
      },
    ];

    // Immediately save the user's message in React state.
    setMessagesByAgent((previous) => ({
      ...previous,
      [activeAgent]: nextMessages,
    }));

    setInput("");
    setSending(true);

    try {
      const reply = await sendChat(
        activeAgent,
        nextMessages
      );

      setMessagesByAgent((previous) => ({
        ...previous,
        [activeAgent]: [
          ...nextMessages,
          {
            role: "assistant",
            content: reply.content,
          },
        ],
      }));
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Something went wrong.";

      setError(message);
    } finally {
      setSending(false);
    }
  }

  // ---------------------------------------------------------
  // Render
  // ---------------------------------------------------------

  return (
    <div className="chat-shell">
      {/* ------------------------------------------------- */}
      {/* Agent List                                         */}
      {/* ------------------------------------------------- */}

      <aside className="agent-list">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className={
              "agent-item" +
              (agent.id === activeAgent
                ? " active"
                : "") +
              (!agent.available
                ? " disabled"
                : "")
            }
            onClick={() => {
              if (agent.available) {
                setActiveAgent(agent.id);
                setError(null);
              }
            }}
            title={
              agent.available
                ? undefined
                : agent.unavailable_reason
            }
          >
            <div
              style={{
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              {agent.name}
            </div>

            <div className="muted">
              {agent.description}
            </div>

            {!agent.available && (
              <div
                className="muted"
                style={{
                  marginTop: 4,
                }}
              >
                Coming soon
              </div>
            )}
          </div>
        ))}
      </aside>

      {/* ------------------------------------------------- */}
      {/* Chat Area                                          */}
      {/* ------------------------------------------------- */}

      <div className="chat-area">
        <div className="chat-messages">
          {messages.length === 0 && (
            <p className="muted">
              Ask this agent something to get started.
            </p>
          )}

          {messages.map((message, index) => (
            <div
              key={`${activeAgent}-${index}`}
              className={`msg ${message.role}`}
            >
              {message.content}
            </div>
          ))}

          {sending && (
            <div className="msg assistant">
              Thinking...
            </div>
          )}

          {error && (
            <div
              className="msg assistant"
              style={{
                color: "#c0392b",
              }}
            >
              {error}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* ------------------------------------------------ */}
        {/* Chat Input                                       */}
        {/* ------------------------------------------------ */}

        <div className="chat-input">
          <input
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                handleSend();
              }
            }}
            placeholder="Ask about a flight, disruption, or policy..."
            disabled={sending}
          />

          <button
            onClick={handleSend}
            disabled={sending}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

