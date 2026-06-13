"""The mission ledger — shared structured state ('structured knowledge working
across teams', in the challenge's words).

Holds the outfit spec, the budget ledger, per-component acquisition state, and the
human-question queue. The Coordinator is the only writer of record; agents propose,
the ledger commits.
"""
from dataclasses import dataclass, field


@dataclass
class Component:
    name: str                 # e.g. "dress", "shoes"
    style_tags: list          # e.g. ["floral", "midi", "casual"]
    allocation: float = 0.0   # sub-budget assigned by procurement
    chosen: dict = None       # the selected listing
    final_price: float = None # after negotiation
    status: str = "open"      # open|proposed|negotiating|acquired|escalated


@dataclass
class Ledger:
    brief: str
    total_budget: float
    palette: list = field(default_factory=list)
    components: list = field(default_factory=list)   # list[Component]
    human_queue: list = field(default_factory=list)  # pending questions

    def spent(self):
        return sum(c.final_price or 0 for c in self.components if c.status == "acquired")

    def committed(self):
        # acquired + best current proposals (for live budget view)
        total = 0
        for c in self.components:
            if c.status == "acquired":
                total += c.final_price or 0
            elif c.chosen:
                total += c.chosen["price"]
        return total

    def remaining(self):
        return round(self.total_budget - self.committed(), 2)

    def by_name(self, name):
        return next((c for c in self.components if c.name == name), None)

    def coverage(self):
        return {c.name: c.status for c in self.components}
