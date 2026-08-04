type Review = {
  id: string;
  property: string;
  reviewer_name: string | null;
  reviewer_country: string | null;
  rating: number | null;
  review_date: string | null;
  text_liked: string | null;
  text_disliked: string | null;
  raw_text: string | null;
};

export default function ReviewFeed({ reviews }: { reviews: Review[] }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-600 mb-3">Review feed</p>
      <div className="space-y-3 max-h-[500px] overflow-y-auto pr-1">
        {reviews.length === 0 && <p className="text-sm text-slate-400">No reviews match the current filters.</p>}
        {reviews.map((r) => (
          <div key={r.id} className="border border-slate-100 rounded-lg p-3">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{r.property}</span>
              <span className="text-slate-400">{r.review_date}</span>
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400 mt-0.5">
              <span>{r.reviewer_name || "Guest"}{r.reviewer_country ? ` · ${r.reviewer_country}` : ""}</span>
              {r.rating !== null && (
                <span className="ml-auto bg-slate-100 rounded px-1.5 py-0.5 font-semibold text-slate-700">
                  {r.rating}/10
                </span>
              )}
            </div>
            {r.text_liked && (
              <p className="text-sm text-emerald-700 mt-2">
                <span className="font-medium">Liked: </span>
                {r.text_liked}
              </p>
            )}
            {r.text_disliked && (
              <p className="text-sm text-red-700 mt-1">
                <span className="font-medium">Disliked: </span>
                {r.text_disliked}
              </p>
            )}
            {!r.text_liked && !r.text_disliked && r.raw_text && (
              <p className="text-sm text-slate-600 mt-2">{r.raw_text}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
