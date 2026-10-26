# Phase 5: production hardening

**Goal:** make the service safe to run for real stores: secure, observable, isolated per store, and compliant with data-protection law. Most of the base is in PR #12; this phase lists what it already does and what is still missing.

**Done when:** every box below is ticked or has a written reason why it does not apply yet.

## What PR #12 already gives you (check after merging)

From `docs/SERVICE.md` and `docs/API.md` on that branch, covered by `tests/test_service.py` (19 tests, also run against Postgres 16):

- Store API keys (stored hashed), an admin key, key rotation (`POST /v1/admin/stores/{id}/rotate-key`).
- Signed order webhooks (HMAC-SHA256 with a per-store secret).
- Per-store rate limits (shared through Redis when several copies run).
- Production mode refuses to start without `MARGINGRAPH_ADMIN_KEY`.
- Store isolation (tested), per-store settings with validation, per-store model registry, quality gate and rollback.
- Fallback to margin-safe best sellers on any model failure or timeout (`latency_budget_ms`, default 300).
- Hard rules on every answer: active, in stock, known cost, not in the basket, margin at or above the floor.
- `/health`, `/ready`, Prometheus `/metrics` (requests, fallbacks, model errors, latency histogram, attributed add-ons).
- Pickled model bundles are only loaded from the service's own artifacts folder, never uploaded through the API.
- CI from PR #11: ruff, tests on Python 3.10 and 3.12, gitleaks secret scan, quality gate, Docker build and load test.

## Security

