#!/usr/bin/env python3
"""Report which scenario pings are already rendered in the TTS audio cache."""
import os
import sys
import hashlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["USE_REAL_FAL"] = "0"
os.environ["USE_REAL_VOICE"] = "1"

from lupo.events import EventStream
from lupo.human.channel import ScriptedChannel
from lupo.missions import shopping
from lupo import server


def key(t):
    sig = f"{os.getenv('GEMINI_TTS_MODEL', '')}|{os.getenv('GEMINI_TTS_VOICE', '')}|{t}"
    return hashlib.sha1(sig.encode()).hexdigest()[:16]


for scen in ["brunch", "tomorrowland"]:
    cfg = shopping.SCENARIOS[scen]
    ch = ScriptedChannel(cfg["script"])
    shopping.run(scen, human=ch, events=EventStream(listener=lambda e: None))
    n = tot = 0
    print(f"\n=== {scen} ===")
    seen = set()
    for _k, msg, _a in ch.transcript:
        if msg in seen:
            continue
        seen.add(msg)
        tot += 1
        p = server.AUDIO_CACHE / f"{key(msg)}.wav"
        hit = p.exists() and p.stat().st_size > 0
        n += hit
        print(("  OK " if hit else "  -- "), msg[:62].replace("\n", " "))
    print(f"  {n}/{tot} cached")
