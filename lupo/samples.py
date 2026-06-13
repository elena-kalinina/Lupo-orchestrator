"""Training-sample store for the model-arbitration loop.

When GLiNER is unsure and escalates a listing to Gemini, Gemini's extraction is
recorded here as a labeled sample. Pioneer's adaptive inference retrains GLiNER on
these — the cheap model learns from the frontier model's judgment over time.
Same active-learning principle as the agent<->human escalation, one level down.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

SAMPLES_PATH = Path(__file__).resolve().parent.parent / "data" / "extraction_samples.jsonl"


def record(text, lang, gliner_attrs, gemini_attrs, gliner_conf):
    SAMPLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(), "text": text, "lang": lang,
           "gliner": gliner_attrs, "label": gemini_attrs, "gliner_conf": round(gliner_conf, 3)}
    with open(SAMPLES_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def load():
    if not SAMPLES_PATH.exists():
        return []
    with open(SAMPLES_PATH, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
