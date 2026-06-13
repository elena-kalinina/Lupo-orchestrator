# Lupo — Architecture

![Lupo architecture](architecture.svg)

## One line
Lupo is a **coordination layer** that orchestrates a team of agents *and* a human to
finish a task at organisational scale. The shopping demo is one instantiation; the
architecture is domain-agnostic.

## The two parts of the diagram

**The domain-agnostic core (the product).** This is the part that doesn't change
between use cases:

- **Coordinator** — the orchestration layer and the star of the project. It doesn't
  shop, style, or haggle. It *coordinates*: routes work to agents, holds the shared
  ledger (the structured state every agent and the human read and write), runs the
  **escalate-vs-proceed policy** that decides when to act autonomously, when to confirm,
  and when to ask the human, and arbitrates conflicts over shared constraints (the budget).
- **Human-in-the-loop channel** — the human is the exec: they set the brief, own the
  taste calls, approve the budget split, and confirm anything that spends money. They're
  reached over a swappable channel (voice via Gemini TTS, WhatsApp, or a web panel) — the
  agent both *asks* for what it's missing and *instructs* the human (which tram, how much
  cash, which message to send).
- **Model arbitration** — the same escalate-vs-proceed idea one level down: a small, cheap,
  multilingual model (**GLiNER2**, via Fastino **Pioneer**) does the extraction; the hard
  cases escalate to the **frontier multimodal model** (**Gemini**); and the frontier model's
  answers become training data that sharpens the small model over time (Pioneer **adaptive
  inference**). On day 1 the escalation bar is set deliberately high (confidence < 0.99), so
  the un-tuned GLiNER2 escalates *aggressively* and we **harvest** every Gemini correction
  as a labelled row (`data/extraction_samples.jsonl`). Overnight, a LoRA fine-tune on those
  rows; on day 2 the sharpened model clears the bar itself and the **escalation rate drops** —
  that fall is the measurable win. Cheap model ↔ frontier model mirrors agent ↔ human.
- **Agent roster** — a swappable set of specialists the coordinator drives. In the demo:
  Stylist, Buyers, Procurement, Negotiator, and (simulated) Sellers.

**The swappable domain layer.** The tools and catalog the agents act on. In this demo it's
Vinted search over an outfit catalog with second-hand sellers and a €60–80 budget. Swap it
for RFQ/URS specs over a product catalog with industrial buyers and sellers, and the same
core runs technical sales — Atira's actual problem.

## Why it generalizes (the point for the video)
Every hard part of this system lives in the core, and the core makes no assumption about
fashion or shopping:

- *brief → machine-checkable spec* (Stylist) is a generic **spec compiler**;
- *act / confirm / ask-the-human* is a generic **escalation policy**;
- *allocate and arbitrate a shared budget* is generic **procurement**;
- *prove every requirement is satisfied or escalated* is generic **traceability**;
- *cheap model handles routine, frontier model handles the hard cases, escalations become
  training data* is generic **model arbitration**.

Change the roster and the domain layer — outfits to pumps, Vinted to RFQs, a wearer to a
procurement team — and the coordination layer is unchanged. That is the thesis the
challenge asks for: not a single agent calling tools, but the layer that coordinates agents
and humans together at organisational scale.

## The same idea at three scales
1. **Agent ↔ human** — the coordinator escalates taste and spend decisions to the exec.
2. **Cheap model ↔ frontier model** — GLiNER escalates hard extractions to Gemini.
3. **Buyer ↔ seller** — the negotiator and seller agents settle a deal autonomously.

One pattern — *do the routine, escalate the hard case, learn from the result* — repeated
at every level. That coherence is what makes it a layer, not a script.

## Model arbitration, made concrete (real outputs)
These are **actual** extractions from the demo's cached listings — Pioneer's hosted
GLiNER2 (`fastino/gliner2-base-v1`, zero-shot) vs the Gemini escalation. Second-hand
listings are multilingual and the base model reliably trips on the foreign *material*
words, which is exactly what the escalate-and-learn loop is for:

| Listing (lang) | GLiNER2 base — wrong | Gemini — corrected |
|---|---|---|
| `…Baggy Fit, oversized, Leder` (DE) | `Leder` (leather) → **style** *and* **brand**; `oversized` → size; **material empty** | material = **leather**; style = parachute/cargo/baggy |
| `Opus linnen jurk, boho, gedragen` (NL) | `boho` → **brand**; linen + "worn" **missed** | material = **linen**; style = dress |
| `Sandali platform neri chunky in pelle` (IT) | `pelle` (leather) → **colour**; `Sandali` → brand; `platform` → size | material = **leather**; style = platform/chunky |
| `Marc O Polo Leinenkleid` (DE) | `Leinenkleid` → **brand**; real brand **missed** | material = **linen**; style = office |

The pattern is consistent: the German `Leder` and Italian `pelle` (both *leather*) never
land in `material`, and the Dutch style word `boho` is read as a brand. Each Gemini
correction is logged as a training row (`lupo/samples.py`), and `scripts/pioneer_finetune.py`
LoRA-fine-tunes GLiNER2 on those rows — so the small model stops making the multilingual
mistake and fewer listings need to escalate. That is adaptive inference, shown not asserted.

### Before / after — a real LoRA fine-tune (not a mock)
We harvested every Gemini correction from the cached listings (`scripts/harvest_samples.py`
→ 31 labelled rows + the curated eval set = 38 training rows over `material`/`style`/`fit`),
uploaded them to Pioneer, and ran a real LoRA fine-tune of `fastino/gliner2-base-v1`. Both
models were then scored on the **same held-out eval set** via Pioneer's evaluations API:

| Model | F1 | Precision | Recall | Accuracy |
|---|---|---|---|---|
| GLiNER2 base (`fastino/gliner2-base-v1`) | 0.188 | 0.150 | 0.250 | 0.602 |
| **+ LoRA fine-tune** (job `b8210478…`) | **0.267** | 0.222 | 0.333 | 0.667 |

That's **+0.079 F1 (≈ +42% relative)** from ~40 harvested rows — the cheap model measurably
distilling the frontier model, one level below the agent↔human escalation. The trained job
id is wired into `.env` (`PIONEER_TRAINED_MODEL_ID`) so live inference routes to it; reproduce
with `python3 scripts/pioneer_finetune.py --phase all` (full result in `data/pioneer/result.json`).
