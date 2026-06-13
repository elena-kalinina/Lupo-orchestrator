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
    trained = os.getenv("PIONEER_TRAINED_MODEL_ID", "").strip()
    # Guard against a stray inline comment / placeholder leaking in: dotenv keeps
    # "# set to your job id…" as the value when the var is left empty with a comment.
    if trained.startswith("#") or " " in trained:
        trained = ""
    return trained or os.getenv("PIONEER_BASE_MODEL", "fastino/gliner2-base-v1").strip()


def infer(text, labels, model=None, timeout=20.0):
    """POST /inference for GLiNER2 entity extraction. Returns the raw Pioneer
    envelope. Confirmed surface (encoder task `extract_entities`):
      body  -> {model_id, task:"extract_entities", text, schema:[<labels>]}  (schema is a LIST)
      reply -> {type:"encoder", result:{data:{entities:{<label>:[{text,confidence,start,end}]}}}}"""
    import httpx
    if not api_key():
        raise RuntimeError("PIONEER_API_KEY not set")
    body = {
        "model_id": model or model_id(),
        "task": "extract_entities",
        "text": text,
        "schema": list(labels),
    }
    r = httpx.post(f"{base_url()}/inference", json=body, headers=headers(), timeout=timeout)
    if r.status_code >= 300:
        raise RuntimeError(f"Pioneer /inference {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def _entities(raw):
    """Pull the {label: [span, ...]} map out of the encoder envelope.
    Tolerates the wrapped (result.data.entities) and flatter shapes."""
    if not isinstance(raw, dict):
        return {}
    node = raw.get("result", raw)
    if isinstance(node, dict) and isinstance(node.get("data"), dict):
        node = node["data"]
    ents = node.get("entities") if isinstance(node, dict) else None
    return ents if isinstance(ents, dict) else {}


def extract(text, labels, threshold=0.4, model=None):
    """High-level: return (attrs, confidence) grouped by label, matching the shape
    extract_entities expects: {"material": [...], "style": [...], "fit": [...]}.
    Spans below `threshold` confidence are dropped. Raises on transport/auth error
    so the caller can fall back to Gemini / the keyword stub."""
    raw = infer(text, labels, model=model)
    ents = _entities(raw)
    attrs = {k: [] for k in ("material", "style", "fit")}
    scores = []
    for label, spans in ents.items():
        if not isinstance(spans, list):
            continue
        lbl = str(label).lower()
        for e in spans:
            if not isinstance(e, dict):
                continue
            value = (e.get("text") or e.get("value") or "").lower().strip()
            sc = e.get("confidence")
            if sc is None:
                sc = e.get("score")
            if isinstance(sc, (int, float)) and sc < threshold:
                continue
            if not value:
                continue
            if isinstance(sc, (int, float)):
                scores.append(float(sc))
            if lbl in attrs:
                attrs[lbl].append(value)
    if scores:
        conf = sum(scores) / len(scores)
    else:
        conf = min(1.0, 0.3 + 0.25 * sum(len(v) for v in attrs.values()))
    return attrs, conf
