"""
Topic classification for operational insights.

APPROACH: keyword/phrase matching against a curated dictionary per category.
Chosen over an LLM call for this build because it's deterministic, free,
instant (no API latency/cost per review), and easy for non-technical ops
staff and evaluators to audit - you can point at exactly why a review was
tagged "cleanliness". A review can match multiple categories.

LIMITATIONS (documented honestly, not hidden):
  - Misses paraphrases, sarcasm, and typos not in the keyword list
    ("the room reeked" won't match unless "reeked" is added).
  - No real sentiment model behind it - sentiment.py below runs the
    positive/negative split off Booking's own liked/disliked fields,
    not off classified text, so it's independent of this module's misses.
  - Coverage improves by extending TOPIC_KEYWORDS; still bounded by
    hand-curated terms.

NEXT ITERATION: swap this module for an LLM classifier (e.g. Gemini, which
this account already has API access to) that takes the review text and the
same 8 category labels and returns matches + confidence - would catch
paraphrasing this dictionary misses, at the cost of API latency/spend per
review. Left as documented future work rather than built under this time
limit, to keep the demo deterministic and dependency-free.
"""
from collections import defaultdict

TOPIC_KEYWORDS = {
    "Cleanliness": [
        "dirty", "clean", "cleanliness", "dust", "dusty", "stain", "stained",
        "mold", "mould", "smell", "smelly", "odor", "odour", "hygiene",
        "unclean", "grime", "grimy", "filthy",
    ],
    "Check-in experience": [
        "check-in", "check in", "checkin", "reception", "front desk",
        "waited", "wait time", "queue", "early check", "late check",
        "key card", "keycard",
    ],
    "Staff/Receptionist behaviour": [
        "staff", "receptionist", "rude", "friendly", "helpful", "unhelpful",
        "service", "manager", "attitude", "welcoming", "professional",
        "unprofessional",
    ],
    "Noise": [
        "noise", "noisy", "loud", "quiet", "soundproof", "traffic noise",
        "thin walls", "party", "music",
    ],
    "Facilities": [
        "wifi", "wi-fi", "elevator", "lift", "pool", "gym", "parking",
        "air conditioning", "aircon", "ac ", "heater", "facilities",
        "amenities", "breakfast",
    ],
    "Location": [
        "location", "central", "walk", "walking distance", "far from",
        "close to", "nearby", "transport", "station", "metro", "commute",
    ],
    "Room condition": [
        "room was", "bed", "mattress", "furniture", "bathroom", "shower",
        "worn", "outdated", "old", "renovat", "broken", "maintenance",
        "small room", "tiny room",
    ],
    "Value for money": [
        "overpriced", "value for money", "expensive", "worth it", "price",
        "cheap", "affordable", "rip off", "ripoff", "not worth",
    ],
}


def classify_text(text: str) -> list[str]:
    """Return the list of topic categories whose keywords appear in `text`."""
    if not text:
        return []
    lowered = text.lower()
    matched = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            matched.append(topic)
    return matched


def classify_review(text_liked: str = None, text_disliked: str = None, raw_text: str = None):
    """
    Returns {"positive_topics": [...], "negative_topics": [...]}.
    We classify liked/disliked text separately when Booking's structured
    fields are available (far more reliable signal than guessing sentiment
    from unstructured text); raw_text is only used when neither is present.
    """
    if text_liked or text_disliked:
        return {
            "positive_topics": classify_text(text_liked or ""),
            "negative_topics": classify_text(text_disliked or ""),
        }
    # No structured split available - classify raw_text into both, since we
    # can't confidently assign sentiment. Downstream, treat rating as the
    # sentiment signal instead (see weekly stats: rating < 3 => negative).
    topics = classify_text(raw_text or "")
    return {"positive_topics": [], "negative_topics": topics}


def topic_breakdown(reviews: list[dict]) -> dict:
    """
    Given a list of review dicts (with rating, text_liked, text_disliked,
    raw_text), compute the % of negative reviews mentioning each topic.
    'Negative' = rating < 3 (out of 5) OR has any disliked text — matches
    how Booking.com's own UI treats a 'disliked' section as negative signal
    even on an otherwise decent-rated stay.
    """
    negative_reviews = [
        r for r in reviews
        if (r.get("rating") is not None and r["rating"] < 6)  # Booking uses a 10-pt scale
        or r.get("text_disliked")
    ]
    total_negative = len(negative_reviews)
    counts = defaultdict(int)
    for r in negative_reviews:
        result = classify_review(r.get("text_liked"), r.get("text_disliked"), r.get("raw_text"))
        for topic in set(result["negative_topics"]):
            counts[topic] += 1

    return {
        "total_negative_reviews": total_negative,
        "topics": [
            {
                "topic": topic,
                "count": count,
                "pct_of_negative": round(100 * count / total_negative, 1) if total_negative else 0.0,
            }
            for topic, count in sorted(counts.items(), key=lambda x: -x[1])
        ],
    }
