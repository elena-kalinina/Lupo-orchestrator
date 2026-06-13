"""Config + partner toggles. Everything off => fully offline, deterministic demo.

Loads a local .env (if present) so every script/server picks up the same keys.
"""
import os

try:
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass  # python-dotenv is optional; stub mode needs no env at all


def _flag(name):
    return os.getenv(name, "0") == "1"


USE_REAL_GEMINI = _flag("USE_REAL_GEMINI")   # stylist + extraction escalation
USE_REAL_VISION = _flag("USE_REAL_VISION")   # Gemini multimodal style-match on listing photos (slower)
USE_REAL_FAL = _flag("USE_REAL_FAL")         # fal.ai outfit preview image
USE_REAL_GLINER = _flag("USE_REAL_GLINER")   # local GLiNER multilingual extraction (pulls torch)
USE_PIONEER = _flag("USE_PIONEER")           # Fastino Pioneer hosted GLiNER2 extraction
USE_REAL_VOICE = _flag("USE_REAL_VOICE")     # Gemini TTS voice ping

# Below this extraction confidence, GLiNER escalates the listing to Gemini (arbitration).
GLINER_ESCALATION_THRESHOLD = float(os.getenv("GLINER_ESCALATION_THRESHOLD", "0.55"))
# Vinted live vs replay is handled by LUPO_VINTED_LIVE in vinted/client.py
# Human channel backend is handled by LUPO_HUMAN_CHANNEL in human/channel.py
