import { useState } from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function App() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState({});

  const sendFeedback = async (messageIdx, helpful) => {
    const assistantMessage = messages[messageIdx];
    if (!assistantMessage?.text || !assistantMessage?.query) return;

    setFeedbackStatus((prev) => ({ ...prev, [messageIdx]: "saving" }));
    try {
      await fetch(`${API_BASE_URL}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "demo-user",
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
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          user_id: "demo-user",
          role: "all",
        }),
      });
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
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { role: "assistant", text: "Could not reach backend API.", sources: [], handoff: false },
      ]);
    } finally {
      setQuery("");
      setLoading(false);
    }
  };

  return (
    <main className="app">
      <section className="chat-card">
        <header className="chat-header">OU IT Assistant</header>
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
    </main>
  );
}
