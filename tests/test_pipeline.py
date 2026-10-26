import json

import numpy as np
import pandas as pd

from margingraph import data, split
from margingraph.optimize import Policy, check_constraints, option_table, solve_enum, solve_milp
from margingraph.pipeline import run


def test_clean_drops_cancellations_and_fees(tiny_cfg):
    cfg, _ = tiny_cfg
    raw = data.read_raw(cfg["data"]["raw_path"])
    lines, log = data.clean(raw, cfg["data"]["product_code_regex"])
    assert not lines["invoice"].str.startswith("C").any()
    assert "POST" not in set(lines["item"])
    assert log["dropped_cancel_or_adjust"] >= 1 and log["dropped_non_product_codes"] >= 1


def test_split_is_temporal(tiny_cfg):
    cfg, _ = tiny_cfg
    lines, _, _ = data.load_or_build(cfg)
    s = split.temporal_split(lines, cfg["split"]["val_start"], cfg["split"]["test_start"])
    info = split.check_no_leakage(s)
    assert info["invoice_overlap"] == 0
    ev = split.make_events(s["test"], 2, 50, None, 0)
    assert all(t not in c for t, c in zip(ev["target"], ev["context"], strict=True))


def _random_case(rng, n=12):
    p = rng.random(n) * 0.2
    price = rng.uniform(1, 20, n)
    cost = price * rng.uniform(0.5, 0.95, n)
    over = rng.random(n) < 0.3
    stock = rng.integers(0, 5, n)
    return p, price, cost, over, stock


def test_milp_matches_enumeration_and_respects_rules():
    rng = np.random.default_rng(1)
    for mode in ("item", "bundle"):
        for disc in ((0.0,), (0.0, 0.1, 0.2)):
            pol = Policy(lam=1.0, overstock_weight=1.5, floor_mode=mode, discounts=disc)
            for _ in range(25):
                args = _random_case(rng)
                a = solve_milp(*args, pol, 2.0)
                b = solve_enum(*args, pol, 2.0)
                o = option_table(*args, pol, 2.0)
                val = lambda ch, o=o, disc=disc: sum(o["value"][j * len(disc) + disc.index(d)] for j, d in ch)
                assert abs(val(a) - val(b)) < 1e-6
                for ch in (a, b):
                    assert check_constraints(ch, args[1], args[2], pol) == 0
                    assert all(args[4][i] > 0 for i, _ in ch)


def test_end_to_end(tiny_cfg, tmp_path):
    cfg, _ = tiny_cfg
    summary = run(cfg, str(tmp_path / "results"), str(tmp_path / "artifacts"))
    e1 = summary["e1"]
    # the planted pairs must be found far above the shuffled null
    assert e1["real_hit@10"] > 2 * e1["shuffled_hit@10"]
    e8 = pd.read_csv(tmp_path / "results" / "e8_strategies_simulated_erp.csv")
    assert (e8.loc[e8.strategy.str.startswith("milp"), "violations"] == 0).all()
    e9 = json.loads((tmp_path / "results" / "e9_solver_check.json").read_text())
    assert e9["objective_agree"] == e9["checked"]
    # release gate: the reranker must beat popularity on the fixture too
    from margingraph import gate

    assert gate.check(tmp_path / "results")["passed"]

    import os

    from fastapi.testclient import TestClient

    os.environ["MARGINGRAPH_ARTIFACTS"] = str(tmp_path / "artifacts")
    from margingraph import api

    api.bundle.cache_clear()
    c = TestClient(api.app)
    r = c.post("/recommend", json={"basket": ["10003", "10005"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["addons"]) <= 2
    assert all(a["margin_pct"] >= 0.15 - 1e-9 for a in body["addons"])


def test_llm_compare_and_prompts():
    from margingraph.llm import build_prompt, compare

    assert "Mug" in build_prompt(["RED MUG"], "BLUE MUG")
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"event_id": np.repeat(np.arange(50), 20), "score": rng.random(1000), "llm": rng.random(1000)})
    df["label"] = (np.arange(1000) % 20 == 3).astype(int)
    out = compare(df, n_boot=50)
    assert set(out["a"]) == {"llm", "blend"}


def test_llm_stack_runs():
    from margingraph.llm import stack

    rng = np.random.default_rng(1)

    def fake(n):
        df = pd.DataFrame({"event_id": np.repeat(np.arange(n), 20), "score": rng.random(n * 20)})
        df["label"] = (np.arange(n * 20) % 20 == 0).astype(int)
        df["llm"] = df["label"] * 2 + rng.random(n * 20)  # informative LLM
        return df

    table, coef = stack(fake(200), fake(100), n_boot=100)
    assert table.loc[table.metric == "hit@1", "diff"].iloc[0] > 0
    assert set(coef.feature) >= {"llm", "lgbm"}
