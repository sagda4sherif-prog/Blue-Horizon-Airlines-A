"use client";

import { useEffect, useRef, useState } from "react";
import { Agent, ChatMessage, getAgents, sendChat } from "@/lib/api";

const CHAT_STORAGE_KEY = "blue-horizon-chat-history-v3";
const ACTIVE_AGENT_STORAGE_KEY = "blue-horizon-active-agent";
const ACTIVE_CHAT_STORAGE_KEY = "blue-horizon-active-chat";

type Conversation = {
  id: string;
  title: string;
  agentId: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
};

export default function ChatPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeAgent, setActiveAgent] = useState<string>("operations");

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
  // Restore local state
  // ---------------------------------------------------------

  useEffect(() => {
    try {
      const savedChats =
        window.localStorage.getItem(CHAT_STORAGE_KEY);

      const savedAgent =
        window.localStorage.getItem(
          ACTIVE_AGENT_STORAGE_KEY
        );

      const savedActiveChat =
        window.localStorage.getItem(
          ACTIVE_CHAT_STORAGE_KEY
        );

      if (savedChats) {
        const parsed = JSON.parse(savedChats);

        if (Array.isArray(parsed)) {
          setConversations(parsed as Conversation[]);
        }
      }

      if (savedAgent) {
        setActiveAgent(savedAgent);
      }

      if (savedActiveChat) {
        setActiveChatId(savedActiveChat);
      }
    } catch (err) {
      console.error("Failed to restore chat history:", err);
    } finally {
      setStorageLoaded(true);
    }
  }, []);

  // ---------------------------------------------------------
  // Save conversations
  // ---------------------------------------------------------

  useEffect(() => {
    if (!storageLoaded) {
      return;
    }

    try {
      window.localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(conversations)
      );
    } catch (err) {
      console.error("Failed to save conversations:", err);
    }
  }, [conversations, storageLoaded]);

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
      console.error("Failed to save active agent:", err);
    }
  }, [activeAgent, storageLoaded]);

  // ---------------------------------------------------------
  // Save active chat
  // ---------------------------------------------------------

  useEffect(() => {
    if (!storageLoaded) {
      return;
    }

    if (activeChatId) {
      window.localStorage.setItem(
        ACTIVE_CHAT_STORAGE_KEY,
        activeChatId
      );
    } else {
      window.localStorage.removeItem(
        ACTIVE_CHAT_STORAGE_KEY
      );
    }
  }, [activeChatId, storageLoaded]);

  // ---------------------------------------------------------
  // Conversations for current agent ONLY
  // ---------------------------------------------------------

  const agentConversations = conversations
    .filter(
      (conversation) =>
        conversation.agentId === activeAgent
    )
    .sort(
      (a, b) => b.updatedAt - a.updatedAt
    );

  // ---------------------------------------------------------
  // Current conversation
  // ---------------------------------------------------------

  const activeConversation =
    conversations.find(
      (conversation) =>
        conversation.id === activeChatId &&
        conversation.agentId === activeAgent
    ) || null;

  const messages =
    activeConversation?.messages || [];

  // ---------------------------------------------------------
  // Scroll
  // ---------------------------------------------------------

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, activeChatId]);

  // ---------------------------------------------------------
  // Create new chat for CURRENT agent
  // ---------------------------------------------------------

  function createNewChat() {
    const newChat: Conversation = {
      id: `${Date.now()}-${Math.random()
        .toString(36)
        .slice(2, 8)}`,
      title: "New conversation",
      agentId: activeAgent,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };

    setConversations((previous) => [
      newChat,
      ...previous,
    ]);

    setActiveChatId(newChat.id);
    setError(null);
    setInput("");
  }

  // ---------------------------------------------------------
  // Clear CURRENT conversation only
  // ---------------------------------------------------------

  function clearCurrentChat() {
    if (!activeConversation) {
      return;
    }

    const confirmed = window.confirm(
      "Clear this conversation?\n\nThis will remove only the current conversation."
    );

    if (!confirmed) {
      return;
    }

    setConversations((previous) =>
      previous.filter(
        (conversation) =>
          conversation.id !== activeConversation.id
      )
    );

    setActiveChatId(null);
    setError(null);
    setInput("");
  }

  // ---------------------------------------------------------
  // Clear ALL chats for CURRENT agent only
  // ---------------------------------------------------------

  function clearAllAgentChats() {
    if (agentConversations.length === 0) {
      return;
    }

    const agentName =
      agents.find(
        (agent) => agent.id === activeAgent
      )?.name || activeAgent;

    const confirmed = window.confirm(
      `Clear all conversations for ${agentName}?\n\nThis will remove only this agent's chat history. Other agents' chats will remain safe.`
    );

    if (!confirmed) {
      return;
    }

    setConversations((previous) =>
      previous.filter(
        (conversation) =>
          conversation.agentId !== activeAgent
      )
    );

    setActiveChatId(null);
    setError(null);
    setInput("");
  }

  // ---------------------------------------------------------
  // Switch agent
  // ---------------------------------------------------------

  function switchAgent(agentId: string) {
    const agent = agents.find(
      (item) => item.id === agentId
    );

    if (!agent || !agent.available) {
      return;
    }

    setActiveAgent(agentId);
    setError(null);
    setInput("");

    // Find latest chat for this agent.
    const latestChat = conversations
      .filter(
        (conversation) =>
          conversation.agentId === agentId
      )
      .sort(
        (a, b) => b.updatedAt - a.updatedAt
      )[0];

    setActiveChatId(
      latestChat?.id || null
    );
  }

  // ---------------------------------------------------------
  // Open past chat
  // ---------------------------------------------------------

  function openChat(conversation: Conversation) {
    if (conversation.agentId !== activeAgent) {
      return;
    }

    setActiveChatId(conversation.id);
    setError(null);
    setInput("");
  }

  // ---------------------------------------------------------
  // Send
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

    let conversationId = activeChatId;

    // Create conversation if none exists.
    if (!conversationId) {
      const newChat: Conversation = {
        id: `${Date.now()}-${Math.random()
          .toString(36)
          .slice(2, 8)}`,
        title:
          trimmedInput.length > 45
            ? `${trimmedInput.slice(0, 45)}...`
            : trimmedInput,
        agentId: activeAgent,
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };

      conversationId = newChat.id;

      setConversations((previous) => [
        newChat,
        ...previous,
      ]);

      setActiveChatId(conversationId);
    }

    const currentConversation =
      conversations.find(
        (conversation) =>
          conversation.id === conversationId
      );

    const existingMessages =
      currentConversation?.messages || [];

    const nextMessages: ChatMessage[] = [
      ...existingMessages,
      {
        role: "user",
        content: trimmedInput,
      },
    ];

    setConversations((previous) =>
      previous.map((conversation) => {
        if (conversation.id !== conversationId) {
          return conversation;
        }

        return {
          ...conversation,
          title:
            conversation.messages.length === 0
              ? trimmedInput.length > 45
                ? `${trimmedInput.slice(0, 45)}...`
                : trimmedInput
              : conversation.title,
          messages: nextMessages,
          updatedAt: Date.now(),
        };
      })
    );

    setInput("");
    setSending(true);

    try {
      const reply = await sendChat(
        activeAgent,
        nextMessages
      );

      setConversations((previous) =>
        previous.map((conversation) => {
          if (conversation.id !== conversationId) {
            return conversation;
          }

          return {
            ...conversation,
            messages: [
              ...nextMessages,
              {
                role: "assistant",
                content: reply.content,
              },
            ],
            updatedAt: Date.now(),
          };
        })
      );
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
  // Date
  // ---------------------------------------------------------

  function formatDate(timestamp: number) {
    return new Date(timestamp).toLocaleDateString(
      undefined,
      {
        month: "short",
        day: "numeric",
      }
    );
  }

  // ---------------------------------------------------------
  // Current agent name
  // ---------------------------------------------------------

  const currentAgentName =
    agents.find(
      (agent) => agent.id === activeAgent
    )?.name || "Agent";

  // ---------------------------------------------------------
  // Render
  // ---------------------------------------------------------

  return (
    <div className="chat-shell">

      {/* ================================================= */}
      {/* Sidebar                                            */}
      {/* ================================================= */}

      <aside className="agent-list">

        {/* Agents */}

        <div className="chat-sidebar-section">
          <div className="chat-section-title">
            Agents
          </div>

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
                  switchAgent(agent.id);
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
        </div>

        {/* New Chat */}

        <div className="chat-sidebar-actions">
          <button
            className="new-chat-button"
            onClick={createNewChat}
          >
            + New Chat
          </button>
        </div>

        {/* Past Chats */}

        <div className="past-chats">

          <div className="past-header">
            <div className="chat-section-title">
              Past Chats
            </div>

            {agentConversations.length > 0 && (
              <button
                className="clear-all-button"
                onClick={clearAllAgentChats}
                title={`Clear all chats for ${currentAgentName}`}
              >
                Clear All
              </button>
            )}
          </div>

          <div className="past-agent-label">
            {currentAgentName}
          </div>

          {agentConversations.length === 0 && (
            <div className="past-empty">
              No previous conversations
            </div>
          )}

          {agentConversations.map(
            (conversation) => (
              <button
                key={conversation.id}
                className={
                  "past-chat-item" +
                  (conversation.id === activeChatId
                    ? " selected"
                    : "")
                }
                onClick={() =>
                  openChat(conversation)
                }
              >
                <div className="past-chat-title">
                  {conversation.title}
                </div>

                <div className="past-chat-meta">
                  {formatDate(
                    conversation.updatedAt
                  )}
                </div>
              </button>
            )
          )}
        </div>
      </aside>

      {/* ================================================= */}
      {/* Chat Area                                         */}
      {/* ================================================= */}

      <div className="chat-area">

        {/* Header */}

        <div className="chat-header">

          <div>
            <div className="chat-header-title">
              {currentAgentName}
            </div>

            <div className="muted">
              {activeConversation
                ? activeConversation.title
                : "New conversation"}
            </div>
          </div>

          <button
            className="danger"
            onClick={clearCurrentChat}
            disabled={!activeConversation}
          >
            Clear Chat
          </button>
        </div>

        {/* Messages */}

        <div className="chat-messages">

          {messages.length === 0 && (
            <div className="chat-empty-state">
              <div className="chat-empty-title">
                Blue Horizon Airlines
              </div>

              <p className="muted">
                Ask this agent something to get started.
              </p>
            </div>
          )}

          {messages.map((message, index) => (
            <div
              key={`${activeChatId}-${index}`}
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

        {/* Input */}

        <div className="chat-input">

          <input
            value={input}
            onChange={(event) => {
              setInput(event.target.value);
            }}
            onKeyDown={(event) => {
              if (
                event.key === "Enter" &&
                !event.shiftKey
              ) {
                event.preventDefault();
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
            {sending ? "Sending..." : "Send"}
          </button>

        </div>
      </div>
    </div>
  );
}
