# Lupo — video script (~85s, trims to 60s)

Two-voice columns: **[SCREEN]** what to show · **[VO]** what you say. Total ≈ 85s.
Demo centres on **Tomorrowland** (the reallocation beat) because it's the headline
coordination move and matches the Live tab; brunch's negotiation gets a one-line nod.

Assets: `frontend/architecture.svg`, `frontend/canvas.html` (or `walkthrough.html` →
Live), `data/events_tomorrowland.jsonl` (already loaded as `events.jsonl`).

---

### 0:00–0:10 · Hook + the problem
- **[SCREEN]** Architecture diagram, dimmed except the title.
- **[VO]** "Most AI agents today are one model calling tools. The hard part — and the real value — is the *layer above*: coordinating a team of agents and a human together, at organizational scale. That's Lupo."

### 0:10–0:28 · The architecture (the thesis)
- **[SCREEN]** `architecture.svg`. Point to the dashed **core**, then the **domain layer**.
- **[VO]** "At the centre is a Coordinator — it doesn't shop or haggle, it *routes*, holds the shared state, and runs one policy: act, confirm, or ask the human. Around it, a swappable roster of agents, a human reachable by voice or chat, and a model-arbitration loop — a cheap on-device model does the routine, the frontier model handles the hard cases. Everything domain-specific lives in one swappable layer at the bottom."

### 0:28–1:05 · Live demo (Tomorrowland)
- **[SCREEN]** Canvas/Live replay. Let it play; narrate the beats.
- **[VO]**
  - "Brief: a Tomorrowland outfit, eighty euros. The stylist proposes a look —" *(vision appears)* "— and pings me. I tweak it: mesh top, more sparkle."
  - "It proposes a budget split across the four pieces, and I approve it." *(budget bar)*
  - "Then it shops Vinted in parallel. These listings are real — French, Dutch, Italian, German — and a small model pulls material, style and fit out of the messy text. On the German listing it misreads *Leder* — leather — as a style," *(point to a GLiNER→Gemini tag)* "so it escalates to Gemini, which corrects it to material: leather. That correction becomes training data for the small model."
  - "Now the interesting part: the platform boots are the hero of the look, but ten euros — four over their slice. It asks me: negotiate, or stretch? I say stretch —" *(reallocation line)* "— and Procurement *reallocates* four euros of slack from the other categories. Total stays at twenty. Nothing overspent."
  - *(optional, play audio)* a funny voice ping: "[hyped, German] Die Boots sind der Star — strecken wir das Budget?"
  - "Final beat: the finds are from four sellers in four countries. So three ship — paid online — and only the local Munich pair becomes an in-person pickup, with the tram and the cash for *that* item."
- **[VO, one line]** "In the brunch run, the same conflict ends differently — it haggles the seller down instead."

### 1:05–1:18 · One pattern, three scales (+ partners)
- **[SCREEN]** Architecture, highlight the arbitration loop.
- **[VO]** "It's the same move at every level: do the routine, escalate the hard case, learn from the result. Agent to human. Cheap model to Gemini. Buyer to seller. Built on Gemini, a fine-tuned GLiNER from Fastino, secured with Aikido."

### 1:18–1:30 · Close — swap the domain
- **[SCREEN]** Architecture; the swap arrow from "consumer" to "industrial" pulses.
- **[VO]** "The core never changes. Swap the roster and the catalog, and this outfit shopper becomes industrial technical sales — RFQs, product catalogs, buyers and sellers. The coordination layer is the product. The outfit was just the demo."

---

## 60s trim
- Cut the partners line (1:05–1:18) to a 3s tag: "Gemini, a fine-tuned GLiNER, Aikido."
- Compress architecture (0:10–0:28) to ~12s: core vs swappable layer only.
- Keep the full demo and the swap close — they carry the message.

## Production notes
- Record the demo with `walkthrough.html` → **Live run** (replays `events.jsonl`,
  currently Tomorrowland) or `canvas.html`. Serve the folder so the Live fetch works:
  `python3 -m http.server` then open `frontend/walkthrough.html`.
- For the audio ping, generate one real line with Gemini TTS (`USE_REAL_VOICE=1`) and
  drop it over the escalation beat — the laugh lands.
- To demo brunch's negotiation instead, copy `data/events_brunch.jsonl` over
  `data/events.jsonl` before recording.
