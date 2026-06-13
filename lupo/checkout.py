"""Open the real Vinted listings for the human to complete the purchase.

Lupo NEVER auto-buys. At the purchase-confirm gate we optionally open each chosen
listing's real Vinted page in the default browser, so the human reviews the actual
item and clicks "Buy now" / pays themselves. The agent's job ends at "here are the
exact items I chose"; the irreversible, money-spending step stays human.

Enable with LUPO_OPEN_LISTINGS=1. URLs are only opened if they are real http(s)
links (curated/live cache), so the offline replay demo never pops browser tabs.
"""
import os
import webbrowser


def _is_real(url):
    return isinstance(url, str) and url.startswith("http")


def open_listings(items, max_open=6):
    """Open up to max_open real listing URLs in the default browser.

    Returns the list of URLs actually opened (empty when disabled or all URLs are
    placeholder/offline fixtures)."""
    if os.getenv("LUPO_OPEN_LISTINGS", "0") != "1":
        return []
    urls = []
    for it in items:
        url = (it or {}).get("url", "")
        if _is_real(url) and url not in urls:
            urls.append(url)
    urls = urls[:max_open]
    for url in urls:
        try:
            webbrowser.open(url, new=2)  # new=2 -> new tab if possible
        except Exception as e:  # never let a browser hiccup break the mission
            print(f"[checkout] could not open {url}: {e}")
    return urls
