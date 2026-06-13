#!/usr/bin/env python3
"""Run the personal-shopper mission end to end (offline, deterministic).

    python scripts/run_mission.py

Stub mode: cached Vinted, scripted human, rule-based agents — no keys, no network.
Toggles: USE_REAL_GEMINI, LUPO_VINTED_LIVE, LUPO_HUMAN_CHANNEL=voice|whatsapp|web.
Scenario: LUPO_SCENARIO=brunch (default) | tomorrowland.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lupo.missions import shopping


def main():
    scenario = os.getenv("LUPO_SCENARIO", "brunch")
    print("=" * 74)
    print(f"LUPO — coordination layer · personal-shopper mission · [{scenario}]")
    print("=" * 74)
    ledger, events = shopping.run(scenario)
    print("\n" + "=" * 74)
    print(shopping.traceability(ledger))
    print("\nEvent stream written to data/events.jsonl ({} events) — feeds the canvas."
          .format(events.seq))


if __name__ == "__main__":
    main()
