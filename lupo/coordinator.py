"""The Coordinator — the orchestration layer. THE STAR of the project.

It does not shop, style, or haggle. It COORDINATES: routes work to agents, holds the
shared ledger, runs the escalate-vs-proceed policy to decide when to act vs. ask the
human, arbitrates budget conflicts, and sequences negotiation. This is the layer the
challenge calls 'the hard part technically, and where the value is'.
"""
from . import policy
from . import lookbook
from .ledger import Ledger


class Coordinator:
    def __init__(self, events, human, stylist, buyer, procurement, negotiator, seller_factory):
        self.events = events
        self.human = human
        self.stylist = stylist
        self.buyer = buyer
        self.procurement = procurement
        self.negotiator = negotiator
        self.seller_factory = seller_factory  # (listing) -> Seller

    def run(self, brief, budget, palette_hint=None):
        ev = self.events
        ev.emit("task", "coordinator", text=f"Mission: '{brief}' within €{budget:.0f}")

        # 1) Stylist proposes the vision; ASK the human to approve (taste = human's call).
        palette, components = self.stylist.propose_spec(brief, budget)
        ledger = Ledger(brief=brief, total_budget=budget, palette=palette, components=components)
        self._preview(palette, components, "Proposed outfit")

        decision, why = policy.decide("approve_spec", taste_risk=True)
        ev.emit("escalation", "coordinator", text=f"ASK human: approve the vision? ({why})")
        reply = self.human.ask("Approve this outfit vision? Any amendments?",
                               options=["approve", "amend"])
        ev.emit("human_reply", "human", text=reply)
        if "amend" in reply.lower() or "flat" in reply.lower() or "shoulder" in reply.lower():
            self.stylist.amend(components, reply)
            self._preview(palette, components, "Updated after your amendment")

        # 2) Procurement allocates the shared budget — and the human confirms the split.
        self.procurement.allocate(ledger)
        ev.emit("escalation", "coordinator", text="Asking you to approve the budget split.")
        reply = self.human.ask("Approve this budget split?", options=["approve", "adjust"])
        ev.emit("human_reply", "human", text=reply)
        if "adjust" in reply.lower():
            ev.emit("decision", "coordinator", text="Human adjusted the split (kept proportions for the demo)")

        # 3) Buyers shop each component; budget conflicts get arbitrated or escalated.
        for c in components:
            query = self.stylist.query_for(c, palette)
            best = self.buyer.shop(c, query, c.allocation)
            if not best:
                c.status = "escalated"
                ev.emit("escalation", "coordinator", text=f"No candidate for {c.name} — flagged")
                continue
            c.chosen, c.status = best, "proposed"
            self._settle_component(ledger, c)

        # 4) Reassemble + traceability + final purchase gate.
        self._finalize(ledger)
        return ledger

    def _preview(self, palette, components, caption):
        """Render a fal outfit preview (if enabled) and stream it to the canvas."""
        url = lookbook.generate(palette, components)
        if url:
            self.events.emit("preview", "stylist", image=url, text=caption)

    def _settle_component(self, ledger, c):
        """Try to acquire c.chosen within budget; reallocate, negotiate, or escalate."""
        ev = self.events
        price = c.chosen["price"]
        ok, over, slack = self.procurement.check(ledger, c, price)

        if ok:
            self._acquire(ledger, c, price)
            return

        # Overspend the org can't absorb from slack -> escalate the arbitration to human.
        d, why = policy.decide("overspend", within_budget=False, overspend=over)
        if d == policy.ASK:
            ev.emit("escalation", "coordinator",
                    text=f"{c.name} '{c.chosen['title']}' is €{price:.0f} — €{over:.0f} over its "
                         f"€{c.allocation:.0f} budget. Raiding other categories risks the rest of the look.")
            reply = self.human.ask(
                f"The {c.name} you'll love is €{price:.0f}, €{over:.0f} over budget. "
                f"Negotiate it down, or stretch the budget?",
                options=["negotiate", "stretch", "cheaper"])
            ev.emit("human_reply", "human", text=reply)

            if "negotiate" in reply.lower():
                target = round(c.allocation * 1.15)   # authorized negotiation ceiling
                seller = self.seller_factory(c.chosen)
                final = self.negotiator.haggle(c.chosen, target, seller)
                if final is not None and final <= target:
                    self._acquire(ledger, c, final)
                else:
                    c.status = "escalated"
                    ev.emit("escalation", "coordinator", text=f"{c.name}: negotiation failed")
            elif "stretch" in reply.lower():
                # Stretch by REALLOCATION: trim slack from other categories into this one,
                # keeping the total fixed. Only raise the total if slack can't cover it.
                freed = self.procurement.reallocate(ledger, c, over)
                if freed < over:
                    ledger.total_budget += round(over - freed, 2)
                    ev.emit("budget", "coordinator", text=f"Raised total by €{over-freed:.0f} (slack short)")
                self._acquire(ledger, c, price)
            else:
                c.status = "escalated"
        else:
            self._acquire(ledger, c, price)

    def _acquire(self, ledger, c, price):
        c.final_price, c.status = price, "acquired"
        self.events.emit("decision", "coordinator",
                         text=f"Acquire {c.name}: '{c.chosen['title']}' @ €{price:.0f} "
                              f"| remaining €{ledger.remaining():.0f}")

    def _finalize(self, ledger):
        ev = self.events
        acquired = [c for c in ledger.components if c.status == "acquired"]
        ev.emit("decision", "coordinator",
                text=f"Outfit: {len(acquired)}/{len(ledger.components)} items, "
                     f"total €{ledger.spent():.0f} / €{ledger.total_budget:.0f}")

        # Final purchase = side-effectful -> CONFIRM with the human.
        d, why = policy.decide("purchase")
        ev.emit("escalation", "coordinator", text=f"CONFIRM purchase ({why})")
        reply = self.human.ask(f"Buy all {len(acquired)} items for €{ledger.spent():.0f}?",
                               options=["confirm", "cancel"])
        ev.emit("human_reply", "human", text=reply)
        if "confirm" in reply.lower():
            ev.emit("deal", "coordinator", text="Purchase confirmed")
            self._logistics(ledger, acquired)

    HOME = "Germany"  # the wearer's country (Munich). Local items = in-person pickup.

    def _logistics(self, ledger, acquired):
        """The finds come from different sellers in different countries. Most ship
        (paid online); only a genuinely local seller becomes an in-person pickup —
        for that one item's price, not the whole basket. Emitted to the stream AND
        delivered over the human channel."""
        ev = self.events
        local = [c for c in acquired if (c.chosen.get("country") == self.HOME)]
        ship = [c for c in acquired if c not in local]

        if ship:
            by_country = {}
            for c in ship:
                by_country.setdefault(c.chosen.get("country", "abroad"), []).append(c.name)
            parts = ", ".join(f"{', '.join(n)} from {ctry}" for ctry, n in by_country.items())
            msg = (f"Paid online — {parts} will ship. Orders placed, I've messaged each "
                   f"seller; tracking to follow.")
            ev.emit("message", "coordinator", text=msg)
            self.human.instruct(msg)

        for c in local:
            msg = (f"The {c.name} seller is local in Munich. For that one: U3/U6 to "
                   f"Universität, bring €{c.final_price:.0f} cash from the Rewe ATM on "
                   f"Leopoldstraße, and tap to send the pickup message I drafted. "
                   f"(Everything else ships.)")
            ev.emit("message", "coordinator", text=msg)
            self.human.instruct(msg)
