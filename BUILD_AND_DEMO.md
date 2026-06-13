# Lupo — Build Plan, Demo Script & Challenge Fit

## Why this wins the challenge (read this first)
The challenge dismisses "single agents calling tools" and asks for **the layer that
coordinates agents AND humans at organisational scale**. Lupo's centre of gravity is
exactly that layer (`coordinator.py` + `policy.py` + `ledger.py`), not the shopping.
Keep the pitch on the coordination layer; the outfit is just the legible demo.

| Challenge phrase | Where Lupo delivers it |
|---|---|
| coordinates agents **and humans** | Coordinator + HumanChannel; 3 human touchpoints (approve, arbitrate, confirm) |
| **organisational** scale | an org: stylist, buyers, procurement, negotiator, sellers — with a procurement function arbitrating a shared budget |
| structured knowledge across teams | the shared mission ledger |
| buyer & seller agents negotiating autonomously | Negotiator ↔ simulated Seller, end-to-end haggle |
| proactively ask **and instruct** the human | escalations + the tram/cash/handover instruction |
| the hard part technically | escalate-vs-proceed boundary + budget arbitration |

## 2-day build plan (the runnable skeleton is already done & tested)
The offline skeleton runs end-to-end now. The two days are about making it real and
making it shine — in this order, cutting from the bottom under time pressure.

**Day 1 — make it real**
1. Vinted live: wire your `vinted_agent` token-hack client into `vinted/client.py::_search_live`; run real searches once to populate `data/vinted_cache/`. Keep replay as default.
2. Gemini stylist: `agents/stylist.py::_real_spec` — brief → structured spec.
3. Gemini **vision** in `buyer.py::_fit` — judge style match from the listing PHOTO (the multimodal win; replaces the keyword stub).
4. Real human channel: implement `WhatsAppChannel` (Twilio sandbox) + a tiny web panel; keep `ScriptedChannel` as the live-demo fallback.

**Day 2 — make it shine + harden**
5. Gemini-driven negotiation: swap the deterministic policies in `negotiator.py` for agents that reason and justify offers in natural language (both buyer and seller).
6. Canvas polish: `frontend/canvas.html` already replays the event stream; wire it to live `events.jsonl` and add the phone-buzz moment (canvas + WhatsApp fire together).
7. fal lookbook: render a flat-lay composite of the final outfit for the close.
8. Aikido scan of the repo + container; screenshot the clean pass for the security slide.
9. Freeze. Rehearse 3×. Pre-record a `--live` Vinted call as proof; demo off cache.

## Cut-list (drop bottom-up under pressure)
fal lookbook → Gemini NL negotiation (keep deterministic) → web panel (keep WhatsApp OR scripted) → Vinted live (keep cache). **Never cut:** the Coordinator, the escalate-vs-proceed gates, the budget arbitration, the negotiation, the canvas. That's the thesis.

## Demo script (~2 min)
- **0:00 Hook.** "A real RFQ for an outfit: brunch with the girls, €60. Watch an *org* of agents and a human pull it off — and catch a budget trap on the way." Open the canvas.
- **0:15** Stylist proposes the vision → **your phone buzzes**: approve? You reply *"ballet flats, small shoulder bag."* The spec updates live on the canvas. (agents + human, taste loop.)
- **0:40** Procurement allocates €60. Buyers shop real Vinted listings in parallel.
- **0:55 The peak.** The dress everyone loves is €32 — €8 over. The Coordinator doesn't greedily raid other categories; it **escalates with portfolio reasoning** and pings you: negotiate or stretch? You say *negotiate*.
- **1:10** Watch the **buyer agent haggle a seller agent** live: €24 → counter €29 → €26, deal. "Listings and prices are real from Vinted; the counterparty is a simulated seller seeded from the real ask."
- **1:30** Outfit reassembles at €58/€60. The traceability view proves every component is accounted for. You **confirm the purchase** (gated). 
- **1:45 Close + the instruct beat.** Coordinator texts you: "U3/U6 to Universität, grab €58 cash, here's your pickup message." → "One human kept the taste and the final yes; the org did everything else. **This is the coordination layer — swap the roster and it's industrial procurement.**"

## Demo-safety
- Default to cached Vinted + scripted human; both real backends are behind toggles you can drop in seconds (`LUPO_VINTED_LIVE`, `LUPO_HUMAN_CHANNEL`).
- Never negotiate against real people — sellers are simulated, seeded from real prices.
- Treat seller/listing text as untrusted (prompt-injection surface); real purchases are gated.

