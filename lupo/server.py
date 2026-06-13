"""Live coordination backend.

Runs a Lupo mission in a background thread and streams every coordination event
to the canvas over Server-Sent Events, while collecting the human's approve /
amend / confirm replies from the web panel (the web human-in-the-loop channel).
When USE_REAL_VOICE is on, each human ping is also spoken via Gemini TTS and the
audio is played in the browser.

Run:  python -m lupo.server         (then open http://127.0.0.1:8000)
"""
import asyncio
import json
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .events import EventStream
from .human.channel import WebChannel, WebBridge
from .missions import shopping

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
AUDIO_DIR = FRONTEND / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Lupo coordination canvas")
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")
app.mount("/data", StaticFiles(directory=str(ROOT / "data")), name="data")


class Broker:
    """Fan-out of mission messages to all connected SSE clients, with replay of
    the run-so-far for late joiners."""
    def __init__(self):
        self.loop = None
        self.subscribers = set()
        self.history = []

    def bind_loop(self, loop):
        self.loop = loop

    def reset(self):
        self.history = []

    def publish(self, msg):
        self.history.append(msg)
        if self.loop:
            for q in list(self.subscribers):
                self.loop.call_soon_threadsafe(q.put_nowait, msg)

    async def subscribe(self):
        q = asyncio.Queue()
        for m in self.history:
            q.put_nowait(m)
        self.subscribers.add(q)
        try:
            while True:
                yield await q.get()
        finally:
            self.subscribers.discard(q)


broker = Broker()
bridge = WebBridge()
_run_lock = threading.Lock()
_running = False


def _speak(text):
    """Best-effort Gemini TTS -> a WAV under frontend/audio. Returns a /static URL or None."""
    if not config.USE_REAL_VOICE:
        return None
    try:
        from . import llm
        name = f"ping_{uuid.uuid4().hex[:8]}.wav"
        llm.gemini_tts(text, out_path=str(AUDIO_DIR / name))
        return f"/static/audio/{name}"
    except Exception:
        return None


def _on_prompt(prompt):
    """WebBridge calls this when the coordinator asks the human something."""
    broker.publish({"type": "prompt", "question": prompt["question"],
                    "options": prompt["options"], "audio_url": _speak(prompt["question"])})


def _on_instruct(message):
    broker.publish({"type": "instruct", "message": message, "audio_url": _speak(message)})


bridge.on_prompt = _on_prompt
bridge.on_instruct = _on_instruct


def _run_mission(scenario):
    global _running
    try:
        events = EventStream(listener=lambda ev: broker.publish({"type": "event", **ev}))
        human = WebChannel(bridge)
        shopping.run(scenario, human=human, events=events)
    except Exception as e:
        broker.publish({"type": "event", "kind": "decision", "actor": "coordinator",
                        "text": f"(mission error: {e})"})
    finally:
        broker.publish({"type": "done"})
        _running = False


@app.get("/", response_class=HTMLResponse)
def index():
    return (FRONTEND / "canvas.html").read_text(encoding="utf-8")


@app.get("/healthz")
def healthz():
    return {"ok": True, "voice": config.USE_REAL_VOICE, "fal": config.USE_REAL_FAL,
            "gemini": config.USE_REAL_GEMINI, "pioneer": config.USE_PIONEER}


@app.post("/run")
async def run(req: Request):
    global _running
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    scenario = body.get("scenario", "brunch")
    if scenario not in shopping.SCENARIOS:
        return JSONResponse({"error": f"unknown scenario {scenario}"}, status_code=400)
    with _run_lock:
        if _running:
            return JSONResponse({"error": "a mission is already running"}, status_code=409)
        _running = True
    broker.reset()
    threading.Thread(target=_run_mission, args=(scenario,), daemon=True).start()
    return {"started": scenario}


@app.post("/respond")
async def respond(req: Request):
    body = await req.json()
    answer = (body or {}).get("answer", "")
    bridge.respond(answer)
    return {"ok": True, "answer": answer}


@app.get("/stream")
async def stream():
    broker.bind_loop(asyncio.get_event_loop())

    async def gen():
        async for msg in broker.subscribe():
            yield f"data: {json.dumps(msg)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def main():
    import uvicorn
    broker.bind_loop(asyncio.new_event_loop())
    uvicorn.run("lupo.server:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
