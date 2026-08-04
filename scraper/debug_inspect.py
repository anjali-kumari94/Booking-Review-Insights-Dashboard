"""
One-off diagnostic script. Run this against ONE property URL, then paste
the full console output back to Claude. It does NOT save reviews - it just
reports what's actually on the page so the real selectors/JSON keys can be
filled in correctly instead of guessed.

Run:
    python debug_inspect.py
"""
from playwright.sync_api import sync_playwright

URL = "https://www.booking.com/hotel/au/sydney-city-stay.html"  # Surry Hills

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        )
        page = context.new_page()

        json_hits = []

        def on_response(response):
            ctype = response.headers.get("content-type", "")
            if "review" in response.url.lower():
                json_hits.append((response.url, ctype, response.status))

        page.on("response", on_response)

        print(f"Navigating to {URL} ...")
        page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # The main hotel page only has the rating-summary widget - individual
        # reviews live behind this "read all reviews" control, confirmed via
        # a prior debug run (data-testid="review-score-read-all-actionable").
        clicked = False
        for selector in [
            '[data-testid="review-score-read-all-actionable"]',
            '[data-testid="review-score-read-all"]',
            'a:has-text("Guest reviews")',
            'a:has-text("Reviews")',
        ]:
            try:
                page.click(selector, timeout=3000)
                print(f"Clicked selector '{selector}'")
                clicked = True
                break
            except Exception:
                continue
        if not clicked:
            print("Could not click any reviews-entry selector - trying scroll instead.")
            page.mouse.wheel(0, 3000)

        page.wait_for_timeout(4000)

        # In case this opened a new tab rather than a modal/same-page panel.
        if len(context.pages) > 1:
            print(f"A new tab/page opened ({len(context.pages)} pages total) - switching to it.")
            page = context.pages[-1]
            page.on("response", on_response)
            page.wait_for_timeout(3000)

        print(f"\nCurrent page URL: {page.url}")

        print("\n=== Network responses with 'review' in the URL ===")
        if not json_hits:
            print("(none seen)")
        for url, ctype, status in json_hits[:20]:
            print(f"[{status}] {ctype} :: {url}")

        print("\n=== Searching rendered HTML for likely review markers ===")
        html = page.content()
        for marker in ['data-testid="review', 'class="review', 'itemprop="review',
                       'c-review', 'review-score-badge', 'review_item', 'review-item',
                       'reviewer', 'review-card', 'review_list', 'reviewlist',
                       'data-review-url', 'review_pos', 'review_neg']:
            count = html.count(marker)
            if count:
                print(f"Found {count}x occurrences of: {marker}")

        # Save full HTML for manual grep if needed.
        with open("page_dump.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("\nFull page HTML saved to scraper/page_dump.html")
        print("If nothing above matched, open that file and search for the word 'review' to find the real markup.")

        browser.close()

if __name__ == "__main__":
    main()
