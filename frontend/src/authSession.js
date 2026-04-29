const SESSION_KEY = "ou_chat_session_v1";
const ACCOUNTS_KEY = "ou_chat_accounts_v1";

function hashPw(pw) {
  return btoa(unescape(encodeURIComponent(`${pw}::ou_demo_salt`)));
}

export function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s?.email || !s?.role) return null;
    if (!s.userId) {
      s.userId = emailKey(s.email).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "user";
    }
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

function loadAccounts() {
  try {
    return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveAccounts(acc) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(acc));
}

function emailKey(email) {
  return email.trim().toLowerCase();
}

function userIdFromEmail(email) {
  const k = emailKey(email).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  return k || "user";
}

export function signup({ email, password, displayName, role }) {
  const accounts = loadAccounts();
  const key = emailKey(email);
  if (!key) throw new Error("Enter a valid email.");
  if (accounts[key]) throw new Error("An account with this email already exists.");
  const row = {
    passwordHash: hashPw(password),
    role,
    displayName: (displayName || "").trim() || key.split("@")[0],
    userId: userIdFromEmail(email),
  };
  accounts[key] = row;
  saveAccounts(accounts);
  return finalizeSession(key, row);
}

export function login({ email, password }) {
  const accounts = loadAccounts();
  const key = emailKey(email);
  const row = accounts[key];
  if (!row || row.passwordHash !== hashPw(password)) {
    throw new Error("Invalid email or password.");
  }
  return finalizeSession(key, row);
}

function finalizeSession(email, row) {
  const session = {
    email,
    userId: row.userId,
    displayName: row.displayName,
    role: row.role,
  };
  setSession(session);
  return session;
}