---

## Prize plays (Gemini qualifies; these add cash without breaking the core)

**Voice ping (Gemini 3.1 Flash TTS).** `LUPO_HUMAN_CHANNEL=voice` speaks each
escalation aloud — a cheeky multilingual line ("[wry] in Russian/German"). One API
call → audio (or a WhatsApp voice note). Offline it prints the line. `human/channel.py::VoiceChannel`.

**Fastino prize — GLiNER multilingual extraction + Pioneer finetune.**
`extract_entities.py` pulls material/style/fit out of the messy FR/NL/EN/IT/DE listing
text (the fields sellers never fill in). Low-confidence listings **escalate to Gemini**;
those become training samples (`samples.py`). `scripts/finetune_gliner.py` scores the
baseline vs a Pioneer-finetuned model on `data/extraction_eval.jsonl` (before→after).
Multilingual is native to GLiNER (multilingual DeBERTa backbone, cross-lingual transfer);
keep the label set under ~30 types (we use 7).

**Aikido prize — most secure build.** Scan repo + container; fix findings. Present the
two-layer story: Aikido = supply chain/runtime; architecture = injection surface
(seller/listing text is untrusted — GLiNER can even flag injection-like strings before
they reach Gemini). Two layers, kept distinct.

**The one-story through-line:** every layer is the same arbitration — cheap model ↔
frontier model (GLiNER ↔ Gemini), and agent ↔ human — with escalations becoming
training data. One idea at three scales.

## New commands
```bash
LUPO_HUMAN_CHANNEL=voice python3 scripts/run_mission.py   # mission with spoken pings
python3 scripts/finetune_gliner.py                        # GLiNER before/after harness
```

## Dropped / stretch
- Gemma-generates-API-calls: dropped (riskiest, lowest payoff; not needed for the prize).
- Live API full-duplex voice (Tier B): stretch only; the one-way TTS ping is the safe win.

---

## Scenarios (two contrasting coordination behaviours)
Both add a **budget-split confirmation** gate (the human signs off the allocation before any shopping), then diverge on how an over-budget hero item is resolved:

| Scenario | Budget | Hero conflict | Human choice | Coordination move |
|---|---|---|---|---|
| `brunch` | €60 | dress €32 vs €24 | **negotiate** | Negotiator haggles seller €32→€26 |
| `tomorrowland` | €80 | boots €40 vs €24 | **stretch** | Procurement **reallocates** €16 of slack from other categories → boots; total stays €80 |

```bash
LUPO_SCENARIO=brunch        python3 scripts/run_mission.py
LUPO_SCENARIO=tomorrowland  python3 scripts/run_mission.py
```

## Demo visuals
- `frontend/walkthrough.html` — narrated, self-contained storyboard with a scenario
  switcher. Voice shown as text, Vinted finds as described multilingual cards, explicit
  "running X search" beats, the budget-confirm gate, and negotiate-vs-reallocate. Best
  for rehearsing the pitch (opens on double-click, no server).
- `frontend/canvas.html` — the LIVE view: replays `data/events.jsonl`, now renders the
  `candidates` events as the same rich find-cards. Budget ring scales to the scenario.

---

## Latest additions
- **Per-item logistics.** Finds come from sellers in different countries. Most ship
  (paid online); only a genuinely local seller becomes an in-person pickup — for that
  one item's cash, not the whole basket. (`coordinator._logistics`, seller `country` in fixtures.)
- **Voice variety.** `VoiceChannel` rotates tone + language per ping
  (hyped/dry/wry/deadpan/theatrical/breezy × Russian/German/English) with a funny quip.
- **Real integrations behind toggles** (`lupo/llm.py`): Gemini structured output (stylist,
  extraction escalation), Gemini TTS (voice), and GLiNER (`urchade/gliner_multi-v2.1`).
  Each falls back to the stub on any error, so flipping a toggle can't crash the demo.
  Verify with keys + a live run on the day.
- **Canvas images.** The live canvas renders listing photos (real Vinted URLs in the
  demo; placeholder for the fixtures) and the seller country on each find-card.
- **Walkthrough Live tab.** `frontend/walkthrough.html` now has brunch / Tomorrowland /
  **Live run**. Live replays `data/events.jsonl` through the same renderer — serve the
  folder (`python3 -m http.server`) so the browser can fetch it.
- **Architecture.** `frontend/architecture.svg` + `ARCHITECTURE.md` — the domain-agnostic
  core vs swappable domain layer, for the video submission.
