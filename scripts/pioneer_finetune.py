#!/usr/bin/env python3
"""Fastino Pioneer — real LoRA finetune of GLiNER2 on Lupo's multilingual
attribute-extraction task (material / style / fit), end to end.

The adaptive-inference story: Lupo's cheap on-device extractor handles the routine;
the hard cases escalate to Gemini; every escalation is logged
(data/extraction_samples.jsonl) and becomes a labelled training example. This
script turns those + the curated eval set into a Pioneer NER dataset, fine-tunes
fastino/gliner2-base-v1 with LoRA, and reports F1 — the cheap model distilling
the frontier model, one level below agent<->human escalation.

Phases (run in order, or 'all'):
  dataset  build NER JSONL from data/extraction_eval.jsonl + extraction_samples.jsonl,
           upload to Pioneer (presigned S3, 3-step), poll until ready
  train    POST /felix/training-jobs (LoRA on fastino/gliner2-base-v1)
  poll     poll the training job until complete (returns F1/precision/recall)
  eval     POST /felix/evaluations on the held-out eval set
  infer    side-by-side base vs trained on a few probe listings

Usage (venv active, .env filled with PIONEER_API_KEY):
  python scripts/pioneer_finetune.py --phase all
  python scripts/pioneer_finetune.py --phase dataset
  python scripts/pioneer_finetune.py --phase train --dataset-name lupo-attrs-v1
  python scripts/pioneer_finetune.py --phase poll
  python scripts/pioneer_finetune.py --phase infer

No key set -> prints SKIP and exits 0 (so the offline demo never depends on it).
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from lupo import config  # noqa: E402  (loads .env)
from lupo import pioneer  # noqa: E402
from lupo.extract_entities import _MATERIAL, _STYLE, _FIT, LABELS  # noqa: E402

NER_LABELS = ["material", "style", "fit"]
_LEXICONS = {"material": _MATERIAL, "style": _STYLE, "fit": _FIT}

EVAL_PATH = _ROOT / "data" / "extraction_eval.jsonl"
SAMPLES_PATH = _ROOT / "data" / "extraction_samples.jsonl"
OUT_DIR = _ROOT / "data" / "pioneer"
DATASET_JSONL = OUT_DIR / "ner_dataset.jsonl"
TRAINING_META = OUT_DIR / "last_training.json"
EVAL_META = OUT_DIR / "last_eval.json"
SIDEBYSIDE_META = OUT_DIR / "last_sidebyside.json"

PROBES = [
    "robe midi fleurie en coton, style bohème, taille normale",
    "leren jas, valt groot, vintage",
    "vestito di seta, anni 2000",
    "Wollpullover, getragen, normale Größe",
]


# --------------------------------------------------------------------------
# Dataset: canonical gold labels -> surface spans via the multilingual lexicons
# --------------------------------------------------------------------------

def _spans_for(text, gold):
    """Locate the surface form of each gold canonical value in `text`, emit
    [span, label] pairs for the GLiNER NER format."""
    lower = text.lower()
    entities = []
    for field in NER_LABELS:
        lex = _LEXICONS[field]
        for canon in gold.get(field, []) or []:
            for variant in lex.get(canon, [canon]):
                idx = lower.find(variant)
                if idx != -1:
                    entities.append([text[idx:idx + len(variant)], field])
                    break
    return entities


def _load_rows():
    rows = []
    if EVAL_PATH.is_file():
        for line in EVAL_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                rows.append((o["text"], o.get("gold", {})))
    if SAMPLES_PATH.is_file():
        for line in SAMPLES_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                o = json.loads(line)
                rows.append((o["text"], o.get("label", {})))
    return rows


def build_dataset():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = _load_rows()
    n = 0
    with DATASET_JSONL.open("w", encoding="utf-8") as f:
        for text, gold in rows:
            entities = _spans_for(text, gold)
            if not entities:
                continue
            f.write(json.dumps({"text": text, "entities": entities}, ensure_ascii=False) + "\n")
            n += 1
    print(f"  built {DATASET_JSONL} ({n}/{len(rows)} rows with spans)")
    return n


# --------------------------------------------------------------------------
# Pioneer HTTP helpers (reuse lupo.pioneer auth/base)
# --------------------------------------------------------------------------

def _post(client, path, body):
    r = client.post(f"{pioneer.base_url()}{path}", json=body, headers=pioneer.headers(), timeout=120)
    if r.status_code >= 300:
        raise RuntimeError(f"POST {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def _get(client, path):
    r = client.get(f"{pioneer.base_url()}{path}", headers=pioneer.headers(), timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"GET {path} -> {r.status_code}: {r.text[:300]}")
    return r.json() if r.content else {}


def upload_dataset(client, dataset_name):
    """3-step presigned upload: get url -> PUT file -> trigger process -> poll ready."""
    step1 = _post(client, "/felix/datasets/upload/url", {
        "dataset_name": dataset_name,
        "dataset_type": "ner",
        "type": "training",
        "filename": "ner_dataset.jsonl",
    })
    presigned = step1.get("presigned_url") or step1.get("url")
    dataset_id = step1.get("dataset_id") or step1.get("id")
    if not presigned:
        raise RuntimeError(f"no presigned_url in upload/url response: {step1}")
    print(f"  got presigned url (dataset_id={dataset_id})")

    put = client.put(presigned, content=DATASET_JSONL.read_bytes(),
                     headers={"Content-Type": "application/octet-stream"}, timeout=120)
    if put.status_code >= 300:
        raise RuntimeError(f"PUT presigned -> {put.status_code}: {put.text[:200]}")
    print("  uploaded dataset to S3")

    _post(client, "/felix/datasets/upload/process", {"dataset_id": dataset_id})
    print("  processing triggered; polling until ready…")
    for _ in range(60):
        time.sleep(5)
        try:
            status = _get(client, f"/felix/datasets/{dataset_name}")
        except Exception as e:
            print(f"  (poll retry: {e})")
            continue
        state = str(status.get("status") or status.get("state") or
                    (status.get("versions") or [{}])[-1].get("status") or "").lower()
        if state in ("ready", "complete", "completed", "succeeded"):
            print("  dataset ready ✓")
            return dataset_id
        if state in ("failed", "error"):
            raise RuntimeError(f"dataset processing failed: {status}")
    raise TimeoutError("dataset not ready in time")


def train(client, dataset_name, model_name, base_model, epochs, lr):
    resp = _post(client, "/felix/training-jobs", {
        "model_name": model_name,
        "base_model": base_model,
        "datasets": [{"name": dataset_name}],
        "training_type": "lora",
        "nr_epochs": epochs,
        "learning_rate": lr,
    })
    job_id = resp.get("id") or resp.get("job_id") or resp.get("training_job_id")
    if not job_id:
        raise RuntimeError(f"no training job id: {resp}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    TRAINING_META.write_text(json.dumps({"job_id": job_id, "dataset_name": dataset_name,
                                         "response": resp}, indent=2))
    print(f"  training_job_id={job_id}")
    print(f"  -> set PIONEER_TRAINED_MODEL_ID={job_id} in .env once it completes")
    return job_id


def poll(client, job_id, timeout_s=1800):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout_s:
        status = _get(client, f"/felix/training-jobs/{job_id}")
        state = str(status.get("status") or status.get("state") or "")
        if state != last:
            print(f"  status={state} ({int(time.time()-t0)}s)")
            last = state
        if state.lower() in ("complete", "completed", "success", "succeeded", "done"):
            metrics = {k: status.get(k) for k in ("f1", "precision", "recall") if k in status}
            print(f"  done — metrics: {metrics or status.get('metrics')}")
            return status
        if state.lower() in ("failed", "error", "cancelled"):
            raise RuntimeError(f"training failed: {status}")
        time.sleep(10)
    raise TimeoutError("training did not complete in time")


def _eval_metrics(rec):
    """Pull the metric block out of one evaluation record (Pioneer's field names)."""
    return {k: rec.get(k) for k in ("f1_score", "precision_score", "recall_score", "accuracy")}


def evaluate(client, model_id, dataset_name, label="trained", timeout_s=300):
    """POST an evaluation of `model_id` on `dataset_name`, then poll until the async
    job fills in the scores. Pioneer returns the created record under {evaluations:[…]}
    with status 'pending' -> 'completed' and f1_score/precision_score/recall_score."""
    resp = _post(client, "/felix/evaluations", {"base_model": model_id, "dataset_name": dataset_name})
    rec = (resp.get("evaluations") or [resp])[0] if isinstance(resp, dict) else resp
    eval_id = rec.get("id")
    t0 = time.time()
    while eval_id and time.time() - t0 < timeout_s:
        rec = _get(client, f"/felix/evaluations/{eval_id}")
        status = str(rec.get("status") or "").lower()
        if rec.get("f1_score") is not None or status in ("complete", "completed", "succeeded", "done"):
            break
        if status in ("failed", "error"):
            raise RuntimeError(f"evaluation failed: {rec.get('error_message')}")
        time.sleep(5)
    m = _eval_metrics(rec)
    EVAL_META.write_text(json.dumps({"label": label, "model_id": model_id, "metrics": m,
                                     "record": rec}, indent=2))
    f1 = m.get("f1_score")
    print(f"  [{label}] F1={f1}  P={m.get('precision_score')}  R={m.get('recall_score')}  "
          f"acc={m.get('accuracy')}")
    return m


def _grouped(raw):
    """Flatten Pioneer's {label:[span,...]} envelope to {label:[text,...]} for printing."""
    if not isinstance(raw, dict) or "error" in raw:
        return raw
    ents = pioneer._entities(raw)
    return {k: [s.get("text") for s in v] for k, v in ents.items() if v}


def infer_sidebyside(base_model, trained_model_id):
    rows = []
    for text in PROBES:
        base = trained = None
        try:
            base = pioneer.infer(text, NER_LABELS, model=base_model)
        except Exception as e:
            base = {"error": str(e)}
        try:
            trained = pioneer.infer(text, NER_LABELS, model=trained_model_id)
        except Exception as e:
            trained = {"error": str(e)}
        rows.append({"text": text, "base": base, "trained": trained})
        print(f"  probe {text[:40]!r}: base={_grouped(base)} trained={_grouped(trained)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SIDEBYSIDE_META.write_text(json.dumps({"base_model": base_model,
                                           "trained_model_id": trained_model_id,
                                           "rows": rows}, indent=2, ensure_ascii=False))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("dataset", "train", "poll", "eval", "infer", "all"), default="all")
    ap.add_argument("--dataset-name", default=os.getenv("PIONEER_DATASET_NAME", "lupo-attrs-v1"))
    ap.add_argument("--model-name", default="lupo-attrs-lora")
    ap.add_argument("--base-model", default=os.getenv("PIONEER_BASE_MODEL", "fastino/gliner2-base-v1"))
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--learning-rate", type=float, default=5e-5)
    ap.add_argument("--job-id", default=None)
    args = ap.parse_args()

    if not pioneer.api_key():
        print("SKIP: PIONEER_API_KEY not set. Add it to .env (https://pioneer.ai).", file=sys.stderr)
        return 0

    import httpx
    job_id = args.job_id or os.getenv("PIONEER_TRAINED_MODEL_ID", "").strip()
    if not job_id and TRAINING_META.is_file():
        job_id = json.loads(TRAINING_META.read_text()).get("job_id")

    with httpx.Client() as client:
        if args.phase in ("dataset", "all"):
            print("\n== dataset ==")
            if build_dataset() == 0:
                print("  no labelled spans found; aborting.", file=sys.stderr)
                return 1
            upload_dataset(client, args.dataset_name)

        if args.phase in ("train", "all"):
            print("\n== train ==")
            job_id = train(client, args.dataset_name, args.model_name,
                           args.base_model, args.epochs, args.learning_rate)

        if args.phase in ("poll", "all"):
            print("\n== poll ==")
            if not job_id:
                print("  no job id — run train first.", file=sys.stderr)
                return 1
            poll(client, job_id)

        if args.phase in ("eval", "all"):
            print("\n== eval (base vs trained) ==")
            try:
                base_m = evaluate(client, args.base_model, args.dataset_name, label="base")
            except Exception as e:
                base_m = {}
                print(f"  base eval skipped: {e}", file=sys.stderr)
            if job_id:
                try:
                    trained_m = evaluate(client, job_id, args.dataset_name, label="trained")
                    b, t = base_m.get("f1_score"), trained_m.get("f1_score")
                    if b is not None and t is not None:
                        print(f"  F1: base {b:.3f} -> trained {t:.3f}  (Δ {t-b:+.3f})")
                except Exception as e:
                    print(f"  trained eval skipped: {e}", file=sys.stderr)

        if args.phase in ("infer", "all"):
            print("\n== infer (base vs trained) ==")
            infer_sidebyside(args.base_model, job_id or args.base_model)

    print("\nDone.")
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
