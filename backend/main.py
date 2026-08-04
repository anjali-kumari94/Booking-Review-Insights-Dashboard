"""
FastAPI backend for the Azzurro Hotels review dashboard.

Thin aggregation layer over the SQLite DB the scraper writes to. No ORM -
the dataset is small enough (a handful of properties' worth of reviews)
that raw SQL keeps this fast to build and easy to audit under a time limit.
"""
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).parent.parent / "scraper"))
from insights import topic_breakdown  # noqa: E402

DB_PATH = Path(__file__).parent.parent / "data" / "reviews.db"

app = FastAPI(title="Azzurro Hotels Review Insights API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # trial/demo scope only - restrict to the dashboard's
                           # origin before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def _row_to_dict(row) -> dict:
    return dict(row)


@app.get("/api/properties")
def list_properties():
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT property FROM reviews ORDER BY property").fetchall()
    return [r["property"] for r in rows]


@app.get("/api/reviews")
def get_reviews(
    property: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_rating: Optional[float] = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
):
    query = "SELECT * FROM reviews WHERE 1=1"
    params = []
    if property:
        query += " AND property = ?"
        params.append(property)
    if date_from:
        query += " AND review_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND review_date <= ?"
        params.append(date_to)
    if min_rating is not None:
        query += " AND rating >= ?"
        params.append(min_rating)
    if max_rating is not None:
        query += " AND rating <= ?"
        params.append(max_rating)
    query += " ORDER BY review_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def _week_bounds(offset_weeks: int = 0):
    """Return (start_iso, end_iso) for the ISO week `offset_weeks` back from
    the current week (0 = this week, 1 = last week)."""
    today = date.today()
    start_of_this_week = today - timedelta(days=today.weekday())
    start = start_of_this_week - timedelta(weeks=offset_weeks)
    end = start + timedelta(days=6)
    return start.isoformat(), end.isoformat()


def _avg_rating_for_range(conn, start: str, end: str, property: Optional[str] = None):
    query = "SELECT AVG(rating) AS avg_rating, COUNT(*) AS n FROM reviews WHERE review_date BETWEEN ? AND ?"
    params = [start, end]
    if property:
        query += " AND property = ?"
        params.append(property)
    row = conn.execute(query, params).fetchone()
    return row["avg_rating"], row["n"]


@app.get("/api/stats/weekly")
def weekly_stats(property: Optional[str] = None):
    this_start, this_end = _week_bounds(0)
    last_start, last_end = _week_bounds(1)

    with get_conn() as conn:
        this_avg, this_n = _avg_rating_for_range(conn, this_start, this_end, property)
        last_avg, last_n = _avg_rating_for_range(conn, last_start, last_end, property)

        properties = [r["property"] for r in conn.execute(
            "SELECT DISTINCT property FROM reviews"
        ).fetchall()]
        per_property = []
        for p in properties:
            avg, n = _avg_rating_for_range(conn, this_start, this_end, p)
            per_property.append({"property": p, "avg_rating": round(avg, 2) if avg else None, "review_count": n})

    delta = None
    if this_avg is not None and last_avg is not None:
        delta = round(this_avg - last_avg, 2)

    return {
        "this_week": {"start": this_start, "end": this_end,
                       "avg_rating": round(this_avg, 2) if this_avg else None, "review_count": this_n},
        "last_week": {"start": last_start, "end": last_end,
                       "avg_rating": round(last_avg, 2) if last_avg else None, "review_count": last_n},
        "delta": delta,
        "per_property_this_week": per_property,
    }


@app.get("/api/insights/topics")
def insights_topics(property: Optional[str] = None, weeks: int = 1):
    """Topic breakdown of negative reviews over the last `weeks` week(s)."""
    start, _ = _week_bounds(weeks - 1)
    _, end = _week_bounds(0)

    query = "SELECT rating, text_liked, text_disliked, raw_text FROM reviews WHERE review_date BETWEEN ? AND ?"
    params = [start, end]
    if property:
        query += " AND property = ?"
        params.append(property)

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    return topic_breakdown([_row_to_dict(r) for r in rows])


@app.get("/api/trends/sentiment")
def sentiment_trend(property: Optional[str] = None, weeks: int = 8):
    """Weekly count of positive (rating >= 6/10) vs negative (rating < 6/10)
    reviews over the last `weeks` weeks, for the trend chart."""
    trend = []
    with get_conn() as conn:
        for w in range(weeks - 1, -1, -1):
            start, end = _week_bounds(w)
            query = "SELECT rating FROM reviews WHERE review_date BETWEEN ? AND ?"
            params = [start, end]
            if property:
                query += " AND property = ?"
                params.append(property)
            rows = conn.execute(query, params).fetchall()
            positive = sum(1 for r in rows if r["rating"] is not None and r["rating"] >= 6)
            negative = sum(1 for r in rows if r["rating"] is not None and r["rating"] < 6)
            trend.append({"week_start": start, "positive": positive, "negative": negative})
    return trend


@app.get("/api/health")
def health():
    return {"status": "ok"}
