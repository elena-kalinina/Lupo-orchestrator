#!/usr/bin/env python3
"""Harvest GLiNER2→Gemini training rows from the cached Vinted listings — fast.

The model-arbitration loop normally banks a training row whenever a listing
escalates *during a mission*. That's slow to accumulate (one row per escalation
per run). This script batches the whole cached catalogue straight through the
loop in one pass, so you build a real labelled dataset in a couple of minutes
without running missions or hitting Vinted:

  for each unique listing text:
    cheap model (Pioneer GLiNER2, or the keyword stub) -> attrs + confidence
    frontier model (Gemini)                            -> the corrected label
    -> append {text, lang, gliner, label, gliner_conf} to extraction_samples.jsonl

It is idempotent: texts already in data/extraction_samples.jsonl are skipped, so
re-running only harvests new listings.

Needs GEMINI_API_KEY + USE_REAL_GEMINI=1 for real labels (otherwise the Gemini
side is the stub and the rows aren't useful for training). USE_PIONEER=1 makes
the "before" column the real GLiNER2 base; otherwise it's the keyword stub.

Usage:
  USE_REAL_GEMINI=1 USE_PIONEER=1 python3 scripts/harvest_samples.py
  python3 scripts/harvest_samples.py --limit 20         # cap the number of Gemini calls
  python3 scripts/harvest_samples.py --dry-run          # list what WOULD be harvested
"""
import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from lupo import config            # noqa: E402  (loads .env)
from lupo import samples           # noqa: E402
from lupo import extract_entities as ex  # noqa: E402

CACHE_DIR = _ROOT / "data" / "vinted_cache"


def _listing_texts():
    """Every unique '{title} {desc}' across the cached listings, in a stable order."""
    seen, texts = set(), []
    for path in sorted(CACHE_DIR.glob("*.json")):
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in items:
            text = f"{it.get('title','')} {it.get('desc','')}".strip()
            key = text.lower()
            if text and key not in seen:
                seen.add(key)
                texts.append(text)
    return texts


def _cheap_extract(text):
    """The 'before' column: Pioneer GLiNER2 if enabled, else the keyword stub."""
    if config.USE_PIONEER:
        try:
            from lupo import pioneer
            return pioneer.extract(text, ex.LABELS, threshold=0.4) + ("pioneer-gliner2",)
        except Exception as e:
            print(f"  [pioneer fallback: {e}]", file=sys.stderr)
    attrs = {"material": ex._scan(text, ex._MATERIAL),
             "style": ex._scan(text, ex._STYLE),
             "fit": ex._scan(text, ex._FIT)}
    conf = min(1.0, 0.3 + 0.25 * sum(len(v) for v in attrs.values()))
    return attrs, conf, "keyword-stub"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max NEW listings to harvest (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be harvested, call nothing")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between Gemini calls (rate-limit cushion)")
    args = ap.parse_args()

    texts = _listing_texts()
    done = {r.get("text", "").lower() for r in samples.load()}
    todo = [t for t in texts if t.lower() not in done]
    if args.limit:
        todo = todo[: args.limit]

    print(f"cached listings: {len(texts)} | already harvested: {len(done)} | to harvest: {len(todo)}")
    if args.dry_run:
        for t in todo:
            print("  +", t[:80])
        return 0
    if not todo:
        print("Nothing new to harvest.")
        return 0
    if not config.USE_REAL_GEMINI:
        print("WARNING: USE_REAL_GEMINI=0 — the Gemini label will be the stub, not useful for "
              "training. Set USE_REAL_GEMINI=1 (and GEMINI_API_KEY) for real rows.", file=sys.stderr)

    harvested = 0
    for i, text in enumerate(todo, 1):
        attrs, conf, source = _cheap_extract(text)
        lang = ex._guess_lang(text)
        try:
            label = ex._gemini_extract(text)   # frontier truth (real Gemini when toggled on)
        except Exception as e:
            print(f"  [{i}/{len(todo)}] Gemini failed ({e}); skipping", file=sys.stderr)
            continue
        samples.record(text, lang, attrs, label, conf)
        harvested += 1
        flat = ", ".join(f"{k}={v}" for k, v in label.items() if v) or "none"
        print(f"  [{i}/{len(todo)}] [{lang}] {source} conf {conf:.2f} -> Gemini: {flat}  «{text[:46]}»")
        if args.sleep:
            time.sleep(args.sleep)

    print(f"\nHarvested {harvested} new rows -> {samples.SAMPLES_PATH}")
    print("Next: python3 scripts/pioneer_finetune.py --phase all")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        msg = str(e).lower()
        if any(x in msg for x in ("429", "quota", "rate limit", "resource exhausted")):
            print(f"WARN (quota): {e}", file=sys.stderr)
            sys.exit(0)
        print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)
