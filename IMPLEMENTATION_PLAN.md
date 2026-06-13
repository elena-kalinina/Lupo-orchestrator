# Lupo — Implementation Plan (hackathon day)

A step-by-step checklist to take the repo from "runs fully offline" to "as real as you
want it for the demo." It assumes **no prior context**. Do the steps in order. After
**every** step the offline demo must still work — that's your safety net, so never
delete the fixtures or the stub code paths.

Golden rule: **every real integration is behind a toggle and falls back to the stub on
error.** If a toggle misbehaves on stage, turn it off and the demo still runs.

---

## 0. What you're starting with
- A Python package `lupo/` (the coordination engine), a `data/` folder of cached inputs,
  a `frontend/` folder of HTML/SVG visuals, `scripts/` to run things, and `tests/`.
- It runs with **no API keys and no network**: cached Vinted listings, a scripted human,
  and rule-based agent stubs. Real models/services switch on via environment variables.

You need: **Python 3.10+**, a terminal, and (for the real bits) a Gemini API key and
your existing `vinted_agent` client.

---

## 1. Set up and verify the offline demo (do this first)
```bash
cd lupo-orchestrator
python3 -m venv .venv && source .venv/bin/activate      # optional but recommended
pip install -r requirements.txt                          # if a managed env complains, add: --break-system-packages
```
Verify it works end-to-end, both scenarios:
```bash
python3 scripts/run_mission.py                           # brunch (€60, negotiate)
LUPO_SCENARIO=tomorrowland python3 scripts/run_mission.py # tomorrowland (€80, reallocate)
python3 tests/test_mission.py                            # should print OK / no failures
```
Expected: a readable event log ending in a traceability table, and `data/events.jsonl`
written. Open the visuals (just double-click the files):
- `frontend/canvas.html` — the live coordination canvas (your recording surface). Use the
  **Brunch / Tomorrowland** buttons at the top.
- `frontend/walkthrough.html` — the narrated storyboard.

If all of that works, you can demo **right now**. Everything below makes it more real.

---

## 2. (Recommended) Wire real Vinted photos
Goal: the canvas cards show real Vinted photos and prices instead of placeholders.

