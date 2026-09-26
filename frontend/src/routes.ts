import type { View } from "./App";

const viewPaths: Record<View, string> = {
  command: "/",
  search: "/search",
  network: "/network",
  timeline: "/timeline",
  geo: "/geo",
  evidence: "/evidence",
  review: "/review",
  cases: "/cases",
  reports: "/reports",
  audit: "/audit",
  users: "/users",
  "camera-cameras": "/admin/cameras",
  "camera-monitoring": "/monitoring",
  "camera-review": "/monitoring/review",
  "camera-event": "/monitoring/review",
};

export function viewToPath(view: View): string {
  return viewPaths[view] ?? "/";
}

export function pathToView(pathname: string): { view: View; eventId: string | null } {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  const eventMatch = normalized.match(/^\/monitoring\/events\/([A-Za-z0-9-]+)$/);
  if (eventMatch) return { view: "camera-event", eventId: eventMatch[1] };
  if (normalized === "/admin/cameras") return { view: "camera-cameras", eventId: null };
  if (normalized === "/monitoring") return { view: "camera-monitoring", eventId: null };
  if (normalized === "/monitoring/review") return { view: "camera-review", eventId: null };
  const entry = (Object.entries(viewPaths) as Array<[View, string]>).find(([, value]) => value === normalized);
  return { view: entry ? entry[0] : "command", eventId: null };
}
