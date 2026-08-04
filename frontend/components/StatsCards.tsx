type WeeklyStats = {
  this_week: { avg_rating: number | null; review_count: number };
  last_week: { avg_rating: number | null; review_count: number };
  delta: number | null;
};

export default function StatsCards({ stats }: { stats: WeeklyStats | null }) {
  if (!stats) return null;

  const deltaColor =
    stats.delta === null ? "text-slate-400" : stats.delta >= 0 ? "text-emerald-600" : "text-red-600";
  const deltaSign = stats.delta !== null && stats.delta > 0 ? "+" : "";

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <p className="text-sm text-slate-500">This week's average rating</p>
        <p className="text-3xl font-semibold mt-1">
          {stats.this_week.avg_rating ?? "—"} <span className="text-base font-normal text-slate-400">/10</span>
        </p>
        <p className="text-xs text-slate-400 mt-1">{stats.this_week.review_count} reviews</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <p className="text-sm text-slate-500">Last week's average rating</p>
        <p className="text-3xl font-semibold mt-1">
          {stats.last_week.avg_rating ?? "—"} <span className="text-base font-normal text-slate-400">/10</span>
        </p>
        <p className="text-xs text-slate-400 mt-1">{stats.last_week.review_count} reviews</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
        <p className="text-sm text-slate-500">Week-over-week change</p>
        <p className={`text-3xl font-semibold mt-1 ${deltaColor}`}>
          {stats.delta !== null ? `${deltaSign}${stats.delta}` : "—"}
        </p>
        <p className="text-xs text-slate-400 mt-1">vs. previous week</p>
      </div>
    </div>
  );
}