### 2a. Implement the live search
Open `lupo/vinted/client.py` and fill in `_search_live(query, limit)`. It must return a
list of dicts in **exactly this shape** (the rest of the system depends on these keys):
```python
{
  "id": "<vinted item id>",        # string/unique
  "title": "...",                  # listing title
  "desc": "...",                   # description (keep it multilingual — that's the point)
  "price": 32,                     # number, in EUR
  "size": "M",
  "brand": "Zara",
  "seller_id": "...",
  "photo": "https://...jpg",       # a real image URL  <-- this is what shows on the cards
  "country": "France",             # seller country (drives ship-vs-local-pickup)
  "url": "https://www.vinted.../items/...",
  # optional: "persona": "flexible" | "firm" | "motivated"  (affects the negotiation sim)
}
```
Use your `vinted_agent` repo here: it already gets `access_token_web` from the site
cookies and calls `/api/v2/catalog/items`. Steps inside `_search_live`:
1. import your client (e.g. `from vinted_agent import VintedClient`),
2. `GET /api/v2/catalog/items?search_text=<query>&per_page=<limit>` with the token,
3. set a real `User-Agent` and refresh the token if it 401s (Cloudflare/expiry),
4. map each API item to the dict above (don't forget `photo` and `country`).

### 2b. Cache for the exact demo queries
The demo issues specific queries (e.g. `mesh sparkle top neon`). This script enumerates
them for you and pulls real listings:
```bash
# DEMO-SAFE (default): keep curated prices/country/persona, only swap in real photos+urls
python3 scripts/cache_vinted.py

# or FULLY REAL (overwrites fixtures; re-check that prices still trigger the over-budget beat)
python3 scripts/cache_vinted.py --full
```
Then re-run the mission and open the canvas — the cards now show real images.
**Recommendation:** use the default (photos-only). It keeps the negotiate / reallocate /
pickup beats intact while making the pictures real. Use `--full` only if you have time to
re-tune the numbers.

Fallback: if you can't get the live client working in time, do nothing — the placeholders
are fine and the demo still runs.

---

## 3. (Optional) Enable Gemini (stylist + extraction escalation)
```bash
pip install google-genai            # add --break-system-packages if needed
export GEMINI_API_KEY=sk-...         # your key
export USE_REAL_GEMINI=1
```
**Verify the model string first.** Open `lupo/llm.py` and confirm `GEMINI_TEXT_MODEL`
points at a model your key can call (the code defaults to `gemini-2.5-flash`; update it
if the current name differs). Then:
```bash
python3 scripts/run_mission.py
```
What changes: the **stylist** builds the outfit spec via Gemini structured output, and any
listing the small extractor is unsure about is **escalated to Gemini**. If a call errors,
the code logs it and falls back to the stub automatically — the run won't crash.

---

## 4. (Optional) Enable real GLiNER (multilingual extraction)
```bash
pip install gliner                  # pulls torch; first run downloads the model (~hundreds of MB)
export USE_REAL_GLINER=1
python3 scripts/run_mission.py
```
What changes: instead of the keyword stub, the real `urchade/gliner_multi-v2.1` model
extracts material/style/fit/etc. from the multilingual listing text. First run is slow
(model download + CPU inference). If it fails or is too slow on the demo machine, unset
`USE_REAL_GLINER` and the keyword stub takes over. (Set a different model with
`GLINER_MODEL=...`.)

---

## 5. (Optional) Enable the voice ping (Gemini TTS)
```bash
export USE_REAL_VOICE=1
export LUPO_HUMAN_CHANNEL=voice
python3 scripts/run_mission.py
```
What changes: each human ping is spoken aloud via Gemini TTS, with a rotating tone +
language (hyped Russian, dry German, wry English, …). It writes a WAV per ping. **Verify
the TTS model name** in `lupo/llm.py` (`GEMINI_TTS_MODEL`, defaults to
`gemini-2.5-flash-preview-tts`) against what your key supports. For the video, record one
good ping and lay it over the boots-escalation beat. If TTS misbehaves, unset the toggle
and the pings print as styled text (still demo-friendly).

---

## 6. (Optional, for the Fastino prize) GLiNER finetune metrics
```bash
python3 scripts/finetune_gliner.py
```
Produces before/after extraction metrics on `data/extraction_eval.jsonl`. For a *real*
finetune story, point it at Fastino Pioneer using the escalation samples Lupo logs to
`data/extraction_samples.jsonl` during runs (every GLiNER→Gemini escalation becomes a
labelled training example — that's the adaptive-inference loop). Keep the harness as the
demo-safe fallback if a live finetune isn't ready.

---

## 7. (Optional, for the Aikido "most secure" prize)
Run Aikido's scanner over the repo (SCA/SAST/secrets/container) and capture the clean
report. Note for the pitch: prompt-injection resistance is handled by the *architecture*
(the Coordinator validates and the human confirms side-effectful actions); Aikido covers
the supply chain and runtime.

---

## 8. Record the video
1. Decide the scenario. **Tomorrowland** shows the reallocation (recommended); **brunch**
   shows live negotiation. Both are buttons in `frontend/canvas.html`.
2. If you want the Live tab to replay a *real* run instead of the embedded one, run that
   scenario and serve the folder so the browser can fetch the log:
   ```bash
   LUPO_SCENARIO=tomorrowland python3 scripts/run_mission.py
   cd frontend && python3 -m http.server 8000      # then open http://localhost:8000/canvas.html
   ```
3. Read `VOICEOVER.md` while screen-recording: architecture diagram first (~22s), then the
   canvas (~50s), then the swap close (~13s).

---

## 9. Package and submit
```bash
cd .. && zip -r lupo-submission.zip lupo-orchestrator -x '*.pyc' -x '*__pycache__*'
```
Submit: the video, `frontend/architecture.svg` (the diagram), and the zip / repo link.

---

## Final pre-demo checklist
- [ ] `python3 tests/test_mission.py` passes.
- [ ] Both scenarios run and end with a traceability table.
- [ ] Canvas opens; Brunch and Tomorrowland buttons both play to the end.
- [ ] If using real toggles: each one tested once, and you know how to turn it off fast.
- [ ] Photos: either real (cache script ran) or placeholders (fine) — no broken state.
- [ ] `events.jsonl` is the scenario you'll show on the Live tab (re-run if needed).
- [ ] VOICEOVER.md open on a second screen.
