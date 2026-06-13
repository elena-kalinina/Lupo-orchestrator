"""Shopping mission — assembles the org and runs an outfit-procurement mission."""
from ..events import EventStream
from ..human.channel import get_channel
from ..coordinator import Coordinator
from ..agents.stylist import Stylist
from ..agents.buyer import Buyer
from ..agents.procurement import Procurement
from ..agents.negotiator import Negotiator, Seller


def _seller_factory(events):
    """Build a simulated seller from a real listing: reservation ~80% of asking."""
    def make(listing):
        asking = listing["price"]
        return Seller(f"seller:{listing['id']}", events,
                      asking=asking, reservation=round(asking * 0.8, 0),
                      persona=listing.get("persona", "flexible"))
    return make


SCENARIOS = {
    "brunch": {
        "brief": "Sunday brunch with the girls — cute but comfy",
        "budget": 60.0,
        "script": [
            ("amendments", "amend: ballet flats instead of sandals, and a small shoulder bag"),
            ("budget split", "approve"),
            ("negotiate it down", "negotiate"),
            ("buy all", "confirm"),
        ],
    },
    "tomorrowland": {
        "brief": "Tomorrowland mainstage, Saturday night — bold, rave-ready, danceable",
        "budget": 80.0,
        "script": [
            ("amendments", "amend: make it a mesh top and add some sparkle"),
            ("budget split", "approve"),
            ("negotiate it down", "stretch"),     # over-budget boots -> reallocate
            ("buy all", "confirm"),
        ],
    },
}


def run(scenario="brunch", human=None, events=None):
    cfg = SCENARIOS[scenario]
    events = events or EventStream()
    human = human or get_channel(cfg["script"])

    stylist = Stylist("stylist", events)
    buyer = Buyer("buyer", events)
    procurement = Procurement("procurement", events)
    negotiator = Negotiator("negotiator", events)

    coord = Coordinator(events, human, stylist, buyer, procurement,
                        negotiator, _seller_factory(events))
    ledger = coord.run(cfg["brief"], cfg["budget"])
    return ledger, events


def traceability(ledger):
    """Every brief component -> acquired/negotiated/escalated, with the budget proof."""
    lines = ["# Mission Traceability",
             f"Brief: {ledger.brief}",
             f"Budget: €{ledger.total_budget:.0f} | Spent: €{ledger.spent():.0f} | "
             f"Remaining: €{ledger.remaining():.0f}",
             "", "| Component | Status | Item | Price | Style |",
             "|-----------|--------|------|-------|-------|"]
    for c in ledger.components:
        item = c.chosen["title"] if c.chosen else "—"
        price = f"€{c.final_price:.0f}" if c.final_price else "—"
        lines.append(f"| {c.name} | {c.status} | {item} | {price} | {'/'.join(c.style_tags)} |")
    return "\n".join(lines)
