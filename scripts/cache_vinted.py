#!/usr/bin/env python3
"""Cache real Vinted listings for the EXACT queries the demo will issue.

Why this exists
---------------
The canvas shows a photo per find. In replay mode those come from the cached
fixtures in data/vinted_cache/. This script pulls real listings from Vinted for
the precise queries each scenario produces, so the demo shows real photos/prices.

Prerequisite
------------
Wire your `vinted_agent` client into  lupo/vinted/client.py::_search_live  first
(see IMPLEMENTATION_PLAN.md, step 4). This script only enumerates the queries and
drives the caching; the live fetch itself is your client.

Modes
-----
  python scripts/cache_vinted.py
        DEMO-SAFE (default, --photos-only): keep the curated fixtures exactly as
        they are (prices, seller country, persona — the things that make the
        negotiate / reallocate / pickup beats work) and only swap in REAL photo
        (and listing URL) from the live results. The story is unchanged; the
        pictures become real.

  python scripts/cache_vinted.py --full
        Overwrite each fixture with the fully-real live listings. Most authentic,
        but real prices may not trigger the scripted over-budget beats — only use
        this if you've re-checked the economics.

  python scripts/cache_vinted.py --scenario tomorrowland   # default: both
  python scripts/cache_vinted.py --limit 6
"""
import os
import sys
import json
import argparse

# Deterministic queries: force the rule-based stylist (not Gemini) for enumeration.
os.environ["USE_REAL_GEMINI"] = "0"
# We drive caching ourselves, so don't let client.search auto-overwrite.
os.environ.setdefault("LUPO_VINTED_LIVE", "0")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lupo.agents.stylist import Stylist          # noqa: E402
from lupo.missions.shopping import SCENARIOS      # noqa: E402
from lupo.vinted import client                    # noqa: E402


class _NullEvents:
    """Stylist needs an event sink; we don't want to touch the event stream here."""
    def emit(self, *a, **k):
        pass


def queries_for(scenario):
    """Reproduce the exact post-amendment queries the Buyer will search for."""
    cfg = SCENARIOS[scenario]
    stylist = Stylist("stylist", _NullEvents())
    palette, comps = stylist.propose_spec(cfg["brief"], cfg["budget"])
    amend_reply = next((reply for needle, reply in cfg["script"] if needle == "amendments"), "")
    if amend_reply:
        stylist.amend(comps, amend_reply)
    return [(c.name, stylist.query_for(c, palette)) for c in comps]


def graft_photos(query, live, limit):
    """DEMO-SAFE: keep the curated fixture, only replace photo/url from live."""
    path = client.CACHE_DIR / f"{client._slug(query)}.json"
    if not path.exists():
        print(f"    ! no curated fixture at {path.name}; skipping (use --full to create it)")
        return 0
    fixture = json.loads(path.read_text(encoding="utf-8"))
    n = 0
    for i, entry in enumerate(fixture):
        if i < len(live) and live[i].get("photo"):
            entry["photo"] = live[i]["photo"]
            if live[i].get("url"):
                entry["url"] = live[i]["url"]
            n += 1
    path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    return n


def overwrite(query, live, limit):
    """--full: replace the fixture with real listings."""
    client._cache_write(query, live[:limit])
    return len(live[:limit])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=list(SCENARIOS) + ["all"], default="all")
    ap.add_argument("--full", action="store_true", help="overwrite fixtures with real listings")
    ap.add_argument("--limit", type=int, default=8)
    args = ap.parse_args()

    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    handler = overwrite if args.full else graft_photos
    mode = "FULL overwrite" if args.full else "photos-only (demo-safe)"
    print(f"Caching real Vinted listings · mode = {mode}\n")

    total = 0
    for sc in scenarios:
        print(f"[{sc}]")
        for name, q in queries_for(sc):
            try:
                live = client._search_live(q, args.limit)
            except NotImplementedError:
                print("\n  ✗ _search_live is not wired yet.")
                print("    Edit lupo/vinted/client.py::_search_live to call your vinted_agent")
                print("    client and map results to {id,title,desc,price,size,brand,seller_id,")
                print("    photo,country,url}. Then re-run this script. (See IMPLEMENTATION_PLAN.md.)")
                return 1
            except Exception as e:
                print(f"    ! {name}: live search failed ({e}) — left fixture unchanged")
                continue
            got = handler(q, live, args.limit)
            total += got
            print(f"    {name:<12} “{q}” → {len(live)} live, {got} written")
        print()
    print(f"Done. {total} listings written. Re-run the mission and open the canvas to check photos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
