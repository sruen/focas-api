from focas_engine.returns import payout_rate, system_from_snapshot
from focas_engine.models import OddsSnapshot


def test_system_detection():
    snap = OddsSnapshot(home=2.3, draw=3.2, away=2.9)
    assert 89 <= payout_rate(snap) <= 96
    assert system_from_snapshot(snap).endswith("系")
