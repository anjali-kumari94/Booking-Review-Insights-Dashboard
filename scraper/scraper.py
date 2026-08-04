"""
Booking.com review scraper for the Azzurro Hotels properties.

STRATEGY (in order of preference):
  1. Embedded state parsing (PRIMARY): Scans page <script> tags for Booking's
     inline Apollo GraphQL cache or embedded state JSON. Dynamically identifies
     review entities even if key names change.
  2. Network interception (fallback): Listens for XHR/fetch JSON responses from
     review and GraphQL endpoints during page load/interaction.
  3. HTML fallback (last resort): Parses rendered review cards using a flexible
     list of fallback CSS selectors.

Run:
    python scraper.py --all
    python scraper.py --property "Surry Hills"
"""
import argparse
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from db import Review, init_db, insert_review, latest_review_date, log_run_start, log_run_end

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("scraper")

PROPERTIES = {
    "Surry Hills": "https://www.booking.com/hotel/au/sydney-city-stay.html",
    "Potts Point": "https://www.booking.com/hotel/au/venus-potts-point-sydney.html",
    "Central Sydney": "https://www.booking.com/hotel/au/venus-surry-hills.html",
    "Darling Harbour": "https://www.booking.com/hotel/au/chateau-de-venus.html",
}

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5
NAV_TIMEOUT_MS = 30000

SCRIPT_TAG_RE = re.compile(r"<script[^>]*>(.*?)</script>", re.DOTALL)


def extract_apollo_reviews(html: str, property_name: str, source_url: str) -> list[Review]:
    """
    Scan every <script> block on the page for JSON payloads and dynamically 
    extract review objects, handling both classic and updated Booking.com Apollo schemas.
    """
    reviews = []
    for match in SCRIPT_TAG_RE.finditer(html):
        body = match.group(1).strip()
        if not body.startswith("{"):
            continue

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        for key, value in data.items():
            if not isinstance(value, dict):
                continue

            # Flexible key/property matching to catch schema updates
            is_review_key = any(key.startswith(prefix) for prefix in ("FeaturedReview:", "Review:", "PropertyReview:"))
            has_review_fields = ("guestName" in value or "averageScore" in value or "positiveText" in value or "negativeText" in value)

            if is_review_key or has_review_fields:
                completed = value.get("completed")
                review_date = None
                if completed:
                    try:
                        review_date = datetime.fromtimestamp(int(completed), tz=timezone.utc).date().isoformat()
                    except (ValueError, OSError, TypeError):
                        review_date = None

                rating_val = value.get("averageScore") or value.get("score") or value.get("rating")

                reviews.append(Review(
                    property=property_name,
                    reviewer_name=value.get("guestName") or value.get("author"),
                    reviewer_country=(value.get("guestCountryCode") or value.get("countryCode") or "").upper() or None,
                    rating=float(rating_val) if rating_val is not None else None,
                    review_date=review_date,
                    text_liked=value.get("positiveText") or value.get("pros") or None,
                    text_disliked=value.get("negativeText") or value.get("cons") or None,
                    raw_text=value.get("text") or value.get("comment") or None,
                    native_id=str(value.get("id")) if value.get("id") is not None else None,
                    source_url=source_url,
                ))

        if reviews:
            break  # Stop searching once the target state block is found

    return reviews


def _parse_json_review_payload(payload: dict, property_name: str, source_url: str) -> list[Review]:
    """
    Pull review objects out of dynamic XHR/fetch JSON responses or GraphQL payloads.
    """
    if not isinstance(payload, dict):
        return []

    candidates = None
    search_nodes = [payload]

    # Handle GraphQL nested structures like payload['data']['property']['reviewList']
    if "data" in payload and isinstance(payload["data"], dict):
        search_nodes.append(payload["data"])
        for val in payload["data"].values():
            if isinstance(val, dict):
                search_nodes.append(val)

    for node in search_nodes:
        for key in ("reviews", "results", "reviewList", "reviewsList", "items", "actionReviews"):
            if key in node and isinstance(node[key], list):
                candidates = node[key]
                break
        if candidates:
            break

    if not candidates:
        return []

    out = []
    for item in candidates:
        if not isinstance(item, dict):
            continue

        rating = item.get("rating") or item.get("average_score") or item.get("score") or item.get("averageScore")
        date_raw = item.get("date") or item.get("review_date") or item.get("checkout_date") or item.get("completed")
        review_id = item.get("id") or item.get("review_id") or item.get("reviewId")
        liked = item.get("positive_text") or item.get("liked") or item.get("pros") or item.get("positiveText")
        disliked = item.get("negative_text") or item.get("disliked") or item.get("cons") or item.get("negativeText")
        reviewer = item.get("reviewer_name") or item.get("author") or item.get("guest_name") or item.get("guestName")
        country = item.get("country") or item.get("reviewer_country") or item.get("guestCountryCode")

        out.append(Review(
            property=property_name,
            reviewer_name=reviewer,
            reviewer_country=str(country).upper() if country else None,
            rating=float(rating) if rating not in (None, "") else None,
            review_date=_normalize_date(date_raw),
            text_liked=liked,
            text_disliked=disliked,
            raw_text=None if (liked or disliked) else item.get("text") or item.get("comment"),
            native_id=str(review_id) if review_id is not None else None,
            source_url=source_url,
        ))
    return out


