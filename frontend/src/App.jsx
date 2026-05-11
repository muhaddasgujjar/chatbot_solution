import { useCallback, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { apiUrl } from "./api";
import { clearSession, getSession } from "./authSession";
import { AdminPanel } from "./AdminPanel";
import { Dashboard } from "./Dashboard";
import { LoginPage } from "./LoginPage";

const DEMO_BEARER_TOKEN = import.meta.env.VITE_DEMO_BEARER_TOKEN || "";

export const ROLE_META = {
  student: { label: "Student", primary: "#2563eb", light: "#dbeafe" },
  faculty: { label: "Faculty", primary: "#b2945b", light: "#fef3c7" },
  staff:   { label: "Staff",   primary: "#059669", light: "#d1fae5" },
  alumni:  { label: "Alumni",  primary: "#7c3aed", light: "#ede9fe" },
  all:     { label: "Guest",   primary: "#374151", light: "#f3f4f6" },
};

function Avatar({ role, isBot }) {
  const meta = ROLE_META[role] || ROLE_META.all;
  return (
    <div className="avatar" style={{ background: isBot ? "#1a1a1a" : meta.primary }}>
      {isBot ? "AI" : (role?.[0]?.toUpperCase() || "U")}
    </div>
  );
}

function TypingIndicator() {
  return (
    <motion.div
      className="message-row assistant"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.85 }}
      transition={{ duration: 0.2 }}
    >
      <Avatar isBot />
      <div className="bubble assistant typing-bubble" aria-label="Assistant is typing">
        <span className="dot" style={{ animationDelay: "0ms" }} />
        <span className="dot" style={{ animationDelay: "200ms" }} />
        <span className="dot" style={{ animationDelay: "400ms" }} />
      </div>
    </motion.div>
  );
}

function TicketForm({ userId, userRole, query, withAuthHeaders }) {
  const [open, setOpen]     = useState(false);
  const [title, setTitle]   = useState("");
  const [email, setEmail]   = useState("");
  const [status, setStatus] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    if (status === "sending" || status === "sent") return;
    setStatus("sending");
    try {
      const res = await fetch(apiUrl("/api/integrations/tdx/tickets/create"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          title: title.trim(),
          description: `Chatbot escalation — user query: "${query}". User ID: ${userId}. Role: ${userRole}.`,
          requester_email: email.trim(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Failed");
      setStatus("sent");
    } catch {
      setStatus("error");
    }
  };

  if (status === "sent") {
    return <p className="ticket-status ok">✓ Support ticket submitted</p>;
  }

  return (
    <div className="ticket-form">
      {!open ? (
        <button type="button" className="btn-ticket" onClick={() => setOpen(true)}>
          Create support ticket
        </button>
      ) : (
        <form onSubmit={submit}>
          <input
            type="text"
            placeholder="Issue summary"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            required
            minLength={3}
            className="ticket-input"
            aria-label="Ticket title"
          />
          <input
            type="email"
            placeholder="Your email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="ticket-input"
            aria-label="Requester email"
          />
          <div className="ticket-actions">
            <button type="submit" className="btn-ticket primary" disabled={status === "sending"}>
              {status === "sending" ? "Submitting…" : "Submit ticket"}
            </button>
            <button type="button" className="btn-ticket" onClick={() => { setOpen(false); setStatus(null); }}>
              Cancel
            </button>
          </div>
          {status === "error" && <p className="ticket-status err">Submission failed — please try again.</p>}
        </form>
      )}
    </div>
  );
}

function MessageBubble({ msg, idx, userRole, userId, withAuthHeaders, sendFeedback, feedbackStatus, requestLiveHandoff, handoffStatus }) {
  const isUser = msg.role === "user";
  const meta = ROLE_META[userRole] || ROLE_META.all;

  return (
    <motion.div
      className={`message-row ${msg.role}`}
      initial={{ opacity: 0, x: isUser ? 20 : -20, y: 6 }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ type: "spring", stiffness: 340, damping: 30 }}
    >
      {!isUser && <Avatar role={userRole} isBot />}

      <div
        className={`bubble ${msg.role}`}
        style={isUser ? { background: meta.primary, color: "#fff" } : {}}
      >
        <p className="bubble-text">
          {msg.text || <span style={{ opacity: 0.3 }}>▊</span>}
        </p>

        {msg.sources?.length > 0 && (
          <div className="sources">
            <p className="sources-label">Sources</p>
            <ul>
              {msg.sources.map((src) => {
                const display = src.replace(/^https?:\/\//, "");
                return (
                  <li key={src}>
                    <a href={src} target="_blank" rel="noreferrer" className="source-link">
                      {display.length > 58 ? display.slice(0, 58) + "…" : display}
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {msg.handoff && (
          <div className="handoff-banner">
            <div className="handoff-top">
              <span>A live agent can help further</span>
              <button
                type="button"
                className="btn-handoff"
                onClick={() => requestLiveHandoff(idx)}
                disabled={handoffStatus[idx] === "sending" || handoffStatus[idx] === "sent"}
                aria-label="Connect to live support agent"
              >
                {handoffStatus[idx] === "sending" ? "Connecting…"
                 : handoffStatus[idx] === "sent"  ? "✓ Connected"
                 : handoffStatus[idx] === "error" ? "Retry"
                 : "Connect to agent"}
              </button>
            </div>
            <TicketForm
              userId={userId}
              userRole={userRole}
              query={msg.query || ""}
              withAuthHeaders={withAuthHeaders}
            />
          </div>
        )}

        {!isUser && msg.text.trim().length > 0 && (
          <div className="feedback-row" role="group" aria-label="Was this response helpful?">
            <motion.button
              type="button"
              className={`btn-feedback${feedbackStatus[idx] === "saved" ? " saved" : ""}`}
              onClick={() => sendFeedback(idx, true)}
              disabled={feedbackStatus[idx] === "saving" || feedbackStatus[idx] === "saved"}
              title="Helpful"
              aria-label="Mark as helpful"
              whileTap={{ scale: 0.82 }}
            >
              👍
            </motion.button>
            <motion.button
              type="button"
              className="btn-feedback"
              onClick={() => sendFeedback(idx, false)}
              disabled={feedbackStatus[idx] === "saving" || feedbackStatus[idx] === "saved"}
              title="Not helpful"
              aria-label="Mark as not helpful"
              whileTap={{ scale: 0.82 }}
            >
              👎
            </motion.button>
            {feedbackStatus[idx] === "saved" && (
              <motion.span
                className="feedback-saved"
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                aria-live="polite"
              >
                Saved
              </motion.span>
            )}
          </div>
        )}
      </div>

      {isUser && <Avatar role={userRole} />}
    </motion.div>
  );
}

export function App() {
  const [session, setSession]             = useState(() => getSession());
  const [page, setPage]                   = useState("chat");
  const [query, setQuery]                 = useState("");
  const [messages, setMessages]           = useState([]);
  const [loading, setLoading]             = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState({});
  const [handoffStatus, setHandoffStatus]   = useState({});
  const [connectionStatus, setConnectionStatus] = useState("checking");
  const messagesEndRef = useRef(null);
  const inputRef       = useRef(null);

  const userId   = session?.userId || "demo-user";
  const userRole = session?.role   || "all";
  const meta     = ROLE_META[userRole] || ROLE_META.all;

  const withAuthHeaders = useCallback((headers = {}) => {
    if (!DEMO_BEARER_TOKEN) return headers;
    return { ...headers, Authorization: `Bearer ${DEMO_BEARER_TOKEN}` };
  }, []);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Bootstrap session
  useEffect(() => {
    if (!session) return;
    (async () => {
      try {
        const h = await fetch(apiUrl("/health"));
        if (!h.ok) throw new Error();
        setConnectionStatus("online");
        await fetch(apiUrl("/api/auth/session"), {
          method: "POST",
          headers: withAuthHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ user_id: userId, role: userRole }),
        });
      } catch {
        setConnectionStatus("offline");
      }
    })();
  }, [session, userId, userRole, withAuthHeaders]);

  const handleLoggedIn = (s) => {
    setSession(s);
    setPage("chat");
    setMessages([]);
    setConnectionStatus("checking");
  };

  const handleLogout = () => {
    clearSession();
    setSession(null);
    setMessages([]);
  };

  const sendFeedback = async (messageIdx, helpful) => {
    const msg = messages[messageIdx];
    if (!msg?.text || !msg?.query) return;
    setFeedbackStatus((p) => ({ ...p, [messageIdx]: "saving" }));
    try {
      await fetch(apiUrl("/api/feedback"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ user_id: userId, query: msg.query, answer: msg.text.trim(), helpful }),
      });
      setFeedbackStatus((p) => ({ ...p, [messageIdx]: "saved" }));
    } catch {
      setFeedbackStatus((p) => ({ ...p, [messageIdx]: "error" }));
    }
  };

  const requestLiveHandoff = async (messageIdx) => {
    const transcript = messages
      .slice(0, messageIdx + 1)
      .map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.text}`);
    setHandoffStatus((p) => ({ ...p, [messageIdx]: "sending" }));
    try {
      const res = await fetch(apiUrl("/api/integrations/purechat/handoff"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ user_id: userId, transcript }),
      });
      if (!res.ok) throw new Error();
      setHandoffStatus((p) => ({ ...p, [messageIdx]: "sent" }));
    } catch {
      setHandoffStatus((p) => ({ ...p, [messageIdx]: "error" }));
    }
  };

  const sendMessage = async (e) => {
    e.preventDefault();
    const currentQuery = query.trim();
    if (!currentQuery || loading) return;

    setLoading(true);
    setQuery("");

    let assistantIndex = 0;
    setMessages((prev) => {
      assistantIndex = prev.length + 1;
      return [
        ...prev,
        { role: "user", text: currentQuery },
        { role: "assistant", text: "", sources: [], handoff: false, query: currentQuery },
      ];
    });

    try {
      const response = await fetch(apiUrl("/api/chat"), {
        method: "POST",
        headers: withAuthHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ query: currentQuery, user_id: userId, role: userRole }),
      });
      if (response.status === 401) throw new Error("Unauthorized token");
      if (!response.ok || !response.body) throw new Error("Chat endpoint failed");

      const reader  = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer    = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const line = event
            .split("\n")
            .find((l) => l.startsWith("data:"))
            ?.replace("data:", "")
            .trim();
          if (!line) continue;
          const payload = JSON.parse(line);

          if (payload.type === "token") {
            setMessages((prev) =>
              prev.map((m, i) =>
                i === assistantIndex ? { ...m, text: m.text + payload.value } : m
              )
            );
          }
          if (payload.type === "end") {
            setMessages((prev) =>
              prev.map((m, i) =>
                i === assistantIndex
                  ? { ...m, sources: payload.sources || [], handoff: !!payload.requires_handoff }
                  : m
              )
            );
          }
        }
      }
    } catch (err) {
      const text =
        err?.message === "Unauthorized token"
          ? "Session expired — please log in again."
          : "Could not reach the assistant. Please try again in a moment.";
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", text, sources: [], handoff: false },
      ]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  };

  if (!session) return <LoginPage onLoggedIn={handleLoggedIn} />;

  const NAV_TABS = [
    { id: "chat",      label: "Chat"      },
    { id: "analytics", label: "Dashboard" },
    { id: "admin",     label: "Admin"     },
  ];

  return (
    <motion.div
      className="app"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.22 }}
    >
      {/* WCAG skip link */}
      <a href="#main-content" className="skip-link">Skip to main content</a>

      {/* ── Header ── */}
      <header className="app-header">
        <div className="app-brand">
          <div className="app-logo" style={{ background: meta.primary }}>OU</div>
          <div>
            <div className="app-brand-name">IT Assistant</div>
            <div className="app-brand-sub">Oakland University</div>
          </div>
        </div>
        <div className="header-right">
          <div className="user-chip" aria-label={`Signed in as ${session.displayName || session.email}, role: ${meta.label}`}>
            <div className="user-chip-avatar" style={{ background: meta.primary }}>
              {(session.displayName || session.email)?.[0]?.toUpperCase()}
            </div>
            <div className="user-chip-info">
              <span className="user-chip-name">{session.displayName || session.email}</span>
              <span className="user-chip-role" style={{ color: meta.primary }}>{meta.label}</span>
            </div>
          </div>
          <button type="button" className="btn-logout" onClick={handleLogout} aria-label="Sign out">
            Sign out
          </button>
        </div>
      </header>

      {/* ── Nav ── */}
      <nav className="app-nav" aria-label="Main navigation">
        {NAV_TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            className={`nav-btn${page === id ? " active" : ""}`}
            style={page === id ? { background: meta.primary } : {}}
            onClick={() => setPage(id)}
            aria-current={page === id ? "page" : undefined}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* ── Pages ── */}
      <main id="main-content">

        <AnimatePresence mode="wait">
          {page === "analytics" && (
            <motion.div
              key="dashboard"
              className="dashboard-wrap"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -14 }}
              transition={{ duration: 0.2 }}
            >
              <Dashboard withAuthHeaders={withAuthHeaders} audienceRole={userRole} meta={meta} />
            </motion.div>
          )}

          {page === "admin" && (
            <motion.div
              key="admin"
              className="dashboard-wrap"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -14 }}
              transition={{ duration: 0.2 }}
            >
              <AdminPanel withAuthHeaders={withAuthHeaders} accentColor={meta.primary} />
            </motion.div>
          )}

          {page === "chat" && (
            <motion.div
              key="chat"
              className="chat-container"
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -14 }}
              transition={{ duration: 0.2 }}
            >
              <section className="chat-card" aria-label="Chat with OU IT Assistant">
                {/* Chat Header */}
                <header className="chat-header" style={{ background: meta.primary }}>
                  <div className="chat-header-left">
                    <div className="bot-avatar" aria-hidden="true">AI</div>
                    <div>
                      <div className="chat-header-title">OU IT Assistant</div>
                      <div className="chat-header-sub">Answers tuned for {meta.label}s</div>
                    </div>
                  </div>
                  <div
                    className={`status-pill ${connectionStatus}`}
                    role="status"
                    aria-live="polite"
                    aria-label={`Connection status: ${connectionStatus}`}
                  >
                    <span className="status-dot" aria-hidden="true" />
                    {connectionStatus}
                  </div>
                </header>

                {/* Messages + Empty State */}
                <div
                  className="chat-body"
                  role="log"
                  aria-live="polite"
                  aria-label="Conversation"
                  aria-atomic="false"
                >
                  <AnimatePresence>
                    {messages.length === 0 && !loading && (
                      <motion.div
                        key="empty"
                        className="chat-empty"
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                        transition={{ duration: 0.25 }}
                      >
                        <div className="chat-empty-icon" style={{ background: meta.light }} aria-hidden="true">💬</div>
                        <h3>Hello, {session.displayName || "there"}!</h3>
                        <p>
                          Ask any IT question. I'll answer using the OU knowledge
                          base with responses tailored for {meta.label}s.
                        </p>
                      </motion.div>
                    )}
                    {messages.map((msg, idx) => (
                      <MessageBubble
                        key={idx}
                        msg={msg}
                        idx={idx}
                        userRole={userRole}
                        userId={userId}
                        withAuthHeaders={withAuthHeaders}
                        sendFeedback={sendFeedback}
                        feedbackStatus={feedbackStatus}
                        requestLiveHandoff={requestLiveHandoff}
                        handoffStatus={handoffStatus}
                      />
                    ))}
                    {loading && <TypingIndicator key="typing" />}
                  </AnimatePresence>
                  <div ref={messagesEndRef} aria-hidden="true" />
                </div>

                {/* Input */}
                <form
                  className="chat-input-area"
                  onSubmit={sendMessage}
                  aria-label="Send a message"
                >
                  <div className="chat-input-wrap">
                    <input
                      ref={inputRef}
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder={`Ask an IT question for ${meta.label}s…`}
                      disabled={loading}
                      className="chat-input"
                      autoComplete="off"
                      aria-label="Your question"
                      aria-busy={loading}
                    />
                    <motion.button
                      type="submit"
                      className="btn-send"
                      style={{ background: meta.primary }}
                      disabled={loading || !query.trim()}
                      whileHover={{ scale: 1.1 }}
                      whileTap={{ scale: 0.9 }}
                      aria-label="Send message"
                    >
                      {loading ? (
                        <span className="spinner" aria-hidden="true" />
                      ) : (
                        <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true">
                          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                        </svg>
                      )}
                    </motion.button>
                  </div>
                  <p className="chat-input-hint" aria-hidden="true">Press Enter to send</p>
                </form>
              </section>
            </motion.div>
          )}
        </AnimatePresence>
      </main>

      {/* ── Footer ── */}
      <footer className="app-footer">
        <span>Built by </span>
        <a
          href="https://github.com/muhaddasgujjar"
          target="_blank"
          rel="noreferrer"
          className="footer-link"
        >
          Muhammad Muhaddas
        </a>
        <span className="footer-sep">·</span>
        <a
          href="https://github.com/muhaddasgujjar/chatbot-solution"
          target="_blank"
          rel="noreferrer"
          className="footer-link"
        >
          View on GitHub
        </a>
      </footer>
    </motion.div>
  );
}
