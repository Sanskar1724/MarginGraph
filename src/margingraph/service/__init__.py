"""Production serving layer: multi-store API, nightly batch training, cache, DB.

The research pipeline (``margingraph run``) measures the method; this package
runs it for real stores. Both share ``CandidateGenerator``, ``Reranker`` and
the Stage 2 solvers, so online and offline scores come from the same code.
"""
