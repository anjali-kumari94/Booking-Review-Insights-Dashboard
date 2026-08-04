type TopicRow = { topic: string; count: number; pct_of_negative: number };

export default function TopicInsights({
  totalNegative,
  topics,
}: {
  totalNegative: number;
  topics: TopicRow[];
}) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-600 mb-1">Operational insight topics</p>
      <p className="text-xs text-slate-400 mb-3">
        Based on {totalNegative} negative review{totalNegative === 1 ? "" : "s"} in the selected period
      </p>
      <div className="space-y-2">
        {topics.length === 0 && <p className="text-sm text-slate-400">No topic mentions found.</p>}
        {topics.map((t) => (
          <div key={t.topic}>
            <div className="flex justify-between text-sm mb-0.5">
              <span>{t.topic}</span>
              <span className="text-slate-500">
                {t.pct_of_negative}% ({t.count})
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2">
              <div
                className="bg-amber-500 h-2 rounded-full"
                style={{ width: `${Math.min(t.pct_of_negative, 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
