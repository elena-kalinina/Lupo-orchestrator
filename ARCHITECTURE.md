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
  multilingual model (**GLiNER**, CPU, on-device) handles the routine extraction and
  classification; only the hard cases escalate to the **frontier multimodal model**
  (**Gemini**); and the frontier model's answers become training data that sharpens the
  small model over time (Fastino **Pioneer** adaptive inference). Cheap model ↔ frontier
  model mirrors agent ↔ human.
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
