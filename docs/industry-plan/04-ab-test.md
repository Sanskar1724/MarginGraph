# Phase 4: live A/B test on the pilot store

**Goal:** measure, on real shoppers, whether MarginGraph's add-ons raise gross profit per checkout without clearly hurting conversion. This is the only result that can be shown to the next store as proof. Win or lose, it gets written up.

**Needs:** Phase 3 done (store synced, offline gate passed, model live in staging), PR #12 merged, and the store's written OK to run the test.

**Done when:**

- [ ] The test plan below is filled in and saved (committed privately or emailed to the store) **before** the test starts.
- [ ] A one-week A/A test showed no difference beyond chance and no technical problems.
- [ ] The A/B test ran to its planned sample size and length, without early stopping.
- [ ] The result (main metric, guard metrics, CIs) is written up for the store, and, with the store's permission, as a case study.

## Why the size matters here

PR #12's replay on UCI already showed the pattern to expect, with about 500 requests per arm (`results/service/` on that branch):

| Treatment vs λ=0 | Conversion difference | Profit per request difference |
| --- | --- | --- |
| λ=1.0 | −4.8 pts [−9.0, −0.5] | +4.35 [−0.92, +13.23] |
| λ=0.5 | −2.8 pts [−7.1, +1.4] | +3.17 [−1.71, +11.81] |

The profit point estimates were positive, but every profit CI included zero, because profit per checkout is very noisy (a few big orders dominate). With a few hundred checkouts per arm, a real store test would most likely end "not proven". The test has to be sized for profit, not for conversion.

## Design

