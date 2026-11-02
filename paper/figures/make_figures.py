"""Build the paper's figures from the measured files in results/.

Run from the repo root:  python paper/figures/make_figures.py
The LLM numbers (Kaggle runs) are not in results/; they are copied from
docs/RESULTS.md, section "E5 LLM rerank".
Figures 6 and 7 read paper/figures/figdata/*.csv, small extracts of the PR #17
(results/public/) and PR #18 (results/retail_sim/) result files.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results"
OUT = Path(__file__).resolve().parent

BLUE, ORANGE, AQUA, GREY = "#2a78d6", "#eb6834", "#1baf7a", "#9a9993"
INK, INK2 = "#0b0b0b", "#52514e"

plt.rcParams.update({
    "font.family": "serif", "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": "#e4e3df", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "savefig.bbox": "tight", "savefig.dpi": 300,
})


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png")
    plt.close(fig)


# Fig 1: baseline ladder vs LightGBM, test Hit@10 with 95% CI
def fig_ladder():
    b = pd.read_csv(RES / "e3_baselines.csv")
    r = pd.read_csv(RES / "e5_rerank.csv")
    rows = b[(b.split == "test") & (b.metric == "hit@10")][["model", "mean", "ci_low", "ci_high"]]
    lg = r[(r.metric == "hit@10")]
    if "split" in lg:
        lg = lg[lg.split == "test"]
    lg = lg[lg.model.str.contains("lightgbm|rerank", case=False)] if "model" in lg else lg
    rows = pd.concat([rows, lg[["model", "mean", "ci_low", "ci_high"]].head(1)])
    names = {"popularity": "Popularity", "recent_pop": "Recent popularity", "repeat": "Repeat purchase",
             "copurchase": "Co-purchase", "als": "ALS", "itemknn": "ItemKNN", "ease": "EASE",
             "ease_decay": "Decayed EASE", "cust_ease": "Customer EASE", "text": "Text (TF-IDF)",
             "trend": "Trending (fresh)", "fresh_co": "Fresh co-purchase"}
    rows["label"] = rows.model.map(names).fillna("LightGBM rerank")
    rows = rows.sort_values("mean")
    fig, ax = plt.subplots(figsize=(3.4, 3.2))
    colors = [ORANGE if l == "LightGBM rerank" else BLUE for l in rows.label]
    y = range(len(rows))
    ax.barh(y, rows["mean"] * 100, color=colors, height=0.6)
    ax.errorbar(rows["mean"] * 100, y, xerr=[(rows["mean"] - rows.ci_low) * 100, (rows.ci_high - rows["mean"]) * 100],
                fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
    for yi, m, h in zip(y, rows["mean"], rows.ci_high):
        ax.text(h * 100 + 0.8, yi, f"{m*100:.1f}%", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(list(y), rows.label)
    ax.set_xlabel("Hit@10 on test (%), 95% bootstrap CI")
    ax.set_xlim(0, 45)
    ax.grid(axis="y", visible=False)
    save(fig, "fig1_ladder")


# Fig 2: relevance-profit frontier (ranker top-2 vs MILP lambda sweep)
def fig_frontier():
    s = pd.read_csv(RES / "e8_strategies_simulated_erp.csv")
    pick = ["ranker_top2"] + [f"milp_lam{l}" for l in ("0.0", "0.25", "0.5", "0.75", "1.0")]
    s = s.set_index("strategy").loc[pick]
    fig, ax = plt.subplots(figsize=(3.4, 2.5))
    m = s.iloc[1:]
    ax.plot(m.hit * 100, m.realized_profit, color=BLUE, lw=1.5, zorder=2)
    ax.errorbar(m.hit * 100, m.realized_profit,
                yerr=[m.realized_profit - m.realized_profit_lo, m.realized_profit_hi - m.realized_profit],
                fmt="o", color=BLUE, ms=4, elinewidth=0.8, capsize=2, label="MILP, 15% floor", zorder=3)
    rk = s.loc["ranker_top2"]
    ax.errorbar([rk.hit * 100], [rk.realized_profit],
                yerr=[[rk.realized_profit - rk.realized_profit_lo], [rk.realized_profit_hi - rk.realized_profit]],
                fmt="s", color=ORANGE, ms=5, elinewidth=0.8, capsize=2, label="Ranker top-2, no floor", zorder=3)
    for lam, (_, row) in zip(["0", "0.25", "0.5", "0.75", "1"], m.iterrows()):
        ax.annotate(f"λ={lam}", (row.hit * 100, row.realized_profit), textcoords="offset points",
                    xytext=(4, 6), fontsize=7, color=INK2, ha="left")
    ax.set_xlabel("Hit@2 on test (%)")
    ax.set_ylabel("Realized profit per basket (£)")
    ax.legend(frameon=False, fontsize=7, loc="lower left")
    save(fig, "fig2_frontier")


# Fig 3: ERP sensitivity, MILP lam=1 minus ranker top-2, realized profit
def fig_sensitivity():
    e = pd.read_csv(RES / "e11_erp_sensitivity_milp_vs_ranker.csv")
    e = e[e.metric == "realized_profit"].reset_index(drop=True)
    lab = {"[2.0, 8.0]": "Beta(2,8), mean 20%", "[4.0, 6.0]": "Beta(4,6), mean 40%", "[6.0, 4.0]": "Beta(6,4), mean 60%"}
    fig, ax = plt.subplots(figsize=(3.4, 2.3))
    col = {k: c for k, c in zip(lab, [BLUE, ORANGE, AQUA])}
    ylabels = []
    for i, r in e.iterrows():
        ax.errorbar([r["diff"]], [i], xerr=[[r["diff"] - r.ci_low], [r.ci_high - r["diff"]]], fmt="o",
                    color=col[r.margin_beta], ms=4, elinewidth=0.9, capsize=2)
        ylabels.append(f"{lab[r.margin_beta].split(', ')[1]}, seed {r.erp_seed}")
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(e)), ylabels, fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("Realized profit gain per basket (£), 95% CI")
    ax.set_ylabel("Simulated gross margin")
    ax.grid(axis="y", visible=False)
    save(fig, "fig3_sensitivity")


# Fig 4: LLM vs LightGBM on the same 1,000 test slates (Hit@5)
def fig_llm():
    rows = [("Qwen2.5-1.5B LoRA fine-tuned", 7.8), ("Random order of slate", 11.6),
            ("Blend: LightGBM + fine-tuned", 16.2), ("Qwen2.5-1.5B zero-shot", 16.8), ("Qwen2.5-3B zero-shot", 16.6),
            ("Blend: LightGBM + 3B", 22.3), ("Blend: LightGBM + 1.5B", 23.2),
            ("Stacker: LightGBM + 3B", 27.5), ("LightGBM alone", 27.6)]
    fig, ax = plt.subplots(figsize=(3.4, 2.8))
    y = range(len(rows))
    ax.barh(y, [v for _, v in rows], color=[ORANGE if n == "LightGBM alone" else GREY if n.startswith("Random") else BLUE for n, _ in rows], height=0.6)
    for yi, (_, v) in zip(y, rows):
        ax.text(v + 0.5, yi, f"{v:.1f}%", va="center", fontsize=7.5, color=INK)
    ax.set_yticks(list(y), [n for n, _ in rows])
    ax.set_xlabel("Hit@5 on 1,000 test baskets, top-20 slates (%)")
    ax.set_xlim(0, 33)
    ax.grid(axis="y", visible=False)
    save(fig, "fig4_llm")


# Fig 5: calibration reliability (test)
def fig_reliability():
    r = pd.read_csv(RES / "e7_reliability_test.csv")
    r = r[r.mean_pred > 1e-5]
    fig, ax = plt.subplots(figsize=(3.0, 2.5))
    lo, hi = 1e-4, 0.06
    ax.plot([lo, hi], [lo, hi], color=GREY, lw=0.8, ls="--", label="Perfect calibration")
    ax.plot(r.mean_pred, r.frac_pos, "o-", color=BLUE, ms=4, lw=1.5, label="Isotonic-calibrated LightGBM")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("Mean predicted p(accept)")
    ax.set_ylabel("Observed acceptance rate")
    ax.legend(frameon=False, fontsize=7)
    save(fig, "fig5_reliability")


DATA = OUT / "figdata"


# Fig 6: LightGBM minus best baseline, Hit@10 with paired 95% CI, per dataset (PR #17 runs)
def fig_multidataset():
    d = pd.read_csv(DATA / "multi_dataset.csv", comment="#")
    d["label"] = d.dataset + d.run.map({"default": "", "repeat-first": " (repeat-first pool)"})
    d = d.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    for i, r in d.iterrows():
        c = AQUA if r.run == "repeat-first" else (ORANGE if r.ci_low > 0 else (GREY if r.ci_high > 0 else "#c8553d"))
        ax.errorbar(r["diff"], i, xerr=[[r["diff"] - r.ci_low], [r.ci_high - r["diff"]]], fmt="o", color=c,
                    ecolor=c, elinewidth=1.2, capsize=2.5, ms=4.5, mfc="white" if r.run == "repeat-first" else c)
        ax.text(11.3, i, f"{r['diff']:+.1f} [{r.ci_low:+.1f}, {r.ci_high:+.1f}]  n={r.test_baskets:,}",
                va="center", fontsize=6.8, color=INK)
    ax.axvline(0, color=INK2, lw=0.8)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels(d.label, fontsize=7.5)
    ax.set_xlim(-5, 11)
    ax.set_xlabel("Hit@10 gain over best baseline (points)")
    ax.grid(axis="y", visible=False)
    save(fig, "fig6_multidataset")


# Fig 7: cumulative add-on profit in the 30-day store simulation, replay acceptance (PR #18)
def fig_retail_sim():
    d = pd.read_csv(DATA / "retail_sim_daily_replay.csv", comment="#")
    names = {"ranker_top2": ("Ranker top-2 (no floor)", GREY, "-"),
             "margingraph_item_floor": ("MarginGraph, item floor", ORANGE, "-"),
             "margingraph_bundle_floor": ("MarginGraph, bundle floor", BLUE, "--"),
             "margingraph_overstock_w2": ("MarginGraph, overstock $w{=}2$", AQUA, ":")}
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    for k, (lab, c, ls) in names.items():
        g = d[d.policy == k].sort_values("day")
        ax.plot(g.day + 1, g.profit.cumsum(), label=lab, color=c, ls=ls, lw=1.4)
    ax.set_xlabel("Simulated day")
    ax.set_ylabel("Cumulative add-on profit (GBP)")
    ax.set_xlim(1, 30)
    ax.legend(frameon=False, fontsize=6.8, loc="upper left")
    save(fig, "fig7_retail_sim")


# Fig 0: system overview diagram
def fig_architecture():
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(7.0, 2.3))
    ax.set_xlim(0, 100); ax.set_ylim(0, 32); ax.axis("off")
    boxes = [
        (1, "Basket +\ncustomer\nhistory", "input", "#eef2f7"),
        (21, "Retrieval\n11 sources\n150 candidates", "Stage 1a", "#e3eefb"),
        (41, "LightGBM\nLambdaRank\n35 features", "Stage 1b", "#e3eefb"),
        (61, "Isotonic\ncalibration\n$p_i$ for top 20", "Stage 1c", "#e3eefb"),
        (81, "MILP optimizer\nmax value\n$\\leq$ 2 add-ons", "Stage 2", "#fdebe2"),
    ]
    for x, t, lab, c in boxes:
        ax.add_patch(FancyBboxPatch((x, 9), 17, 15, boxstyle="round,pad=0.4,rounding_size=1.5", fc=c, ec=INK2, lw=0.8))
        ax.text(x + 8.5, 16.5, t, ha="center", va="center", fontsize=7.6, color=INK)
        ax.text(x + 8.5, 26.3, lab, ha="center", va="center", fontsize=7.2, color=INK2, style="italic")
    for x in (18.6, 38.6, 58.6, 78.6):
        ax.annotate("", xy=(x + 2.2, 16.5), xytext=(x, 16.5), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=0.9))
    ax.text(89.5, 4.2, "hard rules: margin $\\geq$ 15%, in stock,\noverstock weight $w_i\\in[1,2]$", ha="center", va="center", fontsize=6.8, color=ORANGE)
    ax.text(30, 4.2, "store data: invoices, prices, product text; cost and stock from the ERP (simulated here)", ha="center", va="center", fontsize=6.8, color=INK2)
    save(fig, "fig0_architecture")


# Fig 8: candidate-pool recall, UCI-tuned order vs repeat-first order (PR #17)
def fig_pool():
    d = pd.read_csv(DATA / "multi_dataset.csv", comment="#")
    ds = ["Dunnhumby", "Instacart"]
    fig, axes = plt.subplots(1, 2, figsize=(5.6, 2.3))
    for ax, col, lab in [(axes[0], "pool_recall", "Pool recall (%)"), (axes[1], "diff", "Hit@10 gain vs repeat (pts)")]:
        for k, (run, c) in enumerate([("default", GREY), ("repeat-first", AQUA)]):
            v = [float(d[(d.dataset == x) & (d.run == run)][col].iloc[0]) for x in ds]
            xs = [i + (k - 0.5) * 0.36 for i in range(len(ds))]
            ax.bar(xs, v, width=0.34, color=c, label="UCI-tuned order" if run == "default" else "repeat-first order")
            for xi, vi in zip(xs, v):
                ax.text(xi, vi + (1 if vi >= 0 else -1), f"{vi:+.1f}" if col == "diff" else f"{vi:.1f}",
                        ha="center", va="bottom" if vi >= 0 else "top", fontsize=7)
        ax.set_xticks(range(len(ds))); ax.set_xticklabels(ds); ax.set_ylabel(lab)
        ax.axhline(0, color=INK2, lw=0.7); ax.grid(axis="x", visible=False)
    axes[0].set_ylim(0, 85); axes[1].set_ylim(-6, 13)
    axes[0].legend(frameon=False, fontsize=6.8, loc="upper left")
    fig.tight_layout()
    save(fig, "fig8_pool_order")


# Fig 9: Ta Feng with ASSET read as unit cost: hit rate and profit per policy (PR #17)
def fig_tafeng_floor():
    pol = ["Ranker top-2\n(no floor)", "MILP $\\lambda$=0\nitem floor", "MILP $\\lambda$=0.5\nitem floor", "MILP $\\lambda$=1\nbundle floor"]
    hit = [10.1, 5.3, 5.2, 5.8]
    prof = [0.61, 0.69, 0.76, 0.84]
    fig, axes = plt.subplots(1, 2, figsize=(5.8, 2.3))
    for ax, v, lab, fmt in [(axes[0], hit, "Hit@2 (%)", "{:.1f}"), (axes[1], prof, "Realized profit / basket", "{:.2f}")]:
        ax.bar(range(4), v, color=[GREY, ORANGE, ORANGE, BLUE], width=0.6)
        for i, x in enumerate(v):
            ax.text(i, x * 1.02, fmt.format(x), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(range(4)); ax.set_xticklabels(pol, fontsize=6.3); ax.set_ylabel(lab)
        ax.grid(axis="x", visible=False); ax.set_ylim(0, max(v) * 1.2)
    fig.tight_layout()
    save(fig, "fig9_tafeng_floor")


if __name__ == "__main__":
    fig_ladder(); fig_frontier(); fig_sensitivity(); fig_llm(); fig_reliability()
    fig_multidataset(); fig_retail_sim()
    fig_architecture(); fig_pool(); fig_tafeng_floor()
    print("figures written to", OUT)
