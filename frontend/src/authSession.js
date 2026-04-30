import { apiUrl } from "./api";

const SESSION_KEY = "ou_chat_session_v2";
const _LEGACY_KEY  = "ou_chat_session_v1";

// Clear any leftover legacy localStorage auth on first load
if (typeof localStorage !== "undefined") {
  localStorage.removeItem(_LEGACY_KEY);
  localStorage.removeItem("ou_chat_accounts_v1");
}

export function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s?.token || !s?.email) return null;
    return s;
  } catch {
    return null;
  }
}

export function setSession(s) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(s));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

function _buildSession(data) {
  return {
    token: data.token,
    userId: data.user_id,
    email: data.email,
    displayName: data.display_name || data.email.split("@")[0],
    role: data.role || "all",
    isAdmin: !!data.is_admin,
  };
}

export async function signup({ email, password, displayName, role }) {
  const res = await fetch(apiUrl("/api/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName || "", role: role || "all" }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Sign-up failed.");
  const session = _buildSession(data);
  setSession(session);
  return session;
}

export async function login({ email, password }) {
  const res = await fetch(apiUrl("/api/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Login failed.");
  const session = _buildSession(data);
  setSession(session);
  return session;
}
