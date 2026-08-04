"""
Seeds the local SQLite DB with synthetic sample reviews so the dashboard
and insights pipeline can be exercised end-to-end immediately, independent
of getting the live scraper's selectors verified.

This is clearly-labeled placeholder data for wiring/demo purposes only -
NOT a substitute for the "sample review data collected from the listed
properties" deliverable, which must come from an actual scraper run
against the real pages. Run scraper.py against live pages before
submitting, and keep (or replace) this seed data accordingly.

Run: python seed_sample_data.py
"""
import random
from datetime import date, timedelta

from db import Review, init_db, insert_review

PROPERTIES = ["Surry Hills", "Potts Point", "Central Sydney", "Darling Harbour"]

POSITIVE_SNIPPETS = [
    "Staff were incredibly friendly and check-in was quick.",
    "Room was spotless and the bed was very comfortable.",
    "Great location, walking distance to everything we needed.",
    "Excellent value for money compared to nearby hotels.",
    "Wifi was fast and the breakfast spread was generous.",
]
NEGATIVE_SNIPPETS = [
    "Room smelled musty and the bathroom wasn't very clean.",
    "Check-in took over 40 minutes, receptionist seemed overwhelmed.",
    "Very noisy at night, could hear traffic through thin walls.",
    "Air conditioning was broken and maintenance never came.",
    "Overpriced for what you get, room was smaller than expected.",
    "Front desk staff were rude when we asked about late checkout.",
]
COUNTRIES = ["Australia", "United States", "United Kingdom", "Singapore", "New Zealand", "Japan"]


def seed(n_per_property: int = 25):
    init_db()
    today = date.today()
    inserted = 0
    for prop in PROPERTIES:
        for i in range(n_per_property):
            days_ago = random.randint(0, 56)  # spread across ~8 weeks for trend chart
            review_date = today - timedelta(days=days_ago)
            is_negative = random.random() < 0.35
            rating = round(random.uniform(3.0, 6.5) if is_negative else random.uniform(7.0, 10.0), 1)

            liked = random.choice(POSITIVE_SNIPPETS) if random.random() < 0.7 else None
            disliked = random.choice(NEGATIVE_SNIPPETS) if is_negative or random.random() < 0.25 else None

            r = Review(
                property=prop,
                reviewer_name=f"Guest{random.randint(100, 999)}",
                reviewer_country=random.choice(COUNTRIES),
                rating=rating,
                review_date=review_date.isoformat(),
                text_liked=liked,
                text_disliked=disliked,
                native_id=f"seed-{prop}-{i}",
                source_url=None,
            )
            if insert_review(r):
                inserted += 1
    print(f"Seeded {inserted} sample reviews across {len(PROPERTIES)} properties.")


if __name__ == "__main__":
    seed()
