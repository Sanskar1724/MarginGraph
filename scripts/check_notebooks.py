"""Pre-commit hook: refuse notebooks that carry cell outputs.

Outputs are where a token leaked before (a printed environment, a login
cell). This only checks; it never rewrites the notebook, so it does not churn
files other branches are editing. Clear outputs with
``jupyter nbconvert --clear-output --inplace <file>`` before committing.
"""
import json
import sys


def main(paths: list[str]) -> int:
    bad = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            nb = json.load(fh)
        n = sum(len(c.get("outputs", [])) for c in nb.get("cells", []))
        if n:
            bad.append(f"{p}: {n} cell outputs")
    for b in bad:
        print(b, file=sys.stderr)
    return int(bool(bad))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
