"""Stylist (creative director). Brief -> structured outfit spec with constraints.

This IS Lupo's spec compiler in a new domain: free-text brief -> machine-checkable
components + style tags + palette. Stub is rule-based; hackathon day -> Gemini.
"""
from .base import Agent
from ..ledger import Component
from .. import config


class Stylist(Agent):
    role = "stylist"

    def propose_spec(self, brief, budget):
        if config.USE_REAL_GEMINI:
            try:
                return self._real_spec(brief, budget)
            except Exception as e:
                self.emit("decision", text=f"(Gemini spec failed, using stub: {e})")
        b = brief.lower()
        if any(k in b for k in ["tomorrowland", "rave", "festival", "concert"]):
            # Rave outfit. 'top' defaults to plain so the 'mesh + sparkle' amendment
            # changes something. Order puts the hero (boots) LAST so procurement has
            # realised slack to reallocate from when the boots blow the budget.
            palette = ["neon", "black", "holographic"]
            comps = [
                Component(name="top", style_tags=["crop", "plain"]),
                Component(name="bottoms", style_tags=["cargo", "techno"]),
                Component(name="accessories", style_tags=["holographic", "sunglasses"]),
                Component(name="boots", style_tags=["platform", "chunky"]),
            ]
        else:
            # Brunch outfit. Shoes default to SANDALS so the 'ballet flats' amendment lands.
            palette = ["cream", "sage", "gold"]
            comps = [
                Component(name="dress", style_tags=["floral", "midi", "casual"]),
                Component(name="shoes", style_tags=["sandals", "tan", "flat"]),
                Component(name="bag", style_tags=["raffia", "tote", "summer"]),
                Component(name="jewellery", style_tags=["gold", "hoops", "dainty"]),
            ]
        self.emit("message", text=f"Vision: {palette} palette — "
                                  f"{', '.join(c.name+' ('+'/'.join(c.style_tags)+')' for c in comps)}")
        return palette, comps

    def amend(self, components, instruction):
        """Apply a human taste amendment."""
        instr = instruction.lower()
        if "flat" in instr or "ballet" in instr:
            next(c for c in components if c.name == "shoes").style_tags = ["ballet", "flat", "tan"]
            self.emit("decision", text="Amended shoes: sandals → ballet flats")
        if "shoulder" in instr:
            next(c for c in components if c.name == "bag").style_tags = ["shoulder", "small", "summer"]
            self.emit("decision", text="Amended bag: tote → small shoulder bag")
        if "mesh" in instr or "sparkle" in instr:
            next(c for c in components if c.name == "top").style_tags = ["mesh", "sparkle"]
            self.emit("decision", text="Amended top: plain → mesh + sparkle")
        return components

    def query_for(self, component, palette):
        """Build a Vinted search query for a component from its style tags + palette."""
        return " ".join(component.style_tags[:2] + [component.name, palette[0]])

    def _real_spec(self, brief, budget):
        from .. import llm
        from ..ledger import Component
        data = llm.gemini_json(
            "You are a stylist. Given this brief, return JSON with keys "
            "'palette' (list of 3 colours) and 'components' (list of 4 objects "
            "{name, style_tags:[3 tags]}) ordered cheapest-intent first, hero last. "
            f"Brief: {brief!r}. Budget: €{budget:.0f}.")
        palette = data["palette"]
        comps = [Component(name=c["name"], style_tags=c["style_tags"]) for c in data["components"]]
        self.emit("message", text=f"Vision: {palette} — "
                  + ", ".join(c.name for c in comps))
        return palette, comps
