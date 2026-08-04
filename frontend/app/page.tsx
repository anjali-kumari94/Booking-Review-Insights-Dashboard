"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import StatsCards from "@/components/StatsCards";
import PropertyBreakdown from "@/components/PropertyBreakdown";
import ReviewFeed from "@/components/ReviewFeed";
import SentimentTrendChart from "@/components/SentimentTrendChart";
import TopicInsights from "@/components/TopicInsights";

export default function Dashboard() {
  const [properties, setProperties] = useState<string[]>([]);
  const [selectedProperty, setSelectedProperty] = useState<string>("");
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const [stats, setStats] = useState<any>(null);
  const [reviews, setReviews] = useState<any[]>([]);
  const [trend, setTrend] = useState<any[]>([]);
  const [topics, setTopics] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.properties().then(setProperties).catch(() => {});
  }, []);

  useEffect(() => {
    const propertyParam = selectedProperty || undefined;

    Promise.all([
      api.weeklyStats(propertyParam),
      api.reviews({ property: propertyParam, date_from: dateFrom || undefined, date_to: dateTo || undefined, limit: 100 }),
      api.sentimentTrend(propertyParam, 8),
      api.topicInsights(propertyParam, 1),
    ])
      .then(([statsRes, reviewsRes, trendRes, topicsRes]) => {
        setStats(statsRes);
        setReviews(reviewsRes);
        setTrend(trendRes);
        setTopics(topicsRes);
        setError(null);
      })
      .catch((e) => setError(String(e.message || e)));
  }, [selectedProperty, dateFrom, dateTo]);

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">Azzurro Hotels — Review Insights</h1>
        <p className="text-sm text-slate-500 mt-1">
          Guest sentiment and operational trends across all properties
        </p>
      </header>

      {error && (
        <div className="mb-4 text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          Couldn't reach the API ({error}). Is the backend running on port 8000?
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-6">
        <select
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white"
          value={selectedProperty}
          onChange={(e) => setSelectedProperty(e.target.value)}
        >
          <option value="">All properties</option>
          {properties.map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
        <input
          type="date"
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white"
          value={dateFrom}
          onChange={(e) => setDateFrom(e.target.value)}
        />
        <span className="self-center text-slate-400 text-sm">to</span>
        <input
          type="date"
          className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white"
          value={dateTo}
          onChange={(e) => setDateTo(e.target.value)}
        />
      </div>

      <div className="space-y-6">
        <StatsCards stats={stats} />

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PropertyBreakdown rows={stats?.per_property_this_week || []} />
          <TopicInsights
            totalNegative={topics?.total_negative_reviews || 0}
            topics={topics?.topics || []}
          />
        </div>

        <SentimentTrendChart data={trend} />

        <ReviewFeed reviews={reviews} />
      </div>
    </main>
  );
}
