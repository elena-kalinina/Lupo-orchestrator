#!/usr/bin/env python3
"""Pre-render every Gemini-TTS ping for both demo scenarios into the server's audio
cache, so a live run never calls TTS at runtime (immune to the preview-TTS 429 quota).

It replays each scenario with the scripted human to collect the exact prompt + instruct
strings the coordinator will utter (the scenarios are deterministic, so these match the
live run verbatim), then renders each unique line with the SAME cache key the server
uses. Already-cached lines are skipped, so it's safe to re-run after a partial quota hit.

    python3 scripts/prewarm_tts.py

Tip: the chosen TTS model + its fallbacks each have separate quota; this spaces calls
out and rolls over on 429, so running it once a few minutes before the demo is enough.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Capture phase must not hit the network for images; voice must be ON so _speak renders.
os.environ["USE_REAL_FAL"] = "0"
os.environ["USE_REAL_GEMINI"] = "0"
os.environ["USE_REAL_VOICE"] = "1"
os.environ["LUPO_VINTED_LIVE"] = "0"

from lupo.events import EventStream                  # noqa: E402
from lupo.human.channel import ScriptedChannel       # noqa: E402
from lupo.missions import shopping                   # noqa: E402
from lupo import server                              # noqa: E402  (reuse its cache + _speak)


def collect_lines():
    """Every spoken line (prompt questions + one-way instructs) for both scenarios."""
    lines = []
    for scen, cfg in shopping.SCENARIOS.items():
        ch = ScriptedChannel(cfg["script"])
        shopping.run(scen, human=ch, events=EventStream(listener=lambda e: None))
        for _kind, msg, _ans in ch.transcript:
            if msg and msg not in lines:
                lines.append(msg)
    return lines


def _cache_key(text):
    import hashlib
    sig = f"{os.getenv('GEMINI_TTS_MODEL', '')}|{os.getenv('GEMINI_TTS_VOICE', '')}|{text}"
    return hashlib.sha1(sig.encode("utf-8")).hexdigest()[:16]


def _is_cached(text):
    p = server.AUDIO_CACHE / f"{_cache_key(text)}.wav"
    return p.exists() and p.stat().st_size > 0


def main():
    # The preview-TTS quota is a small, slowly-refilling bucket, so we make repeated
    # PASSES: render what we can, wait for the quota to recover, retry the rest. Cached
    # lines are skipped, so each pass only spends quota on the lines still missing.
    gap = float(os.getenv("PREWARM_GAP_S", "12"))         # space successful renders
    recover = float(os.getenv("PREWARM_RECOVER_S", "45"))  # wait after a quota miss
    max_passes = int(os.getenv("PREWARM_MAX_PASSES", "12"))

    lines = collect_lines()
    print(f"{len(lines)} unique ping(s) -> {server.AUDIO_CACHE}\n")
    for p in range(1, max_passes + 1):
        todo = [t for t in lines if not _is_cached(t)]
        if not todo:
            break
        print(f"== pass {p}: {len(todo)} remaining ==")
        hit_quota = False
        for text in todo:
            if _is_cached(text):
                continue
            url = server._speak(text)
            tag = text[:60].replace("\n", " ")
            if url and _is_cached(text):
                print(f"  rendered  {tag}")
                time.sleep(gap)
            else:
                print(f"  quota·skip {tag}")
                hit_quota = True
                time.sleep(2)
        if hit_quota and any(not _is_cached(t) for t in lines):
            print(f"  …waiting {recover:.0f}s for TTS quota to refill\n")
            time.sleep(recover)

    missing = [t for t in lines if not _is_cached(t)]
    done = len(lines) - len(missing)
    print(f"\ncached {done}/{len(lines)} pings.")
    if missing:
        print("Still missing (re-run to fill; cached ones skip):")
        for t in missing:
            print("   -", t[:70].replace("\n", " "))
        sys.exit(1)
    print("All pings cached — the live demo will play voice with no runtime TTS calls.")


if __name__ == "__main__":
    main()
