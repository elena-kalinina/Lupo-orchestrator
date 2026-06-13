"""Event stream. Every coordination action emits an event; the canvas replays them.

This is what makes 'agents and humans coordinating' VISIBLE — the whole thesis on
one screen. Events are appended to a JSONL the frontend polls/replays.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

EVENT_LOG = Path(__file__).resolve().parent.parent / "data" / "events.jsonl"


class EventStream:
    def __init__(self, path=EVENT_LOG, echo=True, listener=None):
        self.path = Path(path)
        self.echo = echo
        self.listener = listener  # optional callback(ev_dict) -> live stream (e.g. SSE)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("")  # reset per run
        self.seq = 0

    def emit(self, kind, actor, **data):
        """kind: task|message|escalation|human_reply|budget|negotiation|decision|deal|preview."""
        self.seq += 1
        ev = {"seq": self.seq, "ts": datetime.now(timezone.utc).isoformat(),
              "kind": kind, "actor": actor, **data}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")
        if self.echo:
            self._print(ev)
        if self.listener:
            try:
                self.listener(ev)
            except Exception:
                pass
        return ev

    @staticmethod
    def _print(ev):
        icon = {"task": "→", "message": "💬", "escalation": "⚠ ", "human_reply": "🙋",
                "budget": "💶", "negotiation": "🤝", "decision": "✓", "deal": "🛍 "}.get(ev["kind"], "·")
        detail = ev.get("text") or ev.get("summary") or ""
        print(f"  {icon} [{ev['actor']:<12}] {ev['kind']:<11} {detail}")
