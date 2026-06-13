"""HumanChannel — one interface, swappable backends.

  ScriptedChannel : offline demo. Pre-seeded answers so run_mission runs with no
                    network and the demo is deterministic. Your reliability net.
  WebChannel      : local panel (always works, instant); doubles as the canvas.
  WhatsAppChannel : Twilio WhatsApp sandbox — the primary 'wow' backend.
  EmailChannel    : SMTP send + IMAP poll — weak fallback for an interactive loop.

The Coordinator only ever calls .ask() and .instruct(); it doesn't care which
backend is live. Swap by env/config on hackathon day.
"""
import os
import threading
from .. import config


class HumanChannel:
    def ask(self, question, options=None):
        """Ask the human and BLOCK for a reply. options=list for quick-tap replies."""
        raise NotImplementedError

    def instruct(self, message):
        """One-way proactive instruction (logistics, 'take the U3', 'bring cash')."""
        raise NotImplementedError


class ScriptedChannel(HumanChannel):
    """Deterministic offline answers keyed by a substring of the question."""
    def __init__(self, script):
        self.script = script          # list of (needle, answer)
        self.transcript = []

    def ask(self, question, options=None):
        answer = next((a for needle, a in self.script if needle.lower() in question.lower()),
                      (options[0] if options else "ok"))
        self.transcript.append(("ask", question, answer))
        return answer

    def instruct(self, message):
        self.transcript.append(("instruct", message, None))


class WebBridge:
    """Thread-safe hand-off between the mission thread (which BLOCKS on the human)
    and the async web server (which delivers the human's tap/typing). The server
    sets on_prompt/on_instruct to push to the SSE stream; /respond calls respond()."""
    def __init__(self):
        self._answer = None
        self._ready = threading.Event()
        self.pending = None
        self.on_prompt = None       # callback({question, options}) -> push to canvas
        self.on_instruct = None     # callback(message) -> push to canvas

    def ask(self, question, options):
        self.pending = {"question": question, "options": list(options or [])}
        self._answer = None
        self._ready.clear()
        if self.on_prompt:
            self.on_prompt(self.pending)
        self._ready.wait()          # block the mission thread until the panel replies
        self.pending = None
        return self._answer if self._answer is not None else (options[0] if options else "ok")

    def respond(self, answer):
        self._answer = answer
        self._ready.set()

    def instruct(self, message):
        if self.on_instruct:
            self.on_instruct(message)


class WebChannel(HumanChannel):
    """Human-in-the-loop over the live canvas: ask() blocks for a tap/typing,
    instruct() pushes a one-way logistics message. Backed by a WebBridge the
    server owns."""
    def __init__(self, bridge):
        self.bridge = bridge

    def ask(self, question, options=None):
        return self.bridge.ask(question, options)

    def instruct(self, message):
        self.bridge.instruct(message)


class WhatsAppChannel(HumanChannel):
    """Twilio WhatsApp sandbox. Set TWILIO_* + WHATSAPP_TO. Join the sandbox first
    (send the join code to the Twilio number from your phone). Verify current setup
    in Twilio's docs — sandbox mechanics drift."""
    def __init__(self):
        self.to = os.getenv("WHATSAPP_TO")
        # from twilio.rest import Client; self.client = Client(sid, token)

    def ask(self, question, options=None):  # TODO: send msg, poll inbound webhook/queue
        raise NotImplementedError

    def instruct(self, message):  # TODO: send one-way message
        raise NotImplementedError


class VoiceChannel(HumanChannel):
    """Speaks the ping aloud via Gemini TTS, then collects the reply through a base
    channel. The fun part: tone + language vary each ping, with a cheeky quip.

    Gemini 3.1 Flash TTS does 70+ languages + audio tags for tone/accent, so each
    line can be delivered in a different voice. Stub prints the styled line offline.
    """
    # (tone, language, a funny localized quip to prepend) — rotates per ping.
    STYLES = [
        ("hyped", "Russian", "Tovarisch! Big news —"),
        ("dry", "German", "Also gut, kurz und schmerzlos —"),
        ("wry", "English", "Right, don't panic, but —"),
        ("deadpan", "Russian", "Ne volnuysya… malenkiy vopros —"),
        ("theatrical", "German", "Achtung, Trommelwirbel —"),
        ("breezy", "English", "Quick one for you —"),
    ]

    def __init__(self, base=None, voice="Kore"):
        self.base = base or ScriptedChannel([])
        self.voice = voice
        self._i = 0

    def _next_style(self):
        s = self.STYLES[self._i % len(self.STYLES)]
        self._i += 1
        return s

    def _speak(self, text):
        tone, lang, quip = self._next_style()
        line = f"{quip} {text}"
        if config.USE_REAL_VOICE:
            return self._tts(line, tone, lang)
        print(f"   🔊 [{tone}, {lang}] “{line}”")

    def ask(self, question, options=None):
        self._speak(question)
        return self.base.ask(question, options)

    def instruct(self, message):
        self._speak(message)
        self.base.instruct(message)

    def _tts(self, text, tone, lang):
        from .. import llm
        return llm.gemini_tts(text, style=f"[{tone}, spoken in {lang}, comedic]", voice=self.voice)


def get_channel(script=None):
    """Factory. Defaults to ScriptedChannel for offline/deterministic demo.
    LUPO_HUMAN_CHANNEL=voice wraps the scripted/base channel with a spoken ping."""
    backend = os.getenv("LUPO_HUMAN_CHANNEL", "scripted")
    base = ScriptedChannel(script or [])
    if backend == "whatsapp":
        return WhatsAppChannel()
    if backend == "web":
        return WebChannel()
    if backend == "voice":
        return VoiceChannel(base=base)
    return base


class EmailChannel(HumanChannel):
    """SMTP send + IMAP poll. Laggy; fallback only."""
    def ask(self, question, options=None):  # TODO
        raise NotImplementedError

    def instruct(self, message):  # TODO
        raise NotImplementedError
