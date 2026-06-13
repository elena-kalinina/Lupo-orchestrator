"""Escalate-vs-proceed policy — the core of the coordination layer, lifted straight
from Lupo's 3-way triage. For every decision the Coordinator faces, this returns:

  PROCEED  : act autonomously (clear, within budget, low taste-risk)
  CONFIRM  : do it but get a human yes first (side-effectful: spend money)
  ASK      : the agent is missing something only the human can supply (taste/ambiguity)

Getting this boundary right IS the hard, valuable part the challenge points at.
"""
PROCEED, CONFIRM, ASK = "proceed", "confirm", "ask"

# Side-effectful actions always need a human yes (cf. Lupo security gates).
SIDE_EFFECTFUL = {"purchase", "send_offer_real_seller", "confirm_handover"}


def decide(action, *, within_budget=True, taste_risk=False, missing_info=False,
           overspend=0.0):
    """Return one of PROCEED/CONFIRM/ASK with a short reason."""
    if missing_info or taste_risk:
        return ASK, "needs human taste/spec input"
    if action in SIDE_EFFECTFUL:
        return CONFIRM, "spends money / real-world action"
    if not within_budget:
        # Overspend: small auto-absorb, large -> ask the human to arbitrate.
        if overspend <= 0:
            return PROCEED, "within budget"
        if overspend <= 3:
            return PROCEED, f"minor overspend €{overspend:.0f} auto-absorbed"
        return ASK, f"overspend €{overspend:.0f} needs arbitration"
    return PROCEED, "clear and within budget"
