"""Real model integrations (Gemini structured output + TTS). Used only when the
USE_REAL_* toggles are on. Each call is best-effort and falls back to the stub on
any error, so flipping a toggle can never crash the demo.

VERIFY ON HACKATHON DAY: needs `pip install google-genai` and GEMINI_API_KEY, and a
live run to confirm the current SDK surface / model names (we pinned what the docs
showed; model strings drift).
"""
import os
import json
import struct
import base64
import wave
import io

_DEF_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
_DEF_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")

_client = None


def client():
    global _client
    if _client is None:
        from google import genai  # google-genai SDK
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


def gemini_json(prompt, model=None):
    """Return parsed JSON from a Gemini structured-output call. Caller handles fallback."""
    r = client().models.generate_content(
        model=model or _DEF_TEXT_MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"},
    )
    return json.loads(r.text)


def gemini_vision_fit(photo_url, style_tags):
    """Score 0..1 how well the garment in `photo_url` matches the desired style tags,
    judged by Gemini multimodal. Caller handles fallback on error."""
    import httpx
    img = httpx.get(photo_url, timeout=15, follow_redirects=True)
    img.raise_for_status()
    mime = img.headers.get("content-type", "image/jpeg").split(";")[0]
    from google.genai import types
    prompt = (
        "You are a fashion stylist judging a second-hand listing photo. "
        f"Desired style: {', '.join(style_tags)}. "
        "Return ONLY a JSON object {\"fit\": <0.0-1.0>} where fit is how well the "
        "garment in the photo matches the desired style (1.0 = perfect)."
    )
    r = client().models.generate_content(
        model=os.getenv("GEMINI_VISION_MODEL", _DEF_TEXT_MODEL),
        contents=[types.Part.from_bytes(data=img.content, mime_type=mime), prompt],
        config={"response_mime_type": "application/json"},
    )
    val = float(json.loads(r.text).get("fit", 0.5))
    return max(0.0, min(1.0, val))


def gemini_tts(text, style="[wry]", voice="Kore", model=None, out_path="lupo_ping.wav"):
    """Generate speech with Gemini TTS and write a WAV. Returns the file path.
    The model returns raw PCM (24kHz, 16-bit, mono) as inline audio data."""
    r = client().models.generate_content(
        model=model or _DEF_TTS_MODEL,
        contents=f"{style}: {text}",
        config={
            "response_modalities": ["AUDIO"],
            "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": voice}}},
        },
    )
    part = r.candidates[0].content.parts[0].inline_data
    pcm = part.data if isinstance(part.data, (bytes, bytearray)) else base64.b64decode(part.data)
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
    return out_path
