import { useCallback, useEffect, useState } from "react";
import { apiUrl } from "./api";
import { Dashboard } from "./Dashboard";

const DEMO_USER_ID = import.meta.env.VITE_DEMO_USER_ID || "demo-user";
const DEMO_USER_ROLE = import.meta.env.VITE_DEMO_USER_ROLE || "all";
const DEMO_BEARER_TOKEN = import.meta.env.VITE_DEMO_BEARER_TOKEN || "";

export function App() {
  const [page, setPage] = useState("chat");
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState({});
  const [handoffStatus, setHandoffStatus] = useState({});
  const [connectionStatus, setConnectionStatus] = useState("checking");

  const withAuthHeaders = useCallback((headers = {}) => {
    if (!DEMO_BEARER_TOKEN) return headers;
    return { ...headers, Authorization: `Bearer ${DEMO_BEARER_TOKEN}` };
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const health = await fetch(apiUrl("/health"));
        if (!health.ok) throw new Error("Health check failed");
        setConnectionStatus("online");

        await fetch(apiUrl("/api/auth/session"), {
          method: "POST",
          headers: withAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({
            user_id: DEMO_USER_ID,
            role: DEMO_USER_ROLE,
          }),
        });
      } catch (error) {
        setConnectionStatus("offline");
      }
    };

    bootstrap();
  }, [withAuthHeaders]);

  const sendFeedback = async (messageIdx, helpful) => {
    const assistantMessage = messages[messageIdx];
    if (!assistantMessage?.text || !assistantMessage?.query) return;

    setFeedbackStatus((prev) => ({ ...prev, [messageIdx]: "saving" }));
    try {
      await fetch(apiUrl("/api/feedback"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          user_id: DEMO_USER_ID,
          query: assistantMessage.query,
          answer: assistantMessage.text.trim(),
          helpful,
        }),
      });
      setFeedbackStatus((prev) => ({ ...prev, [messageIdx]: "saved" }));
    } catch (error) {
      setFeedbackStatus((prev) => ({ ...prev, [messageIdx]: "error" }));
    }
  };

  const requestLiveHandoff = async (messageIdx) => {
    const transcript = messages
      .slice(0, messageIdx + 1)
      .map((msg) => `${msg.role === "user" ? "User" : "Assistant"}: ${msg.text}`);
    setHandoffStatus((prev) => ({ ...prev, [messageIdx]: "sending" }));
    try {
      const response = await fetch(apiUrl("/api/integrations/purechat/handoff"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          user_id: DEMO_USER_ID,
          transcript,
        }),
      });
      if (!response.ok) throw new Error("Handoff request failed");
      setHandoffStatus((prev) => ({ ...prev, [messageIdx]: "sent" }));
    } catch (error) {
      setHandoffStatus((prev) => ({ ...prev, [messageIdx]: "error" }));
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    const userMessage = { role: "user", text: query };
    setLoading(true);
    let assistantIndex = 0;
    setMessages((prev) => {
      assistantIndex = prev.length + 1;
      return [
        ...prev,
        userMessage,
        { role: "assistant", text: "", sources: [], handoff: false, query: query.trim() },
      ];
    });

    try {
      const response = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          query,
          user_id: DEMO_USER_ID,
          role: DEMO_USER_ROLE,
        }),
      });
      if (response.status === 401) {
        throw new Error("Unauthorized token");
      }
      if (!response.ok || !response.body) throw new Error("Chat endpoint failed");
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const line = event
            .split("\n")
            .find((item) => item.startsWith("data:"))
            ?.replace("data:", "")
            .trim();
          if (!line) continue;
          const payload = JSON.parse(line);

          if (payload.type === "token") {
            setMessages((prev) =>
              prev.map((msg, idx) =>
                idx === assistantIndex ? { ...msg, text: `${msg.text}${payload.value}` } : msg
              )
            );
          }

          if (payload.type === "end") {
            setMessages((prev) =>
              prev.map((msg, idx) =>
                idx === assistantIndex
                  ? {
                      ...msg,
                      sources: payload.sources || [],
                      handoff: !!payload.requires_handoff,
                    }
                  : msg
              )
            );
          }
        }
      }
    } catch (error) {
      const fallbackMessage =
        error?.message === "Unauthorized token"
          ? "Unauthorized. Set a valid VITE_DEMO_BEARER_TOKEN for auth-enabled backend."
          : "Could not reach backend API.";
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", text: fallbackMessage, sources: [], handoff: false },
      ]);
    } finally {
      setQuery("");
      setLoading(false);
    }
  };

  return (
    <main className="app">
      <nav className="app-nav" aria-label="Primary">
        <button
          type="button"
          className={page === "chat" ? "nav-btn active" : "nav-btn"}
          onClick={() => setPage("chat")}
        >
          Chat
        </button>
        <button
          type="button"
          className={page === "analytics" ? "nav-btn active" : "nav-btn"}
          onClick={() => setPage("analytics")}
        >
          Analytics
        </button>
      </nav>

      {page === "analytics" ? (
        <Dashboard withAuthHeaders={withAuthHeaders} />
      ) : (
        <section className="chat-card">
          <header className="chat-header">
            <span>OU IT Assistant</span>
            <span className={`status-pill ${connectionStatus}`}>{connectionStatus}</span>
          </header>
          <div className="chat-body" aria-live="polite">
            {messages.map((msg, idx) => (
              <article key={idx} className={`bubble ${msg.role}`}>
                <p>{msg.text}</p>
                {msg.sources?.length > 0 && (
                  <ul>
                    {msg.sources.map((src) => (
                      <li key={src}>
                        <a href={src} target="_blank" rel="noreferrer">
                          {src}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
                {msg.handoff && <p className="handoff">I recommend live agent handoff.</p>}
                {msg.handoff && (
                  <div className="handoff-row">
                    <button
                      type="button"
                      onClick={() => requestLiveHandoff(idx)}
                      disabled={handoffStatus[idx] === "sending"}
                    >
                      Contact live agent
                    </button>
                    {handoffStatus[idx] === "sent" && <span>Handoff ready</span>}
                    {handoffStatus[idx] === "error" && <span>Handoff failed</span>}
                  </div>
                )}
                {msg.role === "assistant" && msg.text.trim().length > 0 && (
                  <div className="feedback-row">
                    <button
                      type="button"
                      onClick={() => sendFeedback(idx, true)}
                      disabled={feedbackStatus[idx] === "saving"}
                    >
                      Helpful
                    </button>
                    <button
                      type="button"
                      onClick={() => sendFeedback(idx, false)}
                      disabled={feedbackStatus[idx] === "saving"}
                    >
                      Not helpful
                    </button>
                    {feedbackStatus[idx] === "saved" && <span>Saved</span>}
                    {feedbackStatus[idx] === "error" && <span>Failed</span>}
                  </div>
                )}
              </article>
            ))}
            {loading && <p className="typing">Assistant is typing...</p>}
          </div>
          <form className="chat-input" onSubmit={sendMessage}>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Ask OU IT support question..."
            />
            <button type="submit">Send</button>
          </form>
        </section>
      )}
    </main>
  );
}
