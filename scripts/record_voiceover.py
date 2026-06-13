#!/usr/bin/env python3
"""Record the Lupo video voiceover with Gradium TTS — one WAV per VOICEOVER.md part.

Adapted from Calmami's backend/scripts/record_voiceover.py (same chunk-then-concat
approach), but pointed at Gradium's REST TTS and split into the three parts of
VOICEOVER.md so each can be dropped onto its segment of the edit:

    data/voiceover/part1_architecture.wav
    data/voiceover/part2_demo.wav
    data/voiceover/part3_close.wav

The spoken text below is the finalized VOICEOVER.md script with the **[do: …]** stage
directions removed (those are not spoken). Keep it in sync with VOICEOVER.md.

    python3 scripts/record_voiceover.py            # all three parts
    python3 scripts/record_voiceover.py part2      # just one

Needs GRADIUM_API_KEY (+ optional GRADIUM_VOICE_ID) in .env.
"""
import os
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lupo import config  # noqa: F401,E402  (loads .env)
import httpx  # noqa: E402

GRADIUM_URL = "https://api.gradium.ai/api/post/speech/tts"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "voiceover"
MAX_CHARS = 1400

# ── Spoken text (VOICEOVER.md, stage directions stripped) ─────────────────────
PARTS = {
    "part1_architecture": (
        "This is Lupo — a coordination layer for agents and humans. "
        "Most A.I. agents today are a single model calling tools. The hard part — and the "
        "real value — is the layer above: coordinating a whole team of agents and a person, "
        "together. "
        "Here's the architecture. At the centre is the Coordinator. It doesn't shop, style, "
        "or haggle — it coordinates. It routes work, it holds the shared ledger that every "
        "agent reads and writes, and it runs one policy: act on its own, confirm with me, or "
        "ask me. "
        "Around it: a human-in-the-loop channel — voice, WhatsApp, or web. A swappable roster "
        "of specialist agents — a stylist, buyers, procurement, a negotiator. And a "
        "model-arbitration loop: a small, cheap model does the routine work, and only the hard "
        "cases escalate to Gemini. "
        "Everything domain-specific lives in one swappable layer at the bottom. That's the "
        "whole idea — the core never changes."
    ),
    "part2_demo": (
        "Now watch it run. The brief: a Tomorrowland outfit, twenty euros. "
        "The stylist proposes a look and pings me — and I tweak it: mesh top, a bit more "
        "sparkle. "
        "Then procurement proposes how to split the budget across the four pieces — and this "
        "is a deliberate checkpoint: I approve that split before anything gets bought. "
        "Now the buyers search Vinted in parallel. These listings are real — French, German, "
        "Dutch, Belgian — and the small model pulls structured attributes out of that messy "
        "multilingual text. When it isn't confident — and on day-one listings it often isn't — "
        "it escalates that one up to Gemini, and every correction becomes a labelled training "
        "row for the small model. We ran that fine-tune for real: it lifted the small model's "
        "F-1 by about forty percent. "
        "And here's the moment that matters. The platform boots are the hero of the look — so "
        "Lupo sources them first, and they come in four euros over their slice. The Coordinator "
        "doesn't just overspend — it asks me: negotiate, or stretch? I say stretch — and "
        "procurement reallocates four euros from the other, still-unspent categories, trimming "
        "each a little. Total stays at twenty. Nothing overspent. "
        "And the finish is honest: the four finds come from four sellers in four countries — so "
        "three of them ship, paid online, and only the local one — the boots, from a seller "
        "here in Berchem — becomes an in-person pickup: ten euros, cash, with a tap to send the "
        "message I drafted."
    ),
    "part3_close": (
        "So that's Lupo. The same move repeats at every level — agent to human, cheap model to "
        "frontier model, buyer to seller. "
        "And because all of that lives in the core, you swap the roster and the catalog, and the "
        "outfit shopper becomes industrial technical sales — R.F.Q.s, product catalogs, buyers "
        "and sellers. The coordination layer is the product. The outfit was just the demo."
    ),
}


def split_chunks(text, max_chars=MAX_CHARS):
    """Split into chunks <= max_chars, breaking only at sentence endings."""
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " ").strip())
    chunks, current = [], ""
    for s in sentences:
        candidate = (current + " " + s).strip() if current else s
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = s
    if current:
        chunks.append(current)
    return chunks


def synth_gradium(text, api_key, voice_id):
    """Gradium REST TTS -> WAV bytes (raises on HTTP error / tiny body)."""
    r = httpx.post(GRADIUM_URL, timeout=60.0,
                   headers={"x-api-key": api_key, "Content-Type": "application/json"},
                   json={"text": text, "voice_id": voice_id,
                         "output_format": "wav", "only_audio": True})
    r.raise_for_status()
    if len(r.content) < 100:
        raise RuntimeError(f"Gradium returned a suspiciously small body ({len(r.content)} bytes)")
    return r.content


def _frames(wav):
    return wav[44:] if wav[:4] == b"RIFF" else wav


def _sample_rate(wav):
    if wav[:4] == b"RIFF" and len(wav) >= 28:
        return struct.unpack_from("<I", wav, 24)[0]
    return 22050


def write_wav(path, pcm_chunks, sample_rate):
    pcm = b"".join(pcm_chunks)
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16,
                         1, 1, sample_rate, sample_rate * 2, 2, 16, b"data", len(pcm))
    path.write_bytes(header + pcm)


def render_part(name, text, api_key, voice_id):
    chunks = split_chunks(text)
    print(f"\n{name}: {len(text)} chars -> {len(chunks)} chunk(s)")
    pcm, sr = [], 22050
    for i, c in enumerate(chunks, 1):
        print(f"  synth {i}/{len(chunks)} ({len(c)} chars)…")
        wav = synth_gradium(c, api_key, voice_id)
        if i == 1:
            sr = _sample_rate(wav)
        pcm.append(_frames(wav))
    out = OUT_DIR / f"{name}.wav"
    write_wav(out, pcm, sr)
    print(f"  -> {out}  ({out.stat().st_size:,} bytes)")


def main():
    api_key = os.getenv("GRADIUM_API_KEY", "").strip()
    voice_id = os.getenv("GRADIUM_VOICE_ID", "kr-Om35JRqmA3Hzq").strip()
    if not api_key:
        sys.exit("GRADIUM_API_KEY missing — add it to .env (see .env.example).")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    todo = {k: v for k, v in PARTS.items() if not want or any(w in k for w in want)}
    if not todo:
        sys.exit(f"No part matched {want}. Options: {list(PARTS)}")
    for name, text in todo.items():
        render_part(name, text, api_key, voice_id)
    print(f"\nDone. Voiceover WAVs in {OUT_DIR}")


if __name__ == "__main__":
    main()
