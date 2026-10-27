// Base URL is empty by default (same origin / dev proxy). Set VITE_API_BASE for a separately hosted API.
const BASE = (import.meta.env?.VITE_API_BASE || "").replace(/\/$/, "");

export async function apiGet(path, params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") qs.set(k, v);
  const url = `${BASE}${path}${qs.toString() ? `?${qs}` : ""}`;
  let res;
  try {
    res = await fetch(url);
  } catch {
    throw new Error("Cannot reach the analysis API. Is the backend running?");
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* keep default */ }
    throw new Error(detail);
  }
  return res.json();
}
