# Lupo

**A coordination layer for agents *and* humans.**

Most AI agents today are a single model calling tools. The interesting, valuable problem
is the layer *above*: coordinating a whole team of agents **and** a person to finish a job
at organisational scale — deciding what to do autonomously, what to confirm, and what to
escalate, while keeping shared state and a budget coherent.

Lupo is that layer. The demo instantiates it as a **personal-shopper org** that assembles
an outfit on Vinted within a budget — but the shopping is just a skin. The core is
domain-agnostic: swap the agent roster and the catalog and the same engine runs
**industrial technical sales** (RFQ → quote), which is the same shape of problem.

---

## What it does (the demo)
You give a brief and a budget. A team of agents — coordinated by a **Coordinator** — styles
an outfit, shops for each piece across multilingual Vinted listings, settles each item
against its budget, and hands you a plan. You stay in the loop at the decisions that matter.

Two scenarios ship, chosen to show two *different* coordination behaviours:

| Scenario | Budget | The conflict | Your choice | What the org does |
|----------|--------|--------------|-------------|-------------------|
| **brunch** | €60 | the standout dress is €8 over its slice | **negotiate** | the Negotiator haggles the seller €32 → €26 |
| **tomorrowland** | €80 | the hero boots are €16 over their slice | **stretch** | Procurement **reallocates** slack from other categories; total stays €80 |

Three human checkpoints in every run: approve the **vision** (with amendments), approve the
**budget split**, and **confirm** the purchase. The finish is per-item logistics: items from
foreign sellers ship (paid online); only a genuinely local seller becomes an in-person
pickup, with the tram and the exact cash for *that* item.

Everything runs **fully offline and deterministic** by default — cached real listings, a
scripted human, rule-based agent stubs — so the demo never depends on a key or the network.
Real models and services switch on behind toggles.

---

## Quick start
```bash
pip install -r requirements.txt        # only needed for the real integrations; stub mode is stdlib-only
python3 scripts/run_mission.py                              # brunch
LUPO_SCENARIO=tomorrowland python3 scripts/run_mission.py   # tomorrowland
python3 tests/test_mission.py                               # smoke tests
```
Then open the visuals (double-click):
- **`frontend/canvas.html`** — the live coordination canvas. Roster, the coordination
  stream (escalations + your replies), a budget ring, and the outfit filling in. Scenario
  buttons at the top (Brunch / Tomorrowland / Live). *This is the recording surface.*
- **`frontend/walkthrough.html`** — a narrated storyboard of the same run.
- **`frontend/architecture.svg`** — the architecture diagram (for the video).

To finalise the real integrations on hackathon day, follow **`IMPLEMENTATION_PLAN.md`**.

---

## Architecture
See **`ARCHITECTURE.md`** (and `frontend/architecture.svg`) for the full picture. In short:

**The domain-agnostic core** (never changes between use cases):
- **Coordinator** — the star. Routes work to agents, holds the shared **ledger** (the
  structured state everyone reads/writes), runs the **escalate-vs-proceed policy** (act /
  confirm / ask the human), and arbitrates conflicts over the shared budget.
- **Human-in-the-loop channel** — the human is the exec: sets the brief, owns taste,
  approves spend. Reachable over a swappable channel (voice via Gemini TTS, WhatsApp, web).
- **Model arbitration** — a cheap, multilingual, on-device model (**GLiNER**) handles the
  routine extraction; only hard cases escalate to a frontier model (**Gemini**); the
  frontier answers become training data that sharpens the small model (Fastino **Pioneer**).
- **Agent roster** (swappable) — Stylist, Buyers, Procurement, Negotiator, Sellers.

**The swappable domain layer** — the tools + catalog. Here: Vinted search over an outfit
catalog. Swap it for RFQ/URS specs over a product catalog and the core runs technical sales.

**The same pattern at three scales** — *do the routine, escalate the hard case, learn from
the result*: agent ↔ human, cheap model ↔ frontier model, buyer ↔ seller. That coherence is
what makes it a layer, not a script.

---

