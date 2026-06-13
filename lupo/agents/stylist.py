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
        # The deterministic skeleton fixes the SLOT NAMES (dress/shoes/… or top/…/boots).
        # Everything downstream — the cached Vinted finds, the amend hooks, the per-slot
        # budget allocations — is keyed on these names, so they must stay constant. When
        # USE_REAL_GEMINI is on we let Gemini rewrite the palette + per-slot style tags
        # for EXACTLY these slots (a real LLM in the loop) but never the names themselves.
        b = brief.lower()
        if any(k in b for k in ["tomorrowland", "rave", "festival", "concert"]):
            # Rave outfit. 'top' defaults to plain so the 'mesh + sparkle' amendment
            # changes something. The hero (boots) is procured FIRST and on purpose: it
            # blows its slice immediately, so 'stretch' visibly trims the still-unspent
            # cheaper categories to fund it — instead of quietly mopping up leftover slack
            # at the end. Procurement.reallocate spreads the trim proportionally so no
            # single category is starved.
            palette = ["neon", "black", "holographic"]
            comps = [
                Component(name="boots", style_tags=["platform", "chunky"]),
                Component(name="top", style_tags=["crop", "plain"]),
                Component(name="bottoms", style_tags=["cargo", "techno"]),
                Component(name="accessories", style_tags=["holographic", "sunglasses"]),
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

        if config.USE_REAL_GEMINI:
            try:
                self._enrich_spec(brief, budget, palette, comps)
            except Exception as e:
                self.emit("decision", text=f"(Gemini spec refine failed, using stub: {e})")

        self.emit("message", text=f"Vision: {palette} palette — "
                                  f"{', '.join(c.name+' ('+'/'.join(c.style_tags)+')' for c in comps)}")
        return palette, comps

    def amend(self, components, instruction):
        """Apply a human taste amendment. Slot lookups are defensive: if a slot isn't
        in the spec (e.g. a refined spec dropped it) we just skip that amendment rather
        than crash the mission."""
        by_name = {c.name: c for c in components}
        instr = instruction.lower()
        if ("flat" in instr or "ballet" in instr) and "shoes" in by_name:
            by_name["shoes"].style_tags = ["ballet", "flat", "tan"]
            self.emit("decision", text="Amended shoes: sandals → ballet flats")
        if "shoulder" in instr and "bag" in by_name:
            by_name["bag"].style_tags = ["shoulder", "small", "summer"]
            self.emit("decision", text="Amended bag: tote → small shoulder bag")
        if ("mesh" in instr or "sparkle" in instr) and "top" in by_name:
            by_name["top"].style_tags = ["mesh", "sparkle"]
            self.emit("decision", text="Amended top: plain → mesh + sparkle")
        return components

    def query_for(self, component, palette):
        """Build a Vinted search query for a component from its style tags + palette."""
        return " ".join(component.style_tags[:2] + [component.name, palette[0]])

    def _enrich_spec(self, brief, budget, palette, comps):
        """Real Gemini in the loop: rewrite the palette + per-slot style tags IN PLACE
        for the fixed slot names. Mutates `palette` and each component's style_tags;
        leaves names untouched so the cache/amend/budget contract holds. The one slot
        the human will amend keeps a tag we can visibly change (sandals / plain)."""
        from .. import llm
        names = [c.name for c in comps]
        # Slots whose default tag must survive so the scripted amendment changes something.
        keep = {"shoes": "sandals", "top": "plain"}
        data = llm.gemini_json(
            "You are a fashion stylist. Fill in an outfit for this brief. Return JSON "
            "with keys 'palette' (exactly 3 short colour words) and 'tags' (an object "
            "mapping EACH of these component names to a list of 3 short lowercase style "
            f"tags): {names}. Use exactly these component names as keys, no others. "
            f"For these components keep this first tag as-is: {keep}. "
            f"Brief: {brief!r}. Budget: €{budget:.0f}.")
        new_pal = data.get("palette")
        if isinstance(new_pal, list) and len(new_pal) >= 2:
            palette[:] = [str(x) for x in new_pal[:3]]
        tags = data.get("tags") or {}
        for c in comps:
            t = tags.get(c.name)
            if isinstance(t, list) and t:
                clean = [str(x).lower() for x in t[:3]]
                if c.name in keep and keep[c.name] not in clean:
                    clean = [keep[c.name]] + clean[:2]   # guarantee the amend hook survives
                c.style_tags = clean
