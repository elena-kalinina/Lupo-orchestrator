"""Multilingual entity extraction from Vinted listings (the messy free text).

Sellers dump material/style/fit into the title & description instead of the
structured fields. GLiNER pulls them out — multilingually (FR/NL/EN/IT/DE and
mixed). Low-confidence listings escalate to Gemini; Gemini's answer is recorded
as a training sample so Pioneer can sharpen GLiNER over time.

This is the 'arbitration between powerful multimodal and smaller cheaper models',
one level below the agent<->human escalation. Keep the label set small (<~30 types;
we use 7) — GLiNER degrades past that.

Offline/stub mode: a multilingual keyword extractor so the demo runs with no model
download. Real mode (USE_REAL_GLINER=1): load gliner_multi and extract by prompt.
"""
import os
import re
from . import config
from . import samples

LABELS = ["material", "style", "fit", "brand", "size", "colour", "condition"]

# --- Stub multilingual lexicon (FR/NL/EN/IT/DE). Real GLiNER replaces this. ---
_MATERIAL = {
    "leather": ["leather", "cuir", "leer", "pelle", "cuoio", "leder"],
    "cotton":  ["cotton", "coton", "katoen", "cotone", "baumwolle"],
    "denim":   ["denim", "jean", "jeans", "spijker"],
    "wool":    ["wool", "laine", "wol", "lana", "wolle"],
    "silk":    ["silk", "soie", "zijde", "seta", "seide"],
    "linen":   ["linen", "lin", "linnen", "lino", "leinen"],
    "velvet":  ["velvet", "velours", "fluweel", "velluto", "samt"],
}
_STYLE = {
    "boho": ["boho", "bohème", "boheme"], "y2k": ["y2k"], "vintage": ["vintage", "rétro", "retro"],
    "minimalist": ["minimalist", "minimaliste", "minimalistisch"],
    "cottagecore": ["cottagecore"], "streetwear": ["streetwear"],
    "coquette": ["coquette"], "preppy": ["preppy"], "grunge": ["grunge"],
}
_FIT = {
    "fits_large": ["fits large", "oversized", "taille grand", "valt groot", "größer", "veste grande"],
    "fits_small": ["fits small", "taille petit", "valt klein", "kleiner", "small fit"],
    "true_to_size": ["true to size", "taille normale", "valt normaal", "normale größe"],
}
_LANG_HINT = {  # cheap language guess for the demo
    "fr": ["taille", "cuir", "soie", "très", "neuf", "porté"],
    "nl": ["maat", "leer", "zijde", "nieuw", "gedragen", "mooie"],
    "it": ["taglia", "pelle", "nuovo", "seta"],
    "de": ["größe", "leder", "neu", "getragen"],
}


def _guess_lang(t):
    for lang, words in _LANG_HINT.items():
        if any(w in t for w in words):
            return lang
    return "en"


def _scan(text, lexicon):
    t = text.lower()
    found = []
    for canon, variants in lexicon.items():
        for v in variants:
            # whole-phrase/word match: "lino" won't fire inside "cartellino"
            if re.search(r"(?<!\w)" + re.escape(v) + r"(?!\w)", t):
                found.append(canon)
                break
    return found


def extract(listing, events=None):
    """Return {attrs, lang, confidence, source}. Escalates to Gemini if unsure."""
    text = f"{listing.get('title','')} {listing.get('desc','')}".strip()
    attrs = conf = None
    source = "keyword-stub"
    if config.USE_PIONEER:
        try:
            from . import pioneer
            attrs, conf = pioneer.extract(text, LABELS, threshold=0.4)
            source = "pioneer-gliner2"
        except Exception:
            attrs = None
    if attrs is None and config.USE_REAL_GLINER:
        try:
            attrs, conf = _real_gliner(text)
            source = "gliner"
        except Exception:
            attrs = None
    if attrs is None:
        attrs = {
            "material": _scan(text, _MATERIAL),
            "style": _scan(text, _STYLE),
            "fit": _scan(text, _FIT),
        }
        signal = sum(len(v) for v in attrs.values())
        conf = min(1.0, 0.3 + 0.25 * signal)   # more hits -> more confident
    lang = _guess_lang(text)

    if conf < config.GLINER_ESCALATION_THRESHOLD:
        g_attrs = _gemini_extract(text)         # frontier model resolves the hard case
        samples.record(text, lang, attrs, g_attrs, conf)
        attrs, conf, source = g_attrs, 0.9, "gemini-escalation"
        if events:
            events.emit("escalation", "buyer",
                        text=f"GLiNER unsure on '{text[:40]}…' ({lang}) → escalated to Gemini")

    if events:
        flat = ", ".join(f"{k}={v}" for k, v in attrs.items() if v) or "none"
        events.emit("message", "buyer", text=f"extracted [{lang}] {flat} (conf {conf:.0%}, {source})")
    return {"attrs": attrs, "lang": lang, "confidence": conf, "source": source}


def _gemini_extract(text):
    """Frontier-model fallback. Stub returns a fuller guess; real -> Gemini structured output."""
    if config.USE_REAL_GEMINI:
        try:
            return _real_gemini(text)
        except Exception:
            pass
    return {"material": _scan(text, _MATERIAL) or ["unknown"],
            "style": _scan(text, _STYLE), "fit": _scan(text, _FIT)}


# --- real implementations (hackathon day) ----------------------------------
_gliner_model = None


def _real_gliner(text):
    """Multilingual GLiNER extraction. Groups predicted spans by label."""
    global _gliner_model
    if _gliner_model is None:
        from gliner import GLiNER
        _gliner_model = GLiNER.from_pretrained(
            os.getenv("GLINER_MODEL", "urchade/gliner_multi-v2.1"))
    ents = _gliner_model.predict_entities(text, LABELS, threshold=0.4)
    attrs = {"material": [], "style": [], "fit": []}
    for e in ents:
        lbl = e["label"]
        if lbl in attrs:
            attrs[lbl].append(e["text"].lower())
    conf = min(1.0, 0.3 + 0.25 * sum(len(v) for v in attrs.values()))
    return attrs, conf


def _real_gemini(text):
    from . import llm
    return llm.gemini_json(
        "Extract fashion attributes from this listing text (any language). "
        "Return JSON {material:[], style:[], fit:[]} using canonical English values "
        "(e.g. material: leather/cotton/wool; fit: fits_small/fits_large/true_to_size). "
        f"Text: {text!r}")
