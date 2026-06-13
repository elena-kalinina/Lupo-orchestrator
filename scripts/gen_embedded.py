#!/usr/bin/env python3
"""Regenerate the canvas's offline EMBEDDED arrays from a real (cached) run.

The canvas ships two baked-in event streams (`EMBEDDED`, `EMBEDDED_TOMORROWLAND`)
so the double-click / file:// demo works with no server. They must mirror what a
live `python -m lupo.server` run produces — same finds, same prices, same seller
countries, same checkout links — otherwise the offline demo drifts (stale photos,
items the cache no longer has, links that don't match the chosen pieces).

This runs both scenarios offline-deterministic, captures the event stream, trims it
to the fields the canvas renders, and splices the two arrays back into canvas.html.

    python3 scripts/gen_embedded.py
"""
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force the deterministic, offline path so the baked run never depends on live keys.
for k in ("USE_REAL_GEMINI", "USE_REAL_FAL", "USE_REAL_VOICE", "USE_REAL_VISION",
          "USE_PIONEER", "USE_REAL_GLINER", "LUPO_VINTED_LIVE"):
    os.environ[k] = "0"

from lupo.events import EventStream          # noqa: E402
from lupo.missions import shopping           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CANVAS = ROOT / "frontend" / "canvas.html"
CAND_KEYS = ("title", "price", "size", "lang", "desc", "photo", "country",
             "attrs", "source", "fit", "best")
MAX_CARDS = 3   # keep the finds card tidy; the run already ranks best-first


def capture(scenario):
    rows = []
    events = EventStream(listener=lambda ev: rows.append(ev))
    shopping.run(scenario, events=events)
    return rows


def trim(rows):
    out = []
    for ev in rows:
        if ev.get("kind") == "preview":
            continue                      # fal URLs expire; offline shows no preview
        # The per-item GLiNER "unsure -> Gemini" escalations and the "extracted ..."
        # confirmations are real, but each find card already carries the
        # `gemini-escalation` source tag, so rendering them as separate feed rows just
        # adds noise. Keep the feed to the coordination beats (the canvas stays in sync
        # with live, which streams these too but the card tag tells the same story).
        if ev.get("actor") == "buyer" and (
                ev.get("kind") == "escalation"
                or (ev.get("kind") == "message"
                    and str(ev.get("text", "")).startswith("extracted"))):
            continue
        e = {"seq": ev["seq"], "kind": ev["kind"], "actor": ev["actor"]}
        if ev.get("text"):
            e["text"] = ev["text"]
        if ev.get("kind") == "candidates" and ev.get("candidates"):
            e["candidates"] = [{k: c[k] for k in CAND_KEYS if k in c}
                               for c in ev["candidates"][:MAX_CARDS]]
        if ev.get("kind") == "links" and ev.get("links"):
            e["links"] = [{"title": l.get("title", ""), "url": l.get("url", "")}
                          for l in ev["links"]]
        out.append(e)
    for n, e in enumerate(out, 1):       # renumber so the filtered feed has no seq gaps
        e["seq"] = n
    return out


def as_js_array(rows):
    lines = [json.dumps(r, ensure_ascii=False) for r in rows]
    return "[\n" + ",\n".join(lines) + "\n]"


def splice(html, name, arr_js):
    pat = re.compile(r"const " + name + r" = \[.*?\n\];", re.S)
    new = f"const {name} = {arr_js};"
    if not pat.search(html):
        raise SystemExit(f"could not find `const {name} = [...]` in canvas.html")
    return pat.sub(lambda _m: new, html, count=1)


def main():
    brunch = trim(capture("brunch"))
    tl = trim(capture("tomorrowland"))
    html = CANVAS.read_text(encoding="utf-8")
    html = splice(html, "EMBEDDED", as_js_array(brunch))
    html = splice(html, "EMBEDDED_TOMORROWLAND", as_js_array(tl))
    CANVAS.write_text(html, encoding="utf-8")
    print(f"brunch: {len(brunch)} events | tomorrowland: {len(tl)} events -> {CANVAS}")
    for label, rows in (("brunch", brunch), ("tomorrowland", tl)):
        picks = [r["text"] for r in rows if r.get("text", "").startswith(("dress: pick",
                 "top: pick"))]
        has_links = any(r["kind"] == "links" for r in rows)
        print(f"  {label}: links_event={has_links}  {picks}")


if __name__ == "__main__":
    main()
