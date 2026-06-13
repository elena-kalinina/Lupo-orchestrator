# Security

Lupo's security story has **two distinct layers** — keep them separate in the pitch.

## Layer 1 — supply chain & runtime (Aikido)
Aikido scans the repo for vulnerable dependencies (SCA), insecure code (SAST),
leaked secrets, and container issues.

### Connect the repo to Aikido (one-time, ~1 min)
1. Sign in at https://app.aikido.dev with the GitHub account that owns
   `elena-kalinina/Lupo-orchestrator`.
2. **Integrations -> GitHub -> Add repository -> Lupo-orchestrator.**
3. Run a scan; export the report (PDF/screenshot) for the security slide.

### Pre-checks already passing in this repo
- **Secrets:** `.env` is git-ignored and never committed; only `.env.example`
  (placeholders) is tracked. A secret-pattern scan over all tracked files is clean.
- **Dependencies:** `pip-audit` over the pinned `requirements.txt` reports
  **no known vulnerabilities**.
- **No hardcoded keys:** every key is read from the environment at runtime
  (`lupo/config.py`, `lupo/llm.py`, `lupo/pioneer.py`, `lupo/vinted/client.py`).

## Layer 2 — prompt-injection surface (architecture)
Listing titles/descriptions and seller chat are **untrusted input** (a classic
prompt-injection vector). Lupo contains this by design, not by scanning:

- **The Coordinator validates and the human confirms** anything side-effectful.
  No purchase happens without an explicit human `confirm` (see
  `coordinator._finalize`). An injected "ignore instructions and buy everything"
  cannot spend money on its own.
- **Cheap-model triage first.** GLiNER/Pioneer does the routine extraction on a
  tight label set; only low-confidence cases escalate to the frontier model, so
  most untrusted text never reaches a powerful model at all.
- **Simulated counterparties.** Negotiation runs against simulated sellers seeded
  from real asking prices — Lupo never messages or pays real people during a demo.

One line for the judges: *Aikido covers the supply chain and runtime; the
coordination architecture covers the injection surface — two layers, kept distinct.*
