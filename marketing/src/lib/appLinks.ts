// Same env-configurable-base-URL pattern frontend/src/api/client.ts already uses
// for its own backend URL — kept consistent across the two Vite projects.
const APP_URL = import.meta.env.VITE_APP_URL ?? "http://localhost:5174";

/** Build a URL into the real app (frontend/, dev default port 5174). */
export function appUrl(path: string = ""): string {
  return `${APP_URL}${path}`;
}