def _normalize_date(raw) -> Optional[str]:
    if not raw:
        return None
    
    # Handle unix timestamps
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and raw.isdigit()):
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).date().isoformat()
        except (ValueError, OSError):
            pass

    raw = str(raw)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d %B %Y"):
        try:
            return datetime.strptime(raw[:19] if "T" in raw else raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


def scrape_property_html_fallback(page, property_name: str, url: str) -> list[Review]:
    """
    HTML fallback path utilizing multiple potential DOM selectors.
    """
    reviews = []
    candidate_card_selectors = [
        '[data-testid="review-card"]',
        '[data-testid="review-sub-item"]',
        'li.review_list_new_item_block',
        '.review_card',
        'div[c-review-card]',
        '[data-review-id]'
    ]

    active_selector = None
    for selector in candidate_card_selectors:
        if page.query_selector(selector):
            active_selector = selector
            break

    if not active_selector:
        log.warning(f"[{property_name}] No review cards found with known HTML selectors.")
        return reviews

    cards = page.query_selector_all(active_selector)
    for card in cards:
        try:
            reviewer = _text_or_none(card, '[data-testid="review-author-name"], .bui-avatar-block__title, .review-author')
            country = _text_or_none(card, '[data-testid="review-author-country"], .bui-avatar-block__subtitle, .review-country')
            rating_txt = _text_or_none(card, '[data-testid="review-score"], .bui-review-score__badge, .review-score')
            date_txt = _text_or_none(card, '[data-testid="review-date"], .c-review-block__date, .review-date')
            liked = _text_or_none(card, '[data-testid="review-positive-text"], .c-review__inner--pro, .review-liked')
            disliked = _text_or_none(card, '[data-testid="review-negative-text"], .c-review__inner--con, .review-disliked')

            rating = None
            if rating_txt:
                try:
                    rating = float(rating_txt.strip().split()[0].replace(",", "."))
                except ValueError:
                    pass

            reviews.append(Review(
                property=property_name,
                reviewer_name=reviewer,
                reviewer_country=country,
                rating=rating,
                review_date=_normalize_date(date_txt.replace("Reviewed:", "").strip() if date_txt else None),
                text_liked=liked,
                text_disliked=disliked,
                raw_text=None if (liked or disliked) else _text_or_none(card, '[data-testid="review-text"], .c-review__body'),
                native_id=None,
                source_url=url,
            ))
        except Exception as e:
            log.warning(f"[{property_name}] Skipped one malformed review card: {e}")
            continue

    return reviews


def _text_or_none(card, selector) -> Optional[str]:
    el = card.query_selector(selector)
    return el.inner_text().strip() if el else None


def scrape_property(playwright, property_name: str, url: str) -> tuple[int, int]:
    """Scrape a single property. Returns (found_count, new_count)."""
    run_id = log_run_start(property_name)
    intercepted_reviews: list[Review] = []
    found = new = 0

    for attempt in range(1, MAX_RETRIES + 1):
        browser = None
        try:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            page = context.new_page()

            def on_response(response):
                url_lower = response.url.lower()
                content_type = response.headers.get("content-type") or ""
                
                # Check for either 'review' or generic 'graphql' API calls
                if ("review" in url_lower or "graphql" in url_lower) and "json" in content_type:
                    try:
                        payload = response.json()
                        parsed = _parse_json_review_payload(payload, property_name, url)
                        if parsed:
                            intercepted_reviews.extend(parsed)
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(url, timeout=NAV_TIMEOUT_MS, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            # Strategy 1: Parse embedded Apollo JSON state
            html = page.content()
            reviews = extract_apollo_reviews(html, property_name, url)

            if reviews:
                log.info(f"[{property_name}] Found {len(reviews)} reviews in embedded page state.")
            else:
                log.info(f"[{property_name}] No embedded reviews found, trying click-through + network interception.")
                try:
                    page.click('a:has-text("Guest reviews")', timeout=5000)
                    page.wait_for_timeout(3000)
                except PWTimeout:
                    pass
                reviews = intercepted_reviews

                # Strategy 3: HTML fallback
                if not reviews:
                    log.info(f"[{property_name}] No JSON reviews intercepted either, trying HTML fallback.")
                    reviews = scrape_property_html_fallback(page, property_name, url)

            found = len(reviews)
            for r in reviews:
                if insert_review(r):
                    new += 1

            log_run_end(run_id, "success", found, new)
            browser.close()
            return found, new

        except Exception as e:
            log.error(f"[{property_name}] Attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            else:
                log_run_end(run_id, "failed", found, new, error=str(e))
                return found, new

    return found, new


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Scrape all four properties")
    parser.add_argument("--property", type=str, help="Scrape a single property by name")
    args = parser.parse_args()

    init_db()

    targets = PROPERTIES if args.all or not args.property else {args.property: PROPERTIES.get(args.property)}
    if args.property and not PROPERTIES.get(args.property):
        log.error(f"Unknown property '{args.property}'. Options: {list(PROPERTIES.keys())}")
        sys.exit(1)

    with sync_playwright() as p:
        summary = {}
        for name, url in targets.items():
            log.info(f"Scraping {name} ...")
            found, new = scrape_property(p, name, url)
            summary[name] = {"found": found, "new": new}
            log.info(f"[{name}] found={found} new={new}")

    log.info("Run summary: " + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()