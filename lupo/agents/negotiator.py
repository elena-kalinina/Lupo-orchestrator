"""Negotiator (buyer-side) and Seller (simulated counterparty).

The autonomous buyer<->seller stress test the challenge asks for. Real-world note:
we negotiate against SIMULATED sellers seeded from a real listing's asking price —
never the real humans behind cached listings.

Both sides are deterministic policies in stub mode (so the demo runs offline and is
watchable). Hackathon upgrade: swap the policies for Gemini agents that reason about
strategy and justify offers in natural language.
"""
from .base import Agent


class Seller(Agent):
    role = "seller"

    def __init__(self, name, events, asking, reservation, persona="flexible"):
        super().__init__(name, events)
        self.asking = asking            # real listing price
        self.reservation = reservation  # lowest they'll accept (hidden)
        self.persona = persona          # firm | flexible | motivated

    def respond(self, offer):
        """Return (accept: bool, counter: float|None)."""
        if offer >= self.reservation:
            if self.persona in ("flexible", "motivated"):
                return True, None                      # happy at/above reservation
            if offer >= self.asking * 0.9:             # firm seller, near asking
                return True, None
            counter = round(max(self.reservation, (offer + self.asking) / 2), 0)
            return (False, counter) if counter > offer else (True, None)
        # below reservation -> counter toward asking
        counter = round(max(self.reservation, self.asking * 0.9), 0)
        return False, counter


class Negotiator(Agent):
    role = "negotiator"

    def haggle(self, listing, target, seller, max_rounds=4):
        """Try to acquire `listing` at or below `target`. Returns final price or None."""
        asking = listing["price"]
        offer = round(max(target * 0.85, asking * 0.7), 0)  # opening anchor
        self.emit("negotiation", text=f"open €{offer:.0f} on '{listing['title']}' "
                                      f"(ask €{asking:.0f}, target €{target:.0f})")
        for _ in range(max_rounds):
            accept, counter = seller.respond(offer)
            if accept:
                self.emit("deal", text=f"DEAL at €{offer:.0f} (saved €{asking-offer:.0f})")
                return offer
            seller.emit("negotiation", text=f"counter €{counter:.0f}")
            if counter <= target:
                self.emit("deal", text=f"DEAL at €{counter:.0f} (within target)")
                return counter
            # concede halfway toward the counter, but never above target+small margin.
            offer = round(min(counter, (offer + counter) / 2), 0)
            if offer > target * 1.1:
                self.emit("decision", text=f"walk away — €{offer:.0f} over target")
                return None
            self.emit("negotiation", text=f"raise to €{offer:.0f}")
        return None
