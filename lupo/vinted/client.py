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
import random
import re
import threading
import time
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "vinted_cache"


def _slug(query):
    return re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:60]


def search(query, max_price=None, limit=8, catalog_ids=None, size_tokens=None):
    """Return list of listings: {id, title, price, size, brand, seller_id, photo, url}.

    Replay (default): read curated fixtures from data/vinted_cache/.
    Live (LUPO_VINTED_LIVE=1): hit the real Vinted API (throttled) and, unless
    LUPO_VINTED_RECORD=0, write the raw result back to the cache.

    catalog_ids: list of Vinted catalog ids to scope the search (e.g. women's
        dresses=10, footwear=16) — applied server-side, live only.
    size_tokens: keep only listings whose size_title contains one of these tokens
        (e.g. ["M", "38"] for women's M / ["38"] for shoe size 38) — applied
        client-side on the live results, since the list response has no size_id."""
    if os.getenv("LUPO_VINTED_LIVE", "0") == "1":
        items = _search_live(query, limit, catalog_ids=catalog_ids)
        if size_tokens:
            items = [it for it in items if _size_match(it.get("size", ""), size_tokens)]
        if items and os.getenv("LUPO_VINTED_RECORD", "1") == "1":
            _cache_write(query, items)
    else:
        items = _cache_read(query)
    if max_price is not None:
        items = [it for it in items if it["price"] <= max_price]
    return items[:limit]


def _size_match(size_title, tokens):
    """True if any token equals one of the slash/space-separated parts of the
    Vinted size string. e.g. 'M / 38 / 10' -> {M, 38, 10}."""
    parts = {p.upper() for p in re.split(r"[\s/]+", str(size_title or "")) if p}
    return any(str(t).upper() in parts for t in tokens)


def _cache_read(query):
    path = CACHE_DIR / f"{_slug(query)}.json"
    if not path.exists():
        # The exact-slug fast path misses whenever the query is phrased differently
        # than when it was cached — e.g. when USE_REAL_GEMINI rewrites the palette and
        # per-slot style tags. Fall back to the cached file that shares the most query
        # tokens (the component name is always one of them), so replay still works with
        # a live-LLM spec. Returns [] only if nothing overlaps at all.
        path = _best_cache_match(query)
        if path is None:
            return []
    return json.loads(path.read_text(encoding="utf-8"))


def _best_cache_match(query):
    """Pick the cached fixture whose slug shares the most tokens with `query`."""
    if not CACHE_DIR.is_dir():
        return None
    q_tokens = set(_slug(query).split("_"))
    best, best_score = None, 0
    for f in CACHE_DIR.glob("*.json"):
        score = len(q_tokens & set(f.stem.split("_")))
        if score > best_score:
            best, best_score = f, score
    return best


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
    ua = os.getenv("VINTED_USER_AGENT", "").strip() or _UA
    domain = os.getenv("VINTED_DOMAIN", "fr").strip() or "fr"
    headers = {
        "User-Agent": ua,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Referer": f"https://www.vinted.{domain}/",
        "X-Requested-With": "XMLHttpRequest",
    }
    if cookie:
        # Accept either the bare value or a full "_vinted_fr_session=..." string.
        headers["Cookie"] = cookie if "=" in cookie else f"_vinted_fr_session={cookie}"
    if bearer:
        headers["Authorization"] = bearer if bearer.lower().startswith("bearer ") else f"Bearer {bearer}"
    return headers


# One persistent curl_cffi Session with a Chrome TLS fingerprint, exactly like the
# vinted_agent token-hack:  session = requests.Session(impersonate="chrome120").
# Reusing the session keeps cookies warm and looks far less bot-like than a fresh
# connection per query.
_session = None
_session_lock = threading.Lock()
_last_request_ts = 0.0
_throttle_lock = threading.Lock()


def _get_session():
    global _session
    with _session_lock:
        if _session is None:
            from curl_cffi import requests as cffi_requests
            _session = cffi_requests.Session(impersonate="chrome120")
            _session.headers.update(_headers())
        return _session


def reset_session():
    """Drop the cached session (e.g. after editing .env credentials)."""
    global _session
    with _session_lock:
        _session = None


