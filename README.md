<div align="center">

# MarginGraph · Live demo (Hugging Face Space)

**A free Gradio app: try the demo store, upload your own orders CSV, or run the backtest.**

![license](https://img.shields.io/badge/license-MIT-green) ![demo](https://img.shields.io/badge/demo-Gradio-FF7C00?logo=gradio&logoColor=white) ![host](https://img.shields.io/badge/host-Hugging%20Face%20Spaces-FFD21E?logo=huggingface&logoColor=white) ![deps](https://img.shields.io/badge/deps-numpy%20%2B%20pandas-lightgrey)

[Full project (`main`)](https://github.com/Sanskar1724/MarginGraph) · [All modules](https://github.com/Sanskar1724/MarginGraph/blob/main/CONTRIBUTING.md#branches) · [Results](https://github.com/Sanskar1724/MarginGraph/blob/main/docs/RESULTS.md)

</div>

> This branch holds only the **Live demo (Hugging Face Space)** module of [MarginGraph](https://github.com/Sanskar1724/MarginGraph), a margin-aware e-commerce recommender (LightGBM ranker + MILP optimizer). The integrated, runnable project lives on `main`.

## What this module does

Self-contained (no package install): EASE on the top 2,000 items, logistic p(buy), exact solver for at most 2 add-ons. Backtest on Oct–Dec 2011 with simulated cost and stock: Hit@2 16.6% for plain top-2 vs 13.2% for MarginGraph, realized profit +22% (CI excludes 0), 0 margin-floor breaks.

## What's in this branch

| Path | What it is |
| --- | --- |
| `space/app.py` | Gradio UI: demo store, merchant upload, backtest, API tab |
| `space/core.py` | Model and optimizer |
| `space/build_artifacts.py` | Rebuilds `space/artifacts/` from the dataset |
| `space/DEPLOY.md` | Step-by-step free deploy |
| `tests/test_space_demo.py` | Tests |

## Run it

```bash
cd space && pip install -r requirements.txt && python app.py
```

Deploy: see [`space/DEPLOY.md`](space/DEPLOY.md).

## License

[MIT](LICENSE)
