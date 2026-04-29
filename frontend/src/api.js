/** Base URL for API + browser loads. Empty string = same origin (Vite proxy or nginx /api proxy). */
export function getApiOrigin() {
  const v = import.meta.env.VITE_API_BASE_URL;
  if (v === undefined || v === null || String(v).trim() === "") return "";
  return String(v).replace(/\/$/, "");
}

export function apiUrl(path) {
  const origin = getApiOrigin();
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${origin}${p}`;
}
