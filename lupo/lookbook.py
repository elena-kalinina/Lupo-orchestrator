"""fal.ai outfit preview.

When the stylist proposes the vision (and again when the human amends it), Lupo
renders a generic-model preview of the outfit on the canvas — no user photo, just
a clean lookbook of the proposed pieces in the chosen palette. This makes the
taste loop tangible: amend "ballet flats / mesh top" and the picture changes.

Real path (USE_REAL_FAL + FAL_KEY): fal text-to-image. Stub: returns None, so the
canvas simply hides the preview and the rest of the demo is unaffected.
"""
import os
from . import config


def describe(palette, components):
    """Build a text-to-image prompt from the structured outfit spec."""
    items = ", ".join(f"{'/'.join(c.style_tags[:2])} {c.name}" for c in components)
    pal = ", ".join(palette)
    return (f"Full-body editorial lookbook photo of a model wearing a coordinated "
            f"outfit: {items}. Colour palette: {pal}. Clean studio backdrop, soft "
            f"natural light, full outfit visible head to toe, no text, no watermark.")


def generate(palette, components):
    """Return a preview image URL for the outfit, or None. Best-effort; never raises."""
    if not config.USE_REAL_FAL:
        return None
    try:
        import fal_client
        prompt = describe(palette, components)
        result = fal_client.subscribe(
            os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/schnell"),
            arguments={"prompt": prompt, "image_size": "portrait_4_3", "num_images": 1},
            with_logs=False,
        )
        images = result.get("images") or []
        return images[0].get("url") if images else None
    except Exception as e:
        print(f"[fal] preview generation failed ({e}); skipping preview.")
        return None
