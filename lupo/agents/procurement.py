"""Procurement / Budget Controller. Owns the shared budget envelope.

This is Lupo's constraint-solver re-instantiated: allocate the total across components,
and when a buyer's pick exceeds its slice, arbitrate — reallocate slack from
under-spent components, or flag an overspend the Coordinator must escalate.

The shared budget is exactly where multi-agent coordination lives: independent buyers
would collectively overspend; this agent is the org's procurement function.
"""
from .base import Agent


class Procurement(Agent):
    role = "procurement"

    # Rough priors for how a budget splits across components, per scenario.
    WEIGHTS = {"dress": 0.40, "shoes": 0.28, "bag": 0.20, "jewellery": 0.12,
               "top": 0.25, "bottoms": 0.30, "boots": 0.30, "accessories": 0.15}

    def allocate(self, ledger):
        total = ledger.total_budget
        fixed = getattr(ledger, "allocations", None) or {}
        for c in ledger.components:
            if c.name in fixed:                       # scenario-tuned sub-budget
                c.allocation = round(float(fixed[c.name]), 2)
            else:
                c.allocation = round(total * self.WEIGHTS.get(c.name, 1 / len(ledger.components)), 2)
        self.emit("budget", text="Allocations: "
                  + ", ".join(f"{c.name} €{c.allocation:.0f}" for c in ledger.components))

    def reallocate(self, ledger, component, needed):
        """STRETCH-by-reallocation: trim slack from the OTHER categories and pour it into
        `component`, keeping the total envelope fixed. The trim is spread PROPORTIONALLY
        to each category's available slack, so funding an over-budget hero (e.g. the
        boots, procured first) tightens every other slice a little rather than starving
        one. Returns the euros freed."""
        others = []
        for c in ledger.components:
            if c is component:
                continue
            spent = (c.final_price if c.status == "acquired"
                     else (c.chosen["price"] if c.chosen else 0)) or 0
            slack = max(0, c.allocation - spent)
            if slack > 0:
                others.append((c, slack))
        total_slack = round(sum(s for _, s in others), 2)
        take_total = round(min(needed, total_slack), 2)
        others.sort(key=lambda x: -x[1])              # largest slack absorbs the remainder
        freed, remaining = 0.0, take_total
        for i, (c, slack) in enumerate(others):
            take = remaining if i == len(others) - 1 else round(take_total * slack / total_slack, 2)
            take = min(take, slack, remaining)
            c.allocation = round(c.allocation - take, 2)
            freed = round(freed + take, 2)
            remaining = round(remaining - take, 2)
        component.allocation = round(component.allocation + freed, 2)
        self.emit("budget", text=f"Reallocated €{freed:.0f} from other categories → {component.name}")
        return freed

    def check(self, ledger, component, price):
        """Return (ok, overspend, slack). Auto-absorbs only TRIVIAL overspend; a
        material overspend is escalated, because aggressively raiding other
        categories early risks starving the rest of the outfit."""
        over = round(price - component.allocation, 2)
        if over <= 0:
            return True, 0.0, 0.0
        slack = self._available_slack(ledger, exclude=component.name)
        if over <= 3 and slack >= over:
            component.allocation = round(component.allocation + over, 2)
            self.emit("budget", text=f"Absorbed €{over:.0f} overspend on {component.name} from slack")
            return True, 0.0, over
        return False, over, slack

    def _available_slack(self, ledger, exclude):
        slack = 0
        for c in ledger.components:
            if c.name == exclude:
                continue
            spent = (c.final_price if c.status == "acquired" else
                     (c.chosen["price"] if c.chosen else 0))
            slack += max(0, c.allocation - (spent or 0))
        return round(slack, 2)
