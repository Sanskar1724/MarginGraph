"""scripts/ab_sample_size.py against the standard two-proportion and two-mean formulas."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("ab_sample_size", Path(__file__).resolve().parents[1] / "scripts" / "ab_sample_size.py")
ab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ab)


def test_conversion_sample_size():
    # 5% -> 6%, alpha 0.05 two-sided, power 0.8: (1.96 + 0.8416)^2 * (0.0475 + 0.0564) / 0.01^2 = 8,155
    assert ab.n_conversion(0.05, 0.20) == 8155
    assert ab.n_conversion(0.05, 0.10) > ab.n_conversion(0.05, 0.20)


def test_mean_sample_size():
    # sd 1, delta 0.1: 2 * 7.849 / 0.01 = 1,570
    assert ab.n_mean(1.0, 0.1) == 1570
