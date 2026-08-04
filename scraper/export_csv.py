"""Exports all rows in reviews.db to a CSV, for the 'sample review data'
deliverable. Run after scraper.py (or seed_sample_data.py for a quick demo
export) to produce data/reviews_export.csv."""
import csv
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "reviews.db"
OUT_PATH = Path(__file__).parent.parent / "data" / "reviews_export.csv"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM reviews ORDER BY property, review_date DESC").fetchall()
conn.close()

if not rows:
    print("No reviews in the database yet — run scraper.py or seed_sample_data.py first.")
else:
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        for r in rows:
            writer.writerow(dict(r))
    print(f"Exported {len(rows)} reviews to {OUT_PATH}")
