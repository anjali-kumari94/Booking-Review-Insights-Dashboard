const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

async function get(path: string, params: Record<string, string | number | undefined> = {}) {
  const query = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
    .join("&");
  const url = `${API_BASE}${path}${query ? `?${query}` : ""}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`Request to ${url} failed: ${res.status}`);
  return res.json();
}

export const api = {
  properties: () => get("/api/properties"),
  reviews: (params: Record<string, string | number | undefined>) => get("/api/reviews", params),
  weeklyStats: (property?: string) => get("/api/stats/weekly", { property }),
  topicInsights: (property?: string, weeks = 1) => get("/api/insights/topics", { property, weeks }),
  sentimentTrend: (property?: string, weeks = 8) => get("/api/trends/sentiment", { property, weeks }),
};
