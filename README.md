# MarginGraph

### Margin-aware e-commerce recommendations: a ranker for relevance, an optimizer for profit

MarginGraph recommends add-on products that customers are likely to buy **and** that keep the retailer profitable. Stage 1 finds relevant products. Stage 2 uses mathematical optimization to choose which ones to show, under hard business rules (a 15% margin floor, at most 2 add-ons, discount limits, overstock priority).

> **Status: research prototype.** The architecture is built. Stage 1 is being rebuilt on real data, and no performance claims are made yet. Every number this project reports will come from an experiment in this repo.

---

## Why

Most recommenders optimize for clicks or conversion and ignore economics. A relevant item can still be a bad recommendation for the retailer if it has a thin margin, needs a deep discount, or adds to stock that is already low. MarginGraph adds explicit profit, margin and inventory logic on top of relevance, without letting a language model make financial decisions.

## Architecture

```text
Customer history / cart
        │
        ▼
Stage 1a: Candidate retrieval   (co-purchase, repeat purchase, category, popularity, ALS)
        │  20–50 candidates
        ▼
Stage 1b: Reranker              (LightGBM baseline vs fine-tuned LLM reading product titles)
        │  relevance score → calibrated purchase probability p(accept)
        ▼
Stage 2: PuLP optimizer         (maximize expected profit under business constraints)
        │
        ▼
Up to 2 margin-safe add-ons
```

**Stage 2 objective**

```text
maximize   Σ_i  (P_i·(1 − d) − C_i) · p_accept_i · w_i · x_i

subject to Σ_i x_i ≤ 2                         (max add-ons)
           post-discount margin ≥ 15%          (margin floor)
           x_i ∈ {0, 1}
```

`P` = price, `C` = cost, `d` = discount, `p_accept` = calibrated purchase probability from Stage 1, `w` = overstock weight (1.0–2.0), `x` = select or not.

**Design rules**

- The LLM ranks products; it never sets prices or overrides constraints.
- Purchase probability comes from the relevance model, so the optimizer cannot push irrelevant high-margin items.
- Business rules are enforced by deterministic code and re-checked on every output.

## Data

| Dataset | Role |
| --- | --- |
| [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) | Primary: real invoices (baskets), real prices, product descriptions |
| H&M Personalized Fashion (Kaggle) | Scale-up option with richer product text |
| Simulated ERP fields | Cost, stock level and overstock flags where real data is unavailable; always labelled as simulated |
| Your own store | `margingraph sync csv / shopify / woocommerce` loads a store's products, orders, cost and stock; see [docs/CONNECTORS.md](docs/CONNECTORS.md) |

## Evaluation

| Area | Metrics |
| --- | --- |
| Relevance | Hit@5, MRR@5, Recall@10, candidate Recall@50, invalid-output rate |
| Economics | Expected profit per session, net margin, profit vs relevance trade-off |
| Inventory | Units cleared and sessions to clear (sequential stock simulation) |
| Reliability | Margin-floor violations, solver failures, latency |
| Statistics | Paired bootstrap 95% CIs over sessions, chance level reported with every metric |

## Roadmap

**Stage 1 (current focus)**

- [ ] Data signal audit (co-purchase lift vs a shuffled null)
- [ ] Strict temporal train / validation / test split
- [ ] Baseline ladder: popularity, repeat purchase, co-purchase, ALS
- [ ] Candidate recall at K = 20 and 50
- [ ] Rerankers: LightGBM vs zero-shot LLM vs fine-tuned LLM (go/no-go gate)

**Stage 2 (after the Stage 1 gate)**

- [ ] Calibrate p(accept)
- [ ] Strategy comparison across discounts and overstock weights
- [ ] Richer constraints (bundle margin, discount as a decision variable)
- [ ] Sequential inventory simulation
- [ ] Sensitivity to simulated ERP assumptions

**Pilot**

- [ ] FastAPI service with a fallback path
- [ ] Gradio demo
- [ ] Shopify development-store integration

Full plan: [`docs/experiment_plan.md`](docs/experiment_plan.md)

## Repository layout

```text
notebooks/   prototype notebooks (V1, V2): kept for history, results not valid
docs/        project report and experiment plan
```

The earlier notebooks are kept as history. Their reported numbers come from mock or randomly generated data and are not results. `docs/experiment_plan.md` explains why.

## Setup (free)

Everything runs on free tools: a laptop or Colab CPU for data prep, baselines and the optimizer; Kaggle Notebooks or a free Colab T4 GPU for the LLM steps; Parquet + DuckDB instead of a database.

```bash
pip install pandas polars duckdb pyarrow scikit-learn lightgbm implicit pulp
# LLM steps (GPU): pip install unsloth trl peft bitsandbytes transformers datasets
```

**Secrets:** never put keys in notebooks. In Colab, add `HF_TOKEN`, `KAGGLE_USERNAME` and `KAGGLE_KEY` under *Secrets*, then:

```python
from google.colab import userdata
HF_TOKEN = userdata.get("HF_TOKEN")
```

## Tech stack

`Python` · `pandas / Polars` · `DuckDB` · `LightGBM` · `implicit` · `Qwen2.5 / Llama 3.1 + QLoRA (Unsloth)` · `PuLP (CBC)` · `Colab / Kaggle`

---

**MarginGraph: let the model understand the customer, and let optimization protect the margin.**
