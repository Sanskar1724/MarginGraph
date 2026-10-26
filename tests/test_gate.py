import pandas as pd

from margingraph import gate


def _write(d, ranker_hit10, pop_hit10):
    pd.DataFrame(
        [{"model": "popularity", "metric": "hit@10", "mean": pop_hit10, "ci_low": pop_hit10 - 0.01,
          "ci_high": pop_hit10 + 0.01, "n": 100, "split": "test"},
         {"model": "popularity", "metric": "hit@10", "mean": 0.99, "ci_low": 0.98,
          "ci_high": 1.0, "n": 100, "split": "val"}]
    ).to_csv(d / "e3_baselines.csv", index=False)
    pd.DataFrame(
        [{"model": "lightgbm", "metric": "hit@10", "mean": ranker_hit10, "ci_low": ranker_hit10 - 0.05,
          "ci_high": ranker_hit10 + 0.05, "n": 100}]
    ).to_csv(d / "e5_rerank.csv", index=False)


def test_gate_passes_and_fails(tmp_path):
    _write(tmp_path, 0.30, 0.10)
    assert gate.main([str(tmp_path)]) == 0
    _write(tmp_path, 0.08, 0.10)
    assert gate.main([str(tmp_path)]) == 1
    # mean clears popularity but the CI lower bound does not
    _write(tmp_path, 0.12, 0.10)
    assert gate.check(tmp_path)["passed"]
    assert not gate.check(tmp_path, strict=True)["passed"]


def test_committed_results_pass_gate():
    """The numbers in results/ come from the real Online Retail II run."""
    assert gate.check("results", strict=True)["passed"]
