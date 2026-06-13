"""Category Buyer. One per component, runs in parallel(-ish). Searches Vinted for
candidates matching its style slice and sub-budget, scores them, proposes the best.

Style-fit now uses GLiNER multilingual extraction: it pulls material/style/fit out
of the messy (FR/NL/EN/IT/DE) listing text — the fields sellers never fill in —
and scores against the brief. Low-confidence listings escalate to Gemini.
Hackathon upgrade: add Gemini VISION on the photo for the final taste call.
"""
from .base import Agent
from ..vinted import client as vinted
from .. import extract_entities
from .. import config


class Buyer(Agent):
    role = "buyer"

    def shop(self, component, query, allocation):
        candidates = vinted.search(query, max_price=None, limit=8)
        self.emit("task", text=f"{component.name}: {len(candidates)} candidates "
                               f"(alloc €{allocation:.0f})", summary=query)
        if not candidates:
            return None
        # Extract structured attributes from each listing's messy multilingual text.
        for it in candidates:
            it["_extracted"] = extract_entities.extract(it, self.events)
        # Optional multimodal taste call: re-score the top text matches by photo.
        self._vision_rescore(candidates, component)
        scored = sorted(candidates, key=lambda it: (-self._fit(it, component), it["price"]))
        best = scored[0]
        # Structured payload for the canvas (rich find-cards).
        self.events.emit("candidates", self.name, category=component.name,
                         text=f"{component.name}: ranked {len(scored)} finds",
                         candidates=[{
                             "title": it["title"], "price": it["price"], "size": it.get("size", ""),
                             "lang": it["_extracted"]["lang"], "desc": it.get("desc", ""),
                             "photo": it.get("photo"), "country": it.get("country"),
                             "attrs": [v for vals in it["_extracted"]["attrs"].values() for v in (vals or [])],
                             "source": it["_extracted"]["source"],
                             "fit": round(self._fit(it, component) * 100),
                             "best": it is best,
                         } for it in scored])
        self.emit("message", text=f"{component.name}: pick '{best['title']}' "
                                  f"€{best['price']} (fit {self._fit(best, component):.0%})")
        return best

    @staticmethod
    def _fit(item, component):
        if item.get("_vision_fit") is not None:
            return item["_vision_fit"]
        text = (item.get("title", "") + " " + item.get("brand", "")).lower()
        hits = sum(1 for tag in component.style_tags if tag in text)
        # Bonus: extracted material/style/fit that match the desired style tags.
        ex = item.get("_extracted", {}).get("attrs", {})
        ex_vals = {v for vals in ex.values() for v in (vals or [])}
        hits += sum(1 for tag in component.style_tags if tag in ex_vals)
        return min(1.0, 0.4 + 0.18 * hits)

    def _vision_rescore(self, candidates, component, top_n=3):
        """Re-score the top text matches with Gemini multimodal on the listing photo.
        Off by default (USE_REAL_VISION); falls back silently to the keyword score."""
        if not (config.USE_REAL_GEMINI and config.USE_REAL_VISION):
            return
        from .. import llm
        top = sorted(candidates, key=lambda it: -self._fit(it, component))[:top_n]
        for it in top:
            photo = it.get("photo", "")
            if not (isinstance(photo, str) and photo.startswith("http")):
                continue
            try:
                it["_vision_fit"] = llm.gemini_vision_fit(photo, component.style_tags)
                self.emit("message", text=f"{component.name}: vision judged "
                                          f"'{it['title'][:30]}' fit {it['_vision_fit']:.0%}")
            except Exception:
                pass  # keep the keyword score
