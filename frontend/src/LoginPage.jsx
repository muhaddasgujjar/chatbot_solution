import { useState } from "react";
import { login, signup } from "./authSession";

const ROLES = [
  { id: "student", label: "Student" },
  { id: "faculty", label: "Faculty" },
  { id: "alumni", label: "Alumni" },
];

export function LoginPage({ onLoggedIn }) {
  const [mode, setMode] = useState("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("student");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      let session;
      if (mode === "signup") {
        if (password.length < 6) throw new Error("Password must be at least 6 characters.");
        session = signup({ email, password, displayName, role });
      } else {
        session = login({ email, password });
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
      <div className="login-card">
        <h1 className="login-title">OU IT Assistant</h1>
        <p className="login-lead">Sign in to open your dashboard and chat tailored to your role.</p>

        <div className="login-toggle" role="tablist">
          <button
            type="button"
            className={mode === "signup" ? "login-tab active" : "login-tab"}
            onClick={() => setMode("signup")}
          >
            Sign up
          </button>
          <button
            type="button"
            className={mode === "login" ? "login-tab active" : "login-tab"}
            onClick={() => setMode("login")}
          >
            Log in
          </button>
        </div>

        <form className="login-form" onSubmit={submit}>
          {mode === "signup" && (
            <>
              <label className="login-field">
                <span>Display name</span>
                <input
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  autoComplete="name"
                  placeholder="Your name"
                />
              </label>
              <label className="login-field">
                <span>Role</span>
                <select value={role} onChange={(e) => setRole(e.target.value)}>
                  {ROLES.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          <label className="login-field">
            <span>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@oakland.edu"
            />
          </label>
          <label className="login-field">
            <span>Password</span>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              placeholder="••••••••"
              minLength={mode === "signup" ? 6 : undefined}
            />
          </label>

          {error && <p className="login-error">{error}</p>}

          <button type="submit" className="login-submit" disabled={busy}>
            {busy ? "Please wait…" : mode === "signup" ? "Create account" : "Log in"}
          </button>
        </form>

        <p className="login-demo-note">
          Demo accounts are stored only in this browser (localStorage). Use a strong password in real
          deployments.
        </p>
      </div>
    </div>
  );
}
