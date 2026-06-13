#!/usr/bin/env python3
"""Live Vinted helper: test auth, fetch real listings, and curate the replay cache.

The demo runs from data/vinted_cache/ (fast, offline, deterministic). This script
is how you fill that cache with REAL finds — and, importantly, lets you pick the
good ones by hand so the demo always looks great.

Usage
-----
  # 1) Verify the cookie/token actually work (single probe request):
  python scripts/vinted_live.py test

  # 2) Fetch every query for a scenario, pick the good finds, cache them:
  python scripts/vinted_live.py scenario brunch
  python scripts/vinted_live.py scenario tomorrowland

  # 3) Or a one-off query:
  python scripts/vinted_live.py search "floral midi dress cream" --limit 16

Notes
-----
- Requests are throttled (VINTED_MIN_DELAY..VINTED_MAX_DELAY) to avoid the bot
  flag. A full scenario is ~6-11 spaced requests, so expect ~1 minute.
- Vinted will eventually rate-limit / log you out. When that happens, refresh
  VINTED_SESSION_COOKIE (and VINTED_BEARER_TOKEN) in .env and re-run. Anything you
  already curated stays cached.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from lupo.vinted import client as vinted

# Build each scenario's queries with the SAME rule the stylist uses at runtime:
#   query = " ".join(style_tags[:2] + [name, palette[0]])
# We include both the base and the amended variants for slots the demo edits
# (brunch: shoes & bag; tomorrowland: top), so replay has a cache either way.
SCENARIOS = {
    "brunch": {
        "palette0": "cream",
        "components": [
            ("dress", ["floral", "midi"]),
            ("shoes", ["sandals", "tan"]),       # base
            ("shoes", ["ballet", "flat"]),       # after the "ballet flats" amendment
            ("bag", ["raffia", "tote"]),         # base
            ("bag", ["shoulder", "small"]),      # after the "shoulder bag" amendment
            ("jewellery", ["gold", "hoops"]),
        ],
    },
    "tomorrowland": {
        "palette0": "neon",
        "components": [
            ("top", ["mesh", "sparkle"]),        # after the "mesh + sparkle" amendment
            ("top", ["crop", "plain"]),          # base
            ("bottoms", ["cargo", "techno"]),
            ("accessories", ["holographic", "sunglasses"]),
            ("boots", ["platform", "chunky"]),
        ],
    },
}

# Shopper profile (matches the vinted_agent defaults): WOMEN, clothes size M,
# shoes 38. Catalog ids are the REAL women's ids read from the Vinted catalog tree.
# Override the sizes via env if you want.
CLOTHES_SIZE = os.getenv("LUPO_CLOTHES_SIZE", "M").upper()
SHOE_SIZE = os.getenv("LUPO_SHOE_SIZE", "38")
_FR_NUM = {"XS": "34", "S": "36", "M": "38", "L": "40", "XL": "42"}


def _clothes_tokens():
    toks = [CLOTHES_SIZE]
    if CLOTHES_SIZE in _FR_NUM:
        toks.append(_FR_NUM[CLOTHES_SIZE])   # accept FR numeric equivalent too
    return toks


# How many listings to pull from the API before client-side size filtering. The
# size string lives in the result, not a query param, so we need a wide net to be
# sure size-M items actually appear. (No extra latency — per_page is free.)
FETCH_N = int(os.getenv("LUPO_FETCH_N", "96"))

# EN -> FR style terms: the .fr catalog is full of French titles, so an English-only
# search misses most of them. We try the English tags, then the French ones.
_FR_TERMS = {
    "floral": "fleurie", "midi": "midi", "casual": "casual",
    "sandals": "sandales", "tan": "beige", "flat": "plates", "ballet": "ballerines",
    "raffia": "raphia", "tote": "cabas", "summer": "été",
    "shoulder": "bandoulière", "small": "petit",
    "gold": "dorées", "hoops": "créoles", "dainty": "fines",
    "crop": "court", "plain": "uni", "mesh": "résille", "sparkle": "paillettes",
    "cargo": "cargo", "techno": "techno",
    "holographic": "holographique", "sunglasses": "lunettes de soleil",
    "platform": "plateforme", "chunky": "épaisses",
}


def _fr(tags):
    return " ".join(_FR_TERMS.get(t, t) for t in tags)


# component name -> (women's catalog ids, size tokens to keep). Bags/accessories/
# jewellery are one-size, so no size filter.
def _filters_for(name):
    clothes = (_clothes_tokens(), None)
    shoes = ([SHOE_SIZE], None)
    table = {
        "dress": ([10], _clothes_tokens()),
        "top": ([12], _clothes_tokens()),
        "bottoms": ([9], _clothes_tokens()),
        "shoes": ([16], [SHOE_SIZE]),
        "boots": ([16], [SHOE_SIZE]),
        "bag": ([19], None),
        "accessories": ([26], None),
        "jewellery": ([163], None),
    }
    return table.get(name, (None, None))


def _query_for(name, style_tags, palette0):
    return " ".join(style_tags[:2] + [name, palette0])


def _fetch(query, limit, catalog_ids=None, size_tokens=None):
    """Force a live, non-recording fetch (we cache only curated picks)."""
    os.environ["LUPO_VINTED_LIVE"] = "1"
    os.environ["LUPO_VINTED_RECORD"] = "0"
    return vinted.search(query, max_price=None, limit=limit,
                         catalog_ids=catalog_ids, size_tokens=size_tokens)


def _fetch_best(tags, catalog_ids, size_tokens, min_hits=3):
    """Progressively broaden the search until we get enough real listings: English
    tags -> French tags -> first English tag -> French of it -> catalog+size only.
    Fetches a wide page (FETCH_N) so client-side size filtering has enough to keep."""
    en, fr = " ".join(tags), _fr(tags)
    attempts = [en]
    if fr != en:
        attempts.append(fr)
    if tags:
        attempts.append(tags[0])
        if _FR_TERMS.get(tags[0], tags[0]) != tags[0]:
            attempts.append(_FR_TERMS[tags[0]])
    attempts.append("")  # catalog + size only
    items, used = [], attempts[0]
    for text in attempts:
        items = _fetch(text, FETCH_N, catalog_ids=catalog_ids, size_tokens=size_tokens)
        used = text
        if len(items) >= min_hits:
            break
    return items, used


def _show(items):
    for i, it in enumerate(items):
        ctry = f" · {it['country']}" if it.get("country") else ""
        print(f"  [{i:>2}] €{it['price']:<5} {it['title'][:52]:<52} "
              f"({it.get('size','')}){ctry}")
        if it.get("photo"):
            print(f"        {it['photo']}")
    if not items:
        print("  (no results)")


def _ask(prompt, default=""):
    try:
        val = input(prompt).strip()
    except EOFError:
        return default
    return val or default


def _parse_selection(raw, n):
    raw = raw.strip().lower()
    if raw in ("", "skip"):
        return None  # leave existing cache untouched
    if raw == "all":
        return list(range(n))
    if raw == "none":
        return []
    idx = []
    for tok in raw.replace(" ", ",").split(","):
        if tok.isdigit() and 0 <= int(tok) < n:
            idx.append(int(tok))
    return idx


def _curate(query, items, interactive=True):
    """Show results, let the user keep the good ones (+ set country/persona),
    and write them to the replay cache for `query`."""
    print(f"\n=== {query!r} — {len(items)} live results ===")
    _show(items)
    if not items:
        return
    if not interactive:
        keep = items[:8]   # top relevance, keep the cache demo-sized
        vinted._cache_write(query, keep)
        print(f"  -> cached {len(keep)} (non-interactive).")
        return
    sel = _parse_selection(
        _ask("  keep which? (e.g. 0,2,5 | all | none | skip): "), len(items))
    if sel is None:
        print("  -> skipped (cache unchanged).")
        return
    kept = [items[i] for i in sel]
    for it in kept:
        # Country drives the ship-vs-local-pickup narrative; persona drives the
        # negotiation. Enter keeps the current/default value.
        it["country"] = _ask(f"    country for '{it['title'][:30]}' "
                             f"[{it.get('country','') or 'blank'}]: ",
                             it.get("country", "")) or it.get("country", "")
        it["persona"] = _ask("    persona (flexible/firm/motivated) [flexible]: ",
                             it.get("persona", "flexible"))
    vinted._cache_write(query, kept)
    print(f"  -> cached {len(kept)} curated find(s) "
          f"to data/vinted_cache/{vinted._slug(query)}.json")


# --- Narrative enrichment ----------------------------------------------------
# The catalog list API omits seller country, so we ASSIGN a coherent country +
# seller persona per slot. This drives the "ships from France/NL/Italy" beat and
# the one local in-person pickup, plus the negotiation persona — deterministically,
# with the real items/photos/prices untouched.
COUNTRY_PROFILE = {
    "brunch": {"dress": "France", "shoes": "Netherlands", "bag": "Italy", "jewellery": "France"},
    "tomorrowland": {"top": "France", "bottoms": "Netherlands", "accessories": "Italy", "boots": "Germany"},
}
PERSONA_PROFILE = {
    "brunch": {"dress": "motivated", "shoes": "flexible", "bag": "flexible", "jewellery": "firm"},
    "tomorrowland": {"top": "flexible", "bottoms": "flexible", "accessories": "motivated", "boots": "firm"},
}
# The buyer picks by STYLE FIT, not price, so a pricey high-fit outlier in a slot
# would blow its budget and derail the scripted demo. We therefore shape each slot's
# cached price band:
#   - non-hero slots: ceiling = the slot's allocation, so whatever the buyer picks fits.
#   - hero slot (floor, ceiling): kept dear enough to trigger the beat but still
#     negotiable/affordable. brunch dress -> negotiate; tomorrowland boots -> stretch.
HERO = {"brunch": ("dress", 12.0, 20.0), "tomorrowland": ("boots", 0.0, 12.0)}


def cmd_narrate(args):
    scn = SCENARIOS.get(args.name)
    if not scn:
        print(f"Unknown scenario {args.name!r}."); sys.exit(1)
    from lupo.missions.shopping import SCENARIOS as MISSION_SCN
    allocations = (MISSION_SCN.get(args.name, {}) or {}).get("allocations", {})
    countries = COUNTRY_PROFILE.get(args.name, {})
    personas = PERSONA_PROFILE.get(args.name, {})
    hero_name, hero_floor, hero_ceil = HERO.get(args.name, (None, 0.0, 1e9))
    touched = 0
    for name, tags in scn["components"]:
        cache_query = _query_for(name, tags, scn["palette0"])
        cache_dir = vinted.CACHE_DIR.resolve()
        path = (cache_dir / f"{vinted._slug(cache_query)}.json").resolve()
        # _slug() already strips to [a-z0-9_]; this guard makes the containment explicit
        # so the path can never escape the cache dir regardless of the query string.
        if cache_dir not in path.parents or not path.exists():
            continue
        items = json.loads(path.read_text(encoding="utf-8"))
        if name == hero_name:
            lo, hi, band = hero_floor, hero_ceil, f"[band €{hero_floor:.0f}-{hero_ceil:.0f}]"
        else:                                          # keep picks within the slice
            lo, hi, band = 0.0, allocations.get(name, 1e9), f"[≤€{allocations.get(name, 0):.0f}]"
        kept = [it for it in items if lo <= it.get("price", 0) <= hi]
        if kept:                                       # never empty a slot
            items = kept
        for it in items:
            it["country"] = countries.get(name, it.get("country", ""))
            it["persona"] = personas.get(name, it.get("persona", "flexible"))
        if getattr(args, "real_countries", False):
            for it in items:
                loc = vinted.fetch_user_location(it.get("seller_id"))
                if loc.get("country") and loc.get("expose_location", True):
                    it["country"] = loc["country"]
                    if loc.get("country_code"):
                        it["country_code"] = loc["country_code"]
                    if loc.get("city"):
                        it["city"] = loc["city"]
        path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        touched += 1
        prices = sorted(round(i["price"]) for i in items)
        if getattr(args, "real_countries", False):
            locs = sorted({(i.get("country", "?") + (f"/{i['city']}" if i.get("city") else "")) for i in items})
            loc_str = ", ".join(locs)
        else:
            loc_str = countries.get(name, "?")
        print(f"  {name:<11} {loc_str:<22} persona={personas.get(name,'flexible'):<9} "
              f"€prices={prices} {band}")
    print(f"\nEnriched {touched} slot(s) for {args.name!r}. "
          f"Use the €prices above to tune budgets/allocations for the drama.")


def cmd_test(args):
    print("Probing Vinted auth with a single search…")
    items = _fetch(args.query, args.limit)
    if items:
        print(f"✅ SUCCESS — {len(items)} items for {args.query!r}.")
        _show(items[:5])
    else:
        print("❌ No items. Check VINTED_SESSION_COOKIE / VINTED_BEARER_TOKEN in .env, "
              "or you may be rate-limited (wait and retry).")
        sys.exit(1)


def cmd_search(args):
    items = _fetch(args.query, args.limit)
    _curate(args.query, items, interactive=not args.yes)


def cmd_scenario(args):
    scn = SCENARIOS.get(args.name)
    if not scn:
        print(f"Unknown scenario {args.name!r}. Choose: {', '.join(SCENARIOS)}")
        sys.exit(1)
    # cache_query = the canonical slug the runtime stylist will look up.
    # fetch_text  = what we actually send to Vinted (just the style tags; the
    #               catalog_ids filter supplies the category, so the generic noun
    #               + palette colour only hurt recall against FR/NL/IT listings).
    plan = [(n, tags, _query_for(n, tags, scn["palette0"]), " ".join(tags))
            for n, tags in scn["components"]]
    print(f"Scenario {args.name!r}: {len(plan)} queries (throttled, WOMEN · "
          f"clothes {CLOTHES_SIZE} · shoes {SHOE_SIZE}). Pick good finds for each.\n"
          + "\n".join(f"  · {cq}  (search: {ft!r})" for _, _, cq, ft in plan))
    for name, tags, cache_query, fetch_text in plan:
        catalog_ids, size_tokens = _filters_for(name)
        items, used = _fetch_best(tags, catalog_ids, size_tokens)
        if used != fetch_text:
            print(f"  ({cache_query!r}: searched {used!r} for enough hits)")
        _curate(cache_query, items[:args.limit], interactive=not args.yes)
    print("\nDone. Demo in replay mode with LUPO_VINTED_LIVE=0 to use these picks.")


def main():
    p = argparse.ArgumentParser(description="Live Vinted fetch + cache curation.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pt = sub.add_parser("test", help="single probe search to verify auth")
    pt.add_argument("query", nargs="?", default="levis 501")
    pt.add_argument("--limit", type=int, default=10)
    pt.set_defaults(func=cmd_test)

    ps = sub.add_parser("search", help="one query, curate + cache")
    ps.add_argument("query")
    ps.add_argument("--limit", type=int, default=16)
    ps.add_argument("--yes", action="store_true", help="cache all, no prompts")
    ps.set_defaults(func=cmd_search)

    pc = sub.add_parser("scenario", help="all queries for a scenario, curate + cache")
    pc.add_argument("name", choices=list(SCENARIOS))
    pc.add_argument("--limit", type=int, default=16)
    pc.add_argument("--yes", action="store_true", help="cache all, no prompts")
    pc.set_defaults(func=cmd_scenario)

    pn = sub.add_parser("narrate", help="enrich cached items with country + persona (offline)")
    pn.add_argument("name", choices=list(SCENARIOS))
    pn.add_argument("--real-countries", action="store_true",
                    help="fetch each kept seller's real country/city from Vinted (live, throttled)")
    pn.set_defaults(func=cmd_narrate)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
