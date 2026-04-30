import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { login, signup } from "./authSession";

const ROLES = [
  { id: "student", label: "Student" },
  { id: "faculty", label: "Faculty" },
  { id: "staff",   label: "Staff"   },
  { id: "alumni",  label: "Alumni"  },
];

const FEATURES = [
  { icon: "🎓", label: "Role-aware answers",  desc: "Responses tailored to students, faculty, staff, or alumni" },
  { icon: "📚", label: "OU knowledge base",   desc: "Grounded in official support.oakland.edu content" },
  { icon: "🔒", label: "Privacy first",       desc: "PII is stripped before any AI processing" },
  { icon: "🤝", label: "Live agent handoff",  desc: "Escalate to human support when needed" },
];

export function LoginPage({ onLoggedIn }) {
  const [mode, setMode]               = useState("login");
  const [email, setEmail]             = useState("");
  const [password, setPassword]       = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole]               = useState("student");
  const [error, setError]             = useState("");
  const [busy, setBusy]               = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      let session;
      if (mode === "signup") {
        if (password.length < 6) throw new Error("Password must be at least 6 characters.");
        session = await signup({ email, password, displayName, role });
      } else {
        session = await login({ email, password });
      }
      onLoggedIn(session);
    } catch (err) {
      setError(err?.message || "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-wrap">
      {/* Left panel – branding */}
      <div className="login-left">
        <div className="login-left-logo">OU IT</div>
        <h1 className="login-left-title">
          Your intelligent<br />IT support assistant
        </h1>
        <p className="login-left-sub">
          Instant answers from the Oakland University knowledge base,
          personalised to your role — available 24 / 7.
        </p>
        <div className="login-features">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.label}
              className="login-feature"
              initial={{ opacity: 0, x: -16 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08 + 0.3, duration: 0.35 }}
            >
              <div className="login-feature-icon">{f.icon}</div>
              <div>
                <div className="login-feature-label">{f.label}</div>
                <div className="login-feature-desc">{f.desc}</div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Right panel – form */}
      <div className="login-right">
        <motion.div
          className="login-card"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: "spring", stiffness: 260, damping: 26 }}
        >
          <div className="login-logo-mobile">OU IT Assistant</div>
          <h2 className="login-title">
            {mode === "signup" ? "Create account" : "Welcome back"}
          </h2>
          <p className="login-lead">
            {mode === "signup"
              ? "Sign up to get role-tailored IT support."
              : "Sign in to continue to your dashboard."}
          </p>

          <div className="login-toggle" role="tablist">
            {["login", "signup"].map((m) => (
              <button
                key={m}
                type="button"
                role="tab"
                aria-selected={mode === m}
                className={`login-tab${mode === m ? " active" : ""}`}
                onClick={() => { setMode(m); setError(""); }}
              >
                {m === "login" ? "Log in" : "Sign up"}
              </button>
            ))}
          </div>

          <form className="login-form" onSubmit={submit}>
            <AnimatePresence mode="wait">
              {mode === "signup" && (
                <motion.div
                  key="signup-fields"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.22 }}
                  style={{ overflow: "hidden" }}
                >
                  <div style={{ display: "flex", flexDirection: "column", gap: 13, paddingBottom: 4 }}>
                    <div className="login-field">
                      <label htmlFor="displayName">Display name</label>
                      <input
                        id="displayName"
                        value={displayName}
                        onChange={(e) => setDisplayName(e.target.value)}
                        autoComplete="name"
                        placeholder="Your full name"
                      />
                    </div>
                    <div className="login-field">
                      <label htmlFor="role">Your role at OU</label>
                      <select id="role" value={role} onChange={(e) => setRole(e.target.value)}>
                        {ROLES.map((r) => (
                          <option key={r.id} value={r.id}>{r.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            <div className="login-field">
              <label htmlFor="email">Email address</label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                placeholder="you@oakland.edu"
              />
            </div>
            <div className="login-field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "signup" ? "new-password" : "current-password"}
                placeholder="••••••••"
                minLength={mode === "signup" ? 6 : undefined}
              />
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  className="login-error"
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>

            <motion.button
              type="submit"
              className="login-submit"
              disabled={busy}
              whileHover={busy ? {} : { scale: 1.02 }}
              whileTap={busy ? {} : { scale: 0.98 }}
            >
              {busy
                ? "Please wait…"
                : mode === "signup"
                ? "Create account"
                : "Sign in"}
            </motion.button>
          </form>

          <p className="login-demo-note">
            Your account is securely stored and accessible from any device.<br />
            No data is sent to external identity providers.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
