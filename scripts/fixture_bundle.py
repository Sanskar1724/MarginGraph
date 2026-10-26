"""Build a model bundle from the tiny synthetic fixture in tests/conftest.py.

Used by CI to run the API, load test and quality gate without the real
dataset. Nothing produced here is a reported number.

    python scripts/fixture_bundle.py /tmp/fixture
    # -> /tmp/fixture/results/*.csv and /tmp/fixture/artifacts/bundle.pkl
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from conftest import tiny_config  # noqa: E402

from margingraph.pipeline import run  # noqa: E402


def main(out: str) -> None:
    d = Path(out)
    d.mkdir(parents=True, exist_ok=True)
    cfg = tiny_config(d)
    run(cfg, str(d / "results"), str(d / "artifacts"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "fixture_out")
