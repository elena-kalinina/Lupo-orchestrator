"""Smoke tests — the coordination arc must hold end to end (offline)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lupo.missions import shopping


def test_mission_completes_under_budget():
    ledger, _ = shopping.run()
    assert ledger.spent() <= ledger.total_budget, "must stay within budget"
    assert all(c.status == "acquired" for c in ledger.components), "all components acquired"


def test_human_amendment_applied():
    ledger, _ = shopping.run()
    shoes = ledger.by_name("shoes")
    assert "ballet" in shoes.style_tags, "human amendment (ballet flats) should apply"


def test_negotiation_saved_money():
    ledger, _ = shopping.run()
    dress = ledger.by_name("dress")
    assert dress.final_price < dress.chosen["price"], "negotiation should beat asking price"


def test_event_stream_emitted():
    _, events = shopping.run()
    assert events.seq > 20, "coordination should emit a rich event stream for the canvas"


if __name__ == "__main__":
    test_mission_completes_under_budget()
    test_human_amendment_applied()
    test_negotiation_saved_money()
    test_event_stream_emitted()
    print("All coordination smoke tests passed.")
