"""fal.ai outfit preview.

When the stylist proposes the vision (and again when the human amends it), Lupo
renders a generic-model preview of the outfit on the canvas — no user photo, just
a clean lookbook of the proposed pieces in the chosen palette. This makes the
taste loop tangible: amend "ballet flats / mesh top" and the picture changes.

Real path (USE_REAL_FAL + FAL_KEY): fal text-to-image. Stub: returns None, so the
canvas simply hides the preview and the rest of the demo is unaffected.
"""
import os
import time
from . import config


def describe(palette, components):
    """Build a text-to-image prompt from the structured outfit spec."""
    def _item(c):
        desc = f"{'/'.join(c.style_tags[:2])} {c.name}"
        # The real brunch find is a plain BEIGE 'clean girl' dress, not a vivid print —
        # ask for a soft pastel dress so the preview matches what actually ships.
        return f"pastel-coloured {desc}" if c.name == "dress" else desc
    items = ", ".join(_item(c) for c in components)
    pal = ", ".join(palette)
    return (f"Full-length editorial lookbook photo of a model wearing a coordinated "
            f"outfit: {items}. Colour palette: {pal}. The model stands centered, the "
            f"ENTIRE body in frame from the top of the head to the shoes, with margin "
            f"above and below — nothing cropped. Clean studio backdrop, soft natural "
            f"light, no text, no watermark.")


def generate(palette, components):
    """Return a preview image URL for the outfit, or None. Best-effort; never raises."""
    if not config.USE_REAL_FAL:
        return None
    prompt = describe(palette, components)
    # fal occasionally answers a cold request with a transient 403/5xx; one quick retry
    # turns those into a rendered preview instead of a silently-skipped one.
    last = None
    for attempt in range(2):
        try:
            import fal_client
            result = fal_client.subscribe(
                os.getenv("FAL_IMAGE_MODEL", "fal-ai/bytedance/seedream/v4/text-to-image"),
                # tall portrait frames a full standing model head-to-toe (the canvas shows it
                # with object-fit:contain, so the whole figure is visible, not a centre crop).
                arguments={"prompt": prompt,
                           "image_size": os.getenv("FAL_IMAGE_SIZE", "portrait_16_9"),
                           "num_images": 1},
                with_logs=False,
            )
            images = result.get("images") or []
            return images[0].get("url") if images else None
        except Exception as e:
            last = e
            if attempt == 0:
                time.sleep(1.5)
    print(f"[fal] preview generation failed ({last}); skipping preview.")
    return None
