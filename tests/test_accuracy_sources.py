import numpy as np
import pandas as pd

from margingraph import models as M


def _lines(rows):
    return pd.DataFrame(rows, columns=["invoice", "item", "ts"]).assign(ts=lambda d: pd.to_datetime(d["ts"]))


def test_fresh_uses_only_sales_from_earlier_days():
    idx = M.ItemIndex(["A", "B", "C"])
    stream = _lines(
        [
            ("1", "A", "2011-10-03 10:00"), ("1", "B", "2011-10-03 10:00"),
            ("2", "A", "2011-10-05 09:00"), ("2", "C", "2011-10-05 09:00"),  # same day as the event
        ]
    )
    f = M.Fresh(idx, days=14)
    f.set_stream(stream)
    out = f.score_time([[0]], [pd.Timestamp("2011-10-05 15:00")])
    # invoice 2 is from the event's own day, so a nightly job has not seen it yet
    assert out["fresh_co"][0].tolist() == [0.0, 1.0, 0.0]
    assert out["trend"][0].tolist() == [1.0, 1.0, 0.0]
    nxt = f.score_time([[0]], [pd.Timestamp("2011-10-06 08:00")])
    assert nxt["fresh_co"][0].tolist() == [0.0, 1.0, 1.0]


def test_text_similarity_finds_colour_variants():
    desc = np.array(["PINK EGG COSY", "BLUE EGG COSY", "RED METAL LANTERN", "WHITE METAL LANTERN", "TEA TOWEL"])
    t = M.TextSim(desc)
    s = t.score([[0]], [""])[0]
    assert s.argmax() == 1 and s[0] == 0.0


def test_customer_ease_scores_from_past_items():
    idx = M.ItemIndex(["A", "B", "C"])
    hist = pd.DataFrame({"customer": ["c1", "c1"], "item": ["A", "B"]})
    rep = M.Repeat(hist, idx)
    B = np.array([[0, 1, 2], [3, 0, 4], [5, 6, 0]], dtype=np.float32)
    ce = M.CustomerEASE(B, {"repeat": rep})
    out = ce.score([[], []], ["c1", "unknown"])
    assert out[0].tolist() == [3.0, 1.0, 6.0]
    assert out[1].tolist() == [0.0, 0.0, 0.0]


def test_decay_weights_halve_per_half_life():
    lines = _lines([("1", "A", "2011-01-01"), ("2", "A", "2011-01-11"), ("3", "B", "2011-01-21")])
    w = M.decay_weights(lines, half_life_days=10)
    assert np.allclose(w, [0.25, 0.5, 1.0])
