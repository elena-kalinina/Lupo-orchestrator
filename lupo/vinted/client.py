"""Vinted search client with record/replay.

Vinted has no public API. The real path (your vinted_agent repo) obtains a short-lived
`access_token_web` from the site's cookies, then calls /api/v2/catalog/items. That
token expires fast and Cloudflare/rate-limits are demo killers — so:

  - DEFAULT (replay): read cached fixtures from data/vinted_cache/. Fast, offline,
    deterministic. Real listings, real prices, real photos — captured during prep.
  - LIVE (record):    LUPO_VINTED_LIVE=1 -> call the real client, cache the result.

This is the same record-and-replay discipline as Lupo's pre-baked demo metrics.
"""
import json
import os
import re
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "vinted_cache"


def _slug(query):
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60]


def search(query, max_price=None, limit=8):
    """Return list of listings: {id, title, price, size, brand, seller_id, photo, url}."""
    if os.getenv("LUPO_VINTED_LIVE", "0") == "1":
        items = _search_live(query, limit)
        _cache_write(query, items)
    else:
        items = _cache_read(query)
    if max_price is not None:
        items = [it for it in items if it["price"] <= max_price]
    return items[:limit]


def _cache_read(query):
    path = CACHE_DIR / f"{_slug(query)}.json"
    if not path.exists():
        # graceful: empty result rather than crash, so the pipeline still runs
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_write(query, items):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{_slug(query)}.json").write_text(json.dumps(items, indent=2), encoding="utf-8")


_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _headers():
    """Build Vinted auth headers from env. Cookie is required; Bearer is optional
    (paste it only if the catalog endpoint 401s with cookie-only)."""
    cookie = os.getenv("VINTED_SESSION_COOKIE", "").strip()
    bearer = os.getenv("VINTED_BEARER_TOKEN", "").strip()
    headers = {"User-Agent": _UA}
    if cookie:
        # Accept either the bare value or a full "_vinted_fr_session=..." string.
        headers["Cookie"] = cookie if "=" in cookie else f"_vinted_fr_session={cookie}"
    if bearer:
        headers["Authorization"] = bearer if bearer.lower().startswith("bearer ") else f"Bearer {bearer}"
    return headers


def _map_item(item):
    """Map one Vinted catalog item to Lupo's listing dict shape."""
    price = item.get("price")
    if isinstance(price, dict):
        price = price.get("amount")
    try:
        price = round(float(price), 2)
    except (TypeError, ValueError):
        price = 0.0

    photo = ""
    photos = item.get("photos") or []
    if photos and isinstance(photos[0], dict):
        photo = photos[0].get("url", "")
    if not photo and isinstance(item.get("photo"), dict):
        photo = item["photo"].get("url", "")

    user = item.get("user") or {}
    return {
        "id": str(item.get("id", "")),
        "title": item.get("title", ""),
        "desc": item.get("description") or item.get("title", ""),
        "price": price,
        "size": item.get("size_title", ""),
        "brand": item.get("brand_title", ""),
        "seller_id": str(user.get("id", "")),
        "photo": photo,
        "country": "",  # not in the catalog list response; graft_photos keeps curated country
        "url": item.get("url", ""),
    }


def _search_live(query, limit):
    """Live Vinted search via the vinted_agent token-hack: curl_cffi with a Chrome
    TLS fingerprint + the session cookie (and optional Bearer) from env. Returns the
    mapped listing dicts, or [] on any error so the caller falls back to cache."""
    try:
        from curl_cffi import requests as cffi_requests
    except Exception as e:
        print(f"[vinted] curl_cffi not installed ({e}); cannot do live search.")
        return []

    domain = os.getenv("VINTED_DOMAIN", "fr").strip() or "fr"
    url = f"https://www.vinted.{domain}/api/v2/catalog/items"
    params = {"search_text": query, "page": 1, "per_page": max(1, int(limit))}
    try:
        resp = cffi_requests.get(url, headers=_headers(), params=params,
                                 impersonate="chrome120", timeout=20)
    except Exception as e:
        print(f"[vinted] live request failed for {query!r}: {e}")
        return []

    if resp.status_code in (401, 403):
        print(f"[vinted] {resp.status_code} for {query!r} — refresh VINTED_SESSION_COOKIE "
              f"(and add VINTED_BEARER_TOKEN if needed).")
        return []
    if resp.status_code != 200:
        print(f"[vinted] HTTP {resp.status_code} for {query!r}: {resp.text[:200]}")
        return []

    try:
        items = resp.json().get("items", [])
    except Exception as e:
        print(f"[vinted] bad JSON for {query!r}: {e}")
        return []
    return [_map_item(it) for it in items]
