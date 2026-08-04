type PropertyRow = { property: string; avg_rating: number | null; review_count: number };

export default function PropertyBreakdown({ rows }: { rows: PropertyRow[] }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-600 mb-3">Property-by-property (this week)</p>
      <div className="space-y-2">
        {rows.length === 0 && <p className="text-sm text-slate-400">No reviews this week yet.</p>}
        {rows.map((r) => (
          <div key={r.property} className="flex items-center justify-between text-sm">
            <span className="text-slate-700">{r.property}</span>
            <div className="flex items-center gap-3">
              <span className="text-slate-400">{r.review_count} reviews</span>
              <span className="font-semibold w-12 text-right">
                {r.avg_rating ?? "—"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