| | Choice | Why |
| --- | --- | --- |
| Unit | Visitor (or logged-in customer), sticky | The service hashes store + experiment name + `customer_id` (else `session_id`). **The cart must send a stable visitor id**, otherwise each request is bucketed at random |
| Split | 50/50 | Most power for a fixed traffic |
| Control | What the store shows today (its own "also bought" box or best sellers). If it shows nothing, MarginGraph at λ=0 (most relevant, no profit term) | The store's question is "is this better than what I have" |
| Treatment | MarginGraph at λ=0.5, the store's margin floor, max 2 add-ons | λ=0.5 had the smaller conversion cost offline (−1.1 pts Hit@2) and in replay |
| Main metric | Gross profit from add-ons per checkout (add-on revenue minus real unit cost) | The product's promise. One main metric only, so there is no picking afterwards |
| Guard metrics | Checkout conversion rate; add-on conversion; average order value; margin-floor breaks (must be exactly 0); API error rate; p95 latency; fallback share | Profit must not come from hurting the store |
| Analysis | Difference in means with a bootstrap 95% CI (`scripts/ab_report.py`, PR #12), same method as offline | Consistent with every other number in the repo |
| Decision rule | Roll out if the profit CI is above zero and checkout conversion is not clearly worse (its CI's lower end above −1 pt, our chosen bar). Otherwise keep the control and write up why | Set now, before seeing data |

If traffic allows a third arm, add MarginGraph at λ=0 too. It separates "better suggestions" from "profit-aware suggestions".

## Sample size and length

Use [`scripts/ab_sample_size.py`](../../scripts/ab_sample_size.py) with the **store's own pre-period data**, not the examples below.

1. From the 4 weeks before the test, compute profit from add-on-type purchases per checkout (or, if the store has no add-on box yet, profit per checkout), one row per checkout, into a CSV.
2. Run:

```bash
python scripts/ab_sample_size.py profit --csv preperiod.csv --column profit --rel-mde 0.10 --daily <checkouts per day>
python scripts/ab_sample_size.py conversion --base <current checkout conversion> --rel-mde 0.05 --daily <visitors per day>
```

3. Run for the **larger** of the two answers, in **whole weeks**, and at least 2 weeks.

Examples from the formula, to show the scale (alpha 0.05, power 0.8; these are calculations, not results):

| Main metric | Baseline | Smallest change to detect (relative) | Per arm | Total |
| --- | --- | --- | --- | --- |
| Add-on conversion | 5% | 20% (5% → 6%) | 8,155 | 16,310 |
| Add-on conversion | 5% | 10% | 31,231 | 62,462 |
| Add-on conversion | 15% | 20% | 2,400 | 4,800 |
| Profit per checkout, sd = 3 × mean | | 20% | 3,532 | 7,064 |
| Profit per checkout, sd = 5 × mean | | 20% | 9,812 | 19,624 |
| Profit per checkout, sd = 5 × mean | | 10% | 39,245 | 78,490 |

So a store with 300 checkouts a day needs about 8 weeks to detect a 20% change in a 5% add-on conversion. **A store with fewer than about 100 checkouts a day cannot give a conclusive profit result in a few weeks.** Pick the pilot store with this in mind (see Phase 7), or plan a longer test.

If the profit data is very skewed (a few huge orders), also report profit per checkout with each checkout's profit capped at its 99th percentile (decide the cap before the test), and the unit-profit measure `ab_report.py` already computes.

## Steps

### Before the test

- [ ] Fill the test plan (copy this block into `pilot1_test_plan.md`, keep it private, email it to the store):
  ```text
  Store: ...            Start date: ...         Planned end (whole weeks): ...
  Control: ...          Treatment: λ=0.5, floor ...%, max ... add-ons, discounts: none
  Main metric: gross add-on profit per checkout (real unit cost)
  Planned sample per arm: ... (from ab_sample_size.py, inputs: ...)
  Guard metrics and limits: floor breaks = 0; error rate < 1%; p95 < 300 ms; checkout conversion CI lower end > −1 pt
  Decision rule: ...
  Stop early only for: a guard metric failing (floor break, errors, latency), never for good or bad results
  ```
- [ ] Integrate the widget: the cart calls `POST /v1/recommend` with the basket and a stable visitor id, shows the add-ons, and sends `POST /v1/events` for clicks and add-to-carts. Purchases come from the order webhook. See `docs/API.md` (added by PR #12), section "Minimal integration". Call the API from the shop's server, not from shoppers' browsers, so the store key is never exposed (see Phase 5).
- [ ] For a control that is the store's own box: the response's variant tells the frontend which box to show. Check this works in staging for both variants.
- [ ] Turn the experiment on:
  ```bash
  curl -X PATCH $MG/v1/settings -H "X-API-Key: $KEY" -H 'content-type: application/json' \
    -d '{"experiment": {"enabled": true, "name": "aa1", "variants": [
          {"name": "control", "weight": 1, "overrides": {"lam": 0.5}},
          {"name": "treatment", "weight": 1, "overrides": {"lam": 0.5}}]}}'
  ```

### A/A week

- [ ] Run one week with both arms identical (above). Check: buckets close to 50/50 (sample ratio mismatch check: a chi-square test of the two counts should not be significant), events are logged for both, purchases are attributed, no errors.
- [ ] `ab_report.py` should show no significant difference. If it does, find the bug before going on.

### A/B

- [ ] Change the experiment `name` (this reshuffles visitors) and the treatment's overrides to the planned policy:
  ```bash
  curl -X PATCH $MG/v1/settings -H "X-API-Key: $KEY" -H 'content-type: application/json' \
    -d '{"experiment": {"enabled": true, "name": "ab1", "variants": [
          {"name": "control", "weight": 1, "overrides": {"lam": 0}},
          {"name": "treatment", "weight": 1, "overrides": {"lam": 0.5}}]}}'
  ```
- [ ] Watch only the guard metrics during the test (dashboard, `/metrics`). Do not look at the profit CI to decide when to stop.
- [ ] At the planned end:
  ```bash
  DATABASE_URL=<the service database> python scripts/ab_report.py --store pilot1
  ```
- [ ] Also look at the result by week (novelty effects) and by device, but treat those as exploration, not the decision.

### After

- [ ] Write up: plan, what ran, main metric with CI, guard metrics with CIs, decision, and what was surprising. Same honesty rules as the repo: a loss is reported as clearly as a win.
- [ ] Store report: private. Public case study: only with written permission, and only the aggregate numbers.
- [ ] If it won: roll out (experiment off, λ=0.5 for everyone), keep monitoring for 4 weeks.
- [ ] If it lost or was inconclusive: say so, check whether the conversion cost was the cause, and decide with the store whether to test a lower λ.

## Files involved

| File | Role |
| --- | --- |
| `scripts/ab_sample_size.py` | Sample size and length (new) |
| `src/margingraph/service/app.py`, `settings.py` (PR #12) | Buckets, overrides, event logging, `/v1/report` |
| `scripts/ab_report.py` (PR #12) | Bootstrap CIs from the service database |
| `src/margingraph/dashboard/` | Merchant view of the A/B result with CIs |
| `docs/launch/pilot-proposal.md` | What the store was promised |

## Prompt for a future Claude session

```text
Phase 4 of docs/industry-plan (04-ab-test.md). Pilot store traffic: <checkouts/day>, current
checkout conversion <x>, 4-week pre-period profit per checkout mean <m>, sd <s> (or I attach the
CSV). Control is <the store's own box / λ=0>. Please: (1) run scripts/ab_sample_size.py with these
and tell me the length in whole weeks; (2) fill in the test plan template from the phase file;
(3) list exactly what the store's developer must change in their cart (calls, visitor id, events)
using docs/API.md. Do not change the main metric or the decision rule from the phase file
unless I ask.
```

At the end of the test:

```text
The pilot A/B test ended. Here is scripts/ab_report.py's output and the test plan we fixed
beforehand: <paste>. Write the result up against the plan's decision rule, with every CI,
including guard metrics, and say clearly whether it is a win, a loss or inconclusive.
Draft (a) a private report for the store and (b) a public case-study paragraph with only
aggregate numbers, marked as needing the store's written permission.
```
