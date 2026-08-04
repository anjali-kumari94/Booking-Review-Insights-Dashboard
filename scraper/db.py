"""
Storage layer for scraped reviews.

Uses SQLite for zero-setup reliability during the trial window (no external
DB service to provision/auth against under a time limit). Swapping to
MongoDB/Postgres later is a small change since all access goes through this
module - see README "Production notes" for what that swap would involve.
"""
import hashlib
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "reviews.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    id TEXT PRIMARY KEY,              -- native booking.com review id, or a
                                       -- content hash fallback (see dedup_key)
    property TEXT NOT NULL,
    reviewer_name TEXT,
    reviewer_country TEXT,
    rating REAL,
    review_date TEXT,                 -- ISO date, as published on the page
    text_liked TEXT,
    text_disliked TEXT,
    raw_text TEXT,                    -- fallback: undivided review body
    scraped_at TEXT NOT NULL,
    source_url TEXT
);
CREATE INDEX IF NOT EXISTS idx_reviews_property ON reviews(property);
CREATE INDEX IF NOT EXISTS idx_reviews_date ON reviews(review_date);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT,                      -- 'success' | 'partial' | 'failed'
    reviews_found INTEGER DEFAULT 0,
    reviews_new INTEGER DEFAULT 0,
    error TEXT
);
"""


@dataclass
class Review:
    property: str
    reviewer_name: Optional[str]
    reviewer_country: Optional[str]
    rating: Optional[float]
    review_date: Optional[str]        # ISO 8601 string, e.g. "2026-07-30"
    text_liked: Optional[str] = None
    text_disliked: Optional[str] = None
    raw_text: Optional[str] = None
    native_id: Optional[str] = None   # booking.com's own review id, if found
    source_url: Optional[str] = None

    def dedup_key(self) -> str:
        """
        Prefer booking.com's own review id when we can extract it from the
        intercepted JSON (most reliable). Fall back to a content hash of
        property + reviewer + date + first 120 chars of text - stable across
        re-scrapes of the same review, resistant to minor whitespace diffs.
        """
        if self.native_id:
            return f"native:{self.native_id}"
        basis = "|".join([
            self.property or "",
            self.reviewer_name or "",
            self.review_date or "",
            (self.text_liked or self.text_disliked or self.raw_text or "")[:120],
        ])
        return "hash:" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert_review(review: Review) -> bool:
    """Insert a review if not already present. Returns True if newly inserted."""
    key = review.dedup_key()
    with get_conn() as conn:
        cur = conn.execute("SELECT 1 FROM reviews WHERE id = ?", (key,))
        if cur.fetchone():
            return False
        conn.execute(
            """INSERT INTO reviews
               (id, property, reviewer_name, reviewer_country, rating,
                review_date, text_liked, text_disliked, raw_text,
                scraped_at, source_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                key, review.property, review.reviewer_name,
                review.reviewer_country, review.rating, review.review_date,
                review.text_liked, review.text_disliked, review.raw_text,
                datetime.utcnow().isoformat(), review.source_url,
            ),
        )
        return True


def latest_review_date(property_name: str) -> Optional[str]:
    """Used by the scraper to stop paginating early once it reaches reviews
    it already has - this is what makes re-runs incremental rather than
    full re-scrapes."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT MAX(review_date) AS d FROM reviews WHERE property = ?",
            (property_name,),
        )
        row = cur.fetchone()
        return row["d"] if row else None


def log_run_start(property_name: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scrape_runs (property, started_at, status) VALUES (?, ?, ?)",
            (property_name, datetime.utcnow().isoformat(), "running"),
        )
        return cur.lastrowid


def log_run_end(run_id: int, status: str, reviews_found: int, reviews_new: int, error: str = None):
    with get_conn() as conn:
        conn.execute(
            """UPDATE scrape_runs
               SET finished_at = ?, status = ?, reviews_found = ?, reviews_new = ?, error = ?
               WHERE id = ?""",
            (datetime.utcnow().isoformat(), status, reviews_found, reviews_new, error, run_id),
        )
