/** Base URL for API + browser loads. Empty string = same origin (Vite proxy or nginx /api proxy). */

export function getApiOrigin() {
  const raw = import.meta.env.VITE_API_BASE_URL;

  if (raw === undefined || raw === null || String(raw).trim() === "") {
    return "";
  }

  let base = String(raw).trim().replace(/\/$/, "");

  // Align API hostname with the page hostname so dev works whether you open
  // http://localhost:5173 or http://127.0.0.1:5173 (avoids confusing CORS/preflight failures).
  if (typeof window !== "undefined") {
    try {
      const u = new URL(base);
      const pageHost = window.location.hostname;
      if (pageHost === "127.0.0.1" && u.hostname === "localhost") {
        u.hostname = "127.0.0.1";
        base = u.origin;
      } else if (pageHost === "localhost" && u.hostname === "127.0.0.1") {
        u.hostname = "localhost";
        base = u.origin;
      }
    } catch {
      /* keep base */
    }
  }

  return base;
}

export function apiUrl(path) {
  const origin = getApiOrigin();
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${origin}${p}`;
}