- [ ] **Never put a store key in a browser.** The store API key is a secret. The shop's own backend (or a Shopify app proxy / server-side function) should call `/v1/recommend`. If browser calls are needed later, add a separate *publishable* key that can only call `/v1/recommend` and `/v1/events`, with strict CORS.
- [ ] Set `MARGINGRAPH_CORS_ORIGINS` to the store's domains (default is `*`).
- [ ] HTTPS only. Free hosts (HF Spaces, Render) give HTTPS; never expose plain HTTP.
- [ ] Admin key: long and random (`python -c "import secrets; print(secrets.token_urlsafe(48))"`), stored only in the host's secrets settings. Rotate it if it is ever pasted anywhere.
- [ ] Dependency audit in CI: add a job running `pip-audit` (free) on the installed packages; fail on known high-severity issues.
- [ ] GitHub settings: enable Dependabot alerts and secret scanning (free on public repos); protect `main` (require PR and green CI).
- [ ] Dashboard: always set `MARGINGRAPH_DASHBOARD_TOKEN` when it is reachable from the internet; add CSRF protection before exposing it without the token (open item from [dashboard.md](../worklog/dashboard.md)).
- [ ] Input limits: maximum basket size and request body size (check what PR #12 enforces; add limits if missing).
- [ ] Pickle: keep the rule that bundles come only from your own training. If you move bundles to Hugging Face Hub (Phase 6), use a **private** repo and pin the exact file revision you load. Longer term, save LightGBM in its own text format and the matrices as `.npz` instead of pickle.
- [ ] Write `SECURITY.md`: how to report a vulnerability (an email address), and what you promise (reply within a few days).

## Monitoring and alerts

- [ ] Scrape `/metrics` with Grafana Cloud's free tier (or Grafana Agent / Alloy on the same host).
- [ ] Dashboard panels: requests per store, p50/p95 latency, fallback share by reason, model errors, attributed add-ons, rate-limited requests.
- [ ] Alerts (email is free):
  - p95 latency above the store's `latency_budget_ms` for 10 minutes
  - error rate above 1% for 10 minutes
  - fallback share above 20% for an hour (the model is broken or missing)
  - any margin-floor break (should be impossible; alert if the counter ever appears)
  - active model older than 3 days (the nightly job stopped)
- [ ] Uptime check on `/health` every 5 minutes (UptimeRobot or Better Stack free tiers). Note that a free host that sleeps will show as down; that is real downtime for the shop, which still gets the store's own fallback if the cart has one.
- [ ] Logs: structured JSON logs with `request_id`, store, variant, latency, fallback reason. No customer data in logs.
- [ ] Weekly check (5 minutes, put it in your calendar): metrics, model age, disk and database size against free-tier limits.

## Multi-tenant

- [ ] Memory per store: a 4,700-item store needs about 300 MB per loaded model (`MARGINGRAPH_MAX_LOADED_MODELS`, default 4). On a 16 GB free Space that is a few dozen small stores; on Render's 512 MB free tier, one small store.
- [ ] **Large catalogs:** replace the dense item-item matrices (EASE, ItemKNN, co-purchase) with sparse top-k neighbour lists (for example the 200 best neighbours per item). Bundle size and RAM then grow linearly with the catalog, not with its square. Gate: Hit@10 on UCI within the CI of the dense version. This is the main code change needed before a store with tens of thousands of products. *Source: SERVICE.md "Limits".*
- [ ] Training isolation: train in the nightly job (`margingraph batch`) or on Kaggle, never through the in-process admin train endpoint for anything but tiny stores.
- [ ] Per-store quotas: requests per month per plan (the business plan's Free tier needs this), enforced next to the rate limit.
- [ ] A test that one store's key can never read or change another store's catalog, orders, settings or models (PR #12 tests isolation; extend it to every route when new routes are added).
- [ ] Store offboarding: one admin command that deletes a store's rows, models and logs (see GDPR below).

## Data protection (GDPR, UK GDPR, India DPDP Act 2023, CCPA)

This is a checklist for a student project, not legal advice. The promises already made to stores are in [privacy-and-data.md](../launch/privacy-and-data.md); the service must actually keep them.

- [ ] **Roles:** the store is the data controller; you are the processor. Write a short **data processing agreement** (DPA) template: what you process, why, where, for how long, sub-processors (your free hosts), breach notice within 72 hours, deletion at the end. Have the pilot store sign it with the pilot agreement.
- [ ] **Minimize:** ask for no names, emails, phones or addresses. Customer ids should be random codes. Add a check in the connectors that **warns and drops** any column that looks like an email or phone number.
- [ ] **Pseudonymize:** hash `customer_id` and `session_id` with a per-store secret salt before storing them in the service database.
- [ ] **Deletion:**
  - Per customer: an endpoint (for example `DELETE /v1/customers/{id}`) that removes that customer's orders and logs, for a store that receives a deletion request. **Not in PR #12 yet.**
  - Per store: delete everything within 30 days of the pilot ending, including backups and models, as promised. **Not in PR #12 yet.**
- [ ] **Retention:** a nightly job that deletes request and event logs older than a set window (for example 13 months, or the pilot length plus 30 days).
- [ ] **Region:** choose EU regions on Neon or Supabase for EU/UK stores; tell the store which provider and region before the pilot (promised in the privacy note).
- [ ] **Record of processing:** a one-page `docs/compliance/records.md` listing data, purpose, storage, retention, sub-processors.
- [ ] **No raw store data in git,** ever. `data/` is ignored; keep it that way, and never commit a pilot store's results.
- [ ] **Cookies:** a visitor id stored in a cookie may need consent under EU rules. Prefer the shop's existing session id, and let the store decide whether it falls under its consent banner.

## Reliability

- [ ] Backups: daily `pg_dump` of the service database to private storage (not the public repo). Test a restore once.
- [ ] Load test before the pilot with the store's catalog size (`scripts/loadtest.py`, budget from the store's traffic). Measured so far: research API p50 22 ms / p95 28 ms at 1 user; production replay p95 89 to 100 ms ([ci.md](../worklog/ci.md), SERVICE.md on PR #12).
- [ ] Model and library versions: pickled bundles are tied to the library versions that trained them. Pin versions in the Docker image, and retrain after upgrading LightGBM or scikit-learn.
- [ ] Runbook `docs/RUNBOOK.md`: what to do when the API is down, the model is bad (roll back with `POST /v1/models/{v}/activate`), a key leaks (rotate), or a store asks for deletion.

## Files involved

| File | Role |
| --- | --- |
| `src/margingraph/service/app.py`, `settings.py`, `db.py`, `metrics.py` (PR #12) | Auth, limits, logging, metrics |
| `src/margingraph/models.py` | Dense matrices to make sparse |
| `src/margingraph/connectors/schema.py` | Where a PII-column check would go |
| `.github/workflows/ci.yml` | Add `pip-audit` |
| `docs/launch/privacy-and-data.md` | Promises the service must keep |
| New: `SECURITY.md`, `docs/RUNBOOK.md`, `docs/compliance/` | |

## Prompt for a future Claude session

```text
Phase 5 of docs/industry-plan (05-production-hardening.md). PR #12 is merged.
Please implement, as separate small PRs against main, each with tests: (1) DELETE /v1/customers/{id}
and an admin store-deletion command, matching docs/launch/privacy-and-data.md; (2) hashing of
customer_id and session_id with a per-store salt; (3) a log-retention step in the nightly batch job;
(4) a pip-audit CI job; (5) a connector warning that drops email/phone-like columns.
Keep everything free and runnable on an 8 GB laptop. Tick the boxes in the phase file.
```

For large catalogs:

```text
Phase 5, "Large catalogs": replace the dense item-item matrices in src/margingraph/models.py with
sparse top-k neighbour lists behind a config option (dense stays the default). Measure on UCI:
Hit@10 and NDCG@10 with their CIs, bundle size, peak RAM and latency, dense vs top-k for
k in 50, 200. Report only measured numbers and write docs/worklog/sparse-models.md.
```