## Project structure
```
lupo-orchestrator/
├── lupo/                       # the coordination engine (Python, stdlib-only in stub mode)
│   ├── coordinator.py          # ★ routes work, holds the ledger, runs escalate-vs-proceed,
│   │                           #   arbitrates the budget, drives the human checkpoints + logistics
│   ├── policy.py               # the escalate-vs-proceed policy (PROCEED / CONFIRM / ASK)
│   ├── ledger.py               # shared mission state: Component dataclass + budget ledger
│   ├── events.py               # EventStream -> data/events.jsonl (feeds the canvas) + console echo
│   ├── extract_entities.py     # multilingual attribute extraction; GLiNER stub + real, Gemini escalation
│   ├── llm.py                  # real integrations: Gemini structured output + Gemini TTS (behind toggles)
│   ├── samples.py              # logs GLiNER→Gemini escalations as training samples (Pioneer loop)
│   ├── config.py               # the toggles (all off = offline deterministic demo)
│   ├── agents/
│   │   ├── base.py             # Agent base (emits events)
│   │   ├── stylist.py          # brief -> outfit spec (rule-based stub or Gemini); amendments
│   │   ├── buyer.py            # searches Vinted, runs extraction, emits structured candidates
│   │   ├── procurement.py      # budget allocation + reallocation (stretch)
│   │   └── negotiator.py       # Negotiator.haggle + a simulated Seller by persona
│   ├── human/
│   │   └── channel.py          # HumanChannel: Scripted (offline), Voice (Gemini TTS), WhatsApp, Web, Email
│   ├── missions/
│   │   └── shopping.py         # SCENARIOS (brunch, tomorrowland), run(), traceability()
│   └── vinted/
│       └── client.py           # Vinted search with record/replay; _search_live = your client (hackathon day)
├── data/
│   ├── vinted_cache/*.json     # cached real listings per query (record/replay)
│   ├── events.jsonl            # latest run (the canvas Live tab reads this)
│   ├── events_brunch.jsonl     # stable per-scenario snapshots
│   ├── events_tomorrowland.jsonl
│   └── extraction_eval.jsonl   # labelled multilingual examples for the GLiNER finetune harness
├── frontend/
│   ├── canvas.html             # live coordination canvas (recording surface)
│   ├── walkthrough.html        # narrated storyboard (brunch / tomorrowland / live)
│   └── architecture.svg        # the architecture diagram
├── scripts/
│   ├── run_mission.py          # run a scenario (LUPO_SCENARIO=brunch|tomorrowland)
│   ├── cache_vinted.py         # cache real listings for the exact demo queries (real photos)
│   └── finetune_gliner.py      # GLiNER before/after metrics (Fastino prize)
├── tests/test_mission.py       # smoke tests (under budget, amendment applied, negotiation saved money)
├── ARCHITECTURE.md             # the design + why it generalises (video material)
├── IMPLEMENTATION_PLAN.md      # step-by-step to finalise the real integrations
├── VIDEO_SCRIPT.md / VOICEOVER.md   # the submission video script and read-aloud narration
├── BUILD_AND_DEMO.md           # plan, demo script, challenge-fit map, prize plays
└── requirements.txt
```

---

## Configuration (toggles)
Everything off ⇒ fully offline, deterministic. Each real path falls back to the stub on error.

| Variable | Default | Effect |
|----------|---------|--------|
| `LUPO_SCENARIO` | `brunch` | which mission to run (`brunch` \| `tomorrowland`) |
| `USE_REAL_GEMINI` | `0` | stylist spec + extraction escalation via Gemini |
| `USE_REAL_GLINER` | `0` | real `urchade/gliner_multi-v2.1` extraction (else keyword stub) |
| `USE_REAL_VOICE` | `0` | speak human pings via Gemini TTS (rotating tone/language) |
| `LUPO_HUMAN_CHANNEL` | `scripted` | `scripted` \| `voice` \| `whatsapp` \| `web` |
| `LUPO_VINTED_LIVE` | `0` | call the real Vinted client and cache (else replay fixtures) |
| `GLINER_ESCALATION_THRESHOLD` | `0.55` | below this confidence, a listing escalates to Gemini |
| `GEMINI_API_KEY` | — | required when `USE_REAL_GEMINI` / `USE_REAL_VOICE` are on |

Model names live in `lupo/llm.py` (`GEMINI_TEXT_MODEL`, `GEMINI_TTS_MODEL`) — verify them
against your key before the demo.

---

## Partners & prizes
- **Gemini** (qualifying) — structured outputs (stylist, extraction escalation) and TTS
  (the voice pings); the arbitration target for hard cases.
- **Fastino / GLiNER** — the small multilingual extractor; **Pioneer** for fine-tuning on
  Lupo's own escalation traces (adaptive inference). Metrics harness: `scripts/finetune_gliner.py`.
- **Aikido** — supply-chain/runtime security scan for the "most secure build" prize;
  prompt-injection resistance is handled by the architecture (Coordinator validates, human confirms).

---

## Testing
```bash
python3 tests/test_mission.py
```
Covers: the outfit lands under budget, the human amendment is applied, the negotiation
saved money, and the event stream is produced.

---

## Why this answers the challenge
The brief asks for more than a single agent calling tools — it asks for the layer that
coordinates agents and humans together at organisational scale. Every hard part here lives
in the core and assumes nothing about fashion: a spec compiler (Stylist), an escalation
policy (Coordinator), shared-budget procurement, traceability, and model arbitration.
Change the roster and the domain layer, and the outfit shopper becomes industrial
procurement. **The coordination layer is the product; the outfit is just the demo.**