def _throttle():
    """Space requests with a randomised human-like gap so Vinted doesn't flag a
    robot. Tune with VINTED_MIN_DELAY / VINTED_MAX_DELAY (seconds)."""
    global _last_request_ts
    try:
        lo = float(os.getenv("VINTED_MIN_DELAY", "4"))
        hi = float(os.getenv("VINTED_MAX_DELAY", "9"))
    except ValueError:
        lo, hi = 4.0, 9.0
    if hi < lo:
        hi = lo
    with _throttle_lock:
        gap = random.uniform(lo, hi)
        if _last_request_ts:
            elapsed = time.time() - _last_request_ts
            if elapsed < gap:
                time.sleep(gap - elapsed)
        _last_request_ts = time.time()


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
    country = ""
    for k in ("country_title", "country", "country_iso_code"):
        if user.get(k):
            country = user[k]
            break
    return {
        "id": str(item.get("id", "")),
        "title": item.get("title", ""),
        "desc": item.get("description") or item.get("title", ""),
        "price": price,
        "size": item.get("size_title", ""),
        "brand": item.get("brand_title", ""),
        "seller_id": str(user.get("id", "")),
        "photo": photo,
        # Catalog list rarely includes country; the curation script lets you set it.
        "country": country,
        "url": item.get("url", ""),
    }


def fetch_user_location(user_id, timeout=20.0):
    """Look up a seller's advertised location via /api/v2/users/{id}.

    The catalog list only embeds a thin `user`; the country/city live on the full
    user record. Returns {country, country_code, city, expose_location} or {} on any
    error / if the seller hides their location. Throttled like every live call."""
    user_id = str(user_id or "").strip()
    if not user_id:
        return {}
    try:
        sess = _get_session()
    except Exception as e:
        print(f"[vinted] curl_cffi not available ({e}); cannot look up user.")
        return {}
    domain = os.getenv("VINTED_DOMAIN", "fr").strip() or "fr"
    url = f"https://www.vinted.{domain}/api/v2/users/{user_id}"
    _throttle()
    try:
        resp = sess.get(url, timeout=timeout)
    except Exception as e:
        print(f"[vinted] user {user_id} request failed: {e}")
        return {}
    if resp.status_code == 429:
        print(f"[vinted] 429 on user {user_id} — backing off."); time.sleep(30); return {}
    if resp.status_code != 200:
        print(f"[vinted] user {user_id}: HTTP {resp.status_code}")
        return {}
    try:
        user = resp.json().get("user", {}) or {}
    except Exception as e:
        print(f"[vinted] user {user_id}: bad JSON ({e})")
        return {}
    return {
        "country": (user.get("country_title") or user.get("country_title_local") or "").strip(),
        "country_code": (user.get("country_iso_code") or user.get("country_code") or "").strip(),
        "city": (user.get("city") or "").strip(),
        "expose_location": bool(user.get("expose_location", True)),
    }


def _search_live(query, limit, catalog_ids=None):
    """Live Vinted search via the vinted_agent token-hack: a persistent curl_cffi
    Session with a Chrome TLS fingerprint + the session cookie (and optional Bearer)
    from env. Requests are throttled. Returns the mapped listing dicts, or [] on any
    error so the caller falls back to cache."""
    try:
        sess = _get_session()
    except Exception as e:
        print(f"[vinted] curl_cffi not available ({e}); cannot do live search.")
        return []

    domain = os.getenv("VINTED_DOMAIN", "fr").strip() or "fr"
    url = f"https://www.vinted.{domain}/api/v2/catalog/items"
    params = {
        "search_text": query,
        "page": 1,
        "per_page": max(1, min(96, int(limit))),
        "order": "relevance",
        "time": int(time.time()),
    }
    if catalog_ids:
        params["catalog_ids"] = ",".join(str(c) for c in catalog_ids)
    _throttle()
    try:
        resp = sess.get(url, params=params, timeout=20)
    except Exception as e:
        print(f"[vinted] live request failed for {query!r}: {e}")
        return []

    if resp.status_code == 429:
        print(f"[vinted] 429 rate-limited on {query!r} — backing off. Increase "
              f"VINTED_MIN_DELAY/VINTED_MAX_DELAY and slow down.")
        time.sleep(30)
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
