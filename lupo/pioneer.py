"""Fastino Pioneer client — hosted GLiNER2 inference + LoRA finetune.

Pioneer (https://pioneer.ai) hosts small encoder models (GLiNER2) for NER /
structured extraction, served from CPU in <100ms, plus LoRA finetuning and the
adaptive-inference loop. We use it as Lupo's cheap, multilingual extractor — the
bottom level of the same arbitration pattern (cheap model handles the routine,
the frontier model handles the hard case, escalations become training data).

Auth: X-API-Key header. Inference: POST /inference with a {"entities": [...]}
schema. Finetune: POST /felix/training-jobs (see scripts/pioneer_finetune.py).

This module is import-safe with no key set; callers gate on config.USE_PIONEER
and fall back to the keyword stub / Gemini escalation on any error.
"""
import os

DEFAULT_API_BASE = "https://api.pioneer.ai"


def base_url():
    return os.getenv("PIONEER_API_BASE", DEFAULT_API_BASE).rstrip("/")


def api_key():
    return os.getenv("PIONEER_API_KEY", "").strip()


def headers():
    return {"X-API-Key": api_key(), "Content-Type": "application/json"}


def model_id():
    """Prefer a finetuned LoRA job id if configured, else the base GLiNER2 model."""
    return (os.getenv("PIONEER_TRAINED_MODEL_ID", "").strip()
            or os.getenv("PIONEER_BASE_MODEL", "fastino/gliner2-base-v1").strip())


def infer(text, labels, threshold=0.4, model=None, timeout=20.0):
    """POST /inference for entity extraction. Returns the raw Pioneer envelope."""
    import httpx
    if not api_key():
        raise RuntimeError("PIONEER_API_KEY not set")
    body = {
        "model_id": model or model_id(),
        "text": text,
        "schema": {"entities": list(labels)},
        "threshold": threshold,
    }
    r = httpx.post(f"{base_url()}/inference", json=body, headers=headers(), timeout=timeout)
    if r.status_code >= 300:
        raise RuntimeError(f"Pioneer /inference {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def _find_entities(raw):
    """Pioneer's response shape varies; dig out a list of {text,label,score} spans.
    Confirmed/likely layouts:
      {type:"encoder", result:{entities:[...]}}
      {output:{entities:[...]}}
      {entities:[...]}
    """
    if not isinstance(raw, dict):
        return []
    for container in (raw.get("result"), raw.get("output"), raw):
        if isinstance(container, dict):
            ents = container.get("entities") or container.get("spans")
            if isinstance(ents, list):
                return [e for e in ents if isinstance(e, dict)]
    return []


def extract(text, labels, threshold=0.4, model=None):
    """High-level: return (attrs, confidence) grouped by label, matching the shape
    extract_entities expects: {"material": [...], "style": [...], "fit": [...]}.
    Raises on transport/auth error so the caller can fall back."""
    raw = infer(text, labels, threshold=threshold, model=model)
    spans = _find_entities(raw)
    attrs = {k: [] for k in ("material", "style", "fit")}
    scores = []
    for e in spans:
        label = (e.get("label") or e.get("type") or "").lower()
        value = (e.get("text") or e.get("value") or "").lower().strip()
        if not value:
            continue
        sc = e.get("score") or e.get("confidence")
        if isinstance(sc, (int, float)):
            scores.append(float(sc))
        if label in attrs:
            attrs[label].append(value)
    if scores:
        conf = sum(scores) / len(scores)
    else:
        conf = min(1.0, 0.3 + 0.25 * sum(len(v) for v in attrs.values()))
    return attrs, conf
