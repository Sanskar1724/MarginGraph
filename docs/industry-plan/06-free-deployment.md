# Phase 6: deploy on free tiers

**Goal:** a public, always-reachable demo and landing page, and a production API, database, nightly training and dashboard that a pilot store can use, all at zero cost.

**Free tiers change.** The limits below are what the earlier work threads recorded on 2026-10-26 (sources given). Check each provider's pricing page before relying on them.

**Done when:**

- [ ] Demo (HF Space) and landing page (GitHub Pages) are live. *(Phase 0)*
- [ ] Production API is reachable over HTTPS with `/ready` returning 200.
- [ ] Database is hosted Postgres, with a tested backup.
- [ ] The nightly job trains every store and the API picks up the new model.
- [ ] Merchant dashboard is reachable with a token.
- [ ] Monitoring and an uptime check are on (Phase 5).
- [ ] `docs/DEPLOYMENT.md` records what runs where, with the URLs (no secrets).

## The free stack

| Piece | Choice | Recorded limits | Source |
| --- | --- | --- | --- |
| Demo | Hugging Face Space, Gradio, CPU basic | 2 vCPU, 16 GB RAM; sleeps after 48 h idle | `space/DEPLOY.md`, demo worklog |
| Landing page | GitHub Pages via `.github/workflows/pages.yml` | free for public repos | launch worklog |
| Production API | **Option A:** Hugging Face Space with the Docker SDK | 16 GB RAM; disk is not persistent | SERVICE.md (PR #12) |
| | **Option B:** Render free web service | 512 MB RAM: enough to serve one small store, not to train | SERVICE.md (PR #12) |
| Database | Neon or Supabase Postgres | `DATABASE_URL=postgresql+psycopg://...?sslmode=require` | SERVICE.md (PR #12) |
| Cache (only with 2+ API copies) | Upstash Redis | `REDIS_URL=rediss://...` | SERVICE.md (PR #12) |
| Nightly training | GitHub Actions cron, or Kaggle, or your laptop's cron | UCI-size training: 73 to 84 s, 1.65 GB peak RAM | SERVICE.md (PR #12) |
| Model storage | Private Hugging Face model repo | | this plan |
| Monitoring | Grafana Cloud free + an uptime checker | | Phase 5 |
| CI | GitHub Actions | already running | ci worklog |

Recommended start: **HF Space (Docker) for the API + Neon Postgres + a GitHub Actions nightly job that uploads model bundles to a private HF model repo.** One API copy needs no Redis.

## The one missing piece: getting models to a host without a disk

Free hosts lose their disk on restart, and the nightly job may run somewhere else. The service reads bundles from `MARGINGRAPH_ARTIFACTS`. So:

- [ ] Add a small step to the batch job: after the quality gate passes, upload `artifacts/<store>/<version>/bundle.pkl` to a **private** HF model repo (`huggingface_hub.upload_file`, token from secrets).
- [ ] Add a start-up step to the API: download the active version for each store from that repo into `MARGINGRAPH_ARTIFACTS` before preloading. The model registry (which version is active) lives in Postgres, so it survives restarts.
- [ ] Test: restart the Space; `/ready` lists the models; a recommendation is served by the model, not the fallback.

This is new code (not in PR #12). Keep it behind environment variables (`MARGINGRAPH_HF_REPO`, `HF_TOKEN`) so local runs are unchanged.

## Steps

### 1. Database (Neon example)

- [ ] Create a free Neon project; pick an EU region for EU/UK stores.
- [ ] Copy the connection string; change the scheme to `postgresql+psycopg://` and keep `?sslmode=require`.
- [ ] Initialize from your laptop (the URL only lives in `.env`):
  ```bash
  set -a; source .env; set +a
  margingraph init-db
  ```

### 2. API on a Hugging Face Space (Docker)

- [ ] New Space → SDK **Docker** → Blank → CPU basic → visibility **Private** while testing.
- [ ] Push the repo (or a copy with only what the image needs) to the Space; the root `Dockerfile` from PR #12 runs the production API and reads `PORT`. HF Spaces expects port 7860 by default: set `PORT=7860` or `app_port` in the Space README's settings block.
- [ ] Space → Settings → **Secrets**: `MARGINGRAPH_ENV=production`, `MARGINGRAPH_ADMIN_KEY`, `DATABASE_URL`, `MARGINGRAPH_CORS_ORIGINS`, and later `HF_TOKEN`, `MARGINGRAPH_HF_REPO`.
- [ ] Check:
  ```bash
  curl https://<user>-<space>.hf.space/health
  curl https://<user>-<space>.hf.space/ready
  ```
- [ ] Create a store and load a catalog from your laptop (Phase 3 commands, with `MG` set to the Space URL).

### 3. Nightly training (GitHub Actions)

- [ ] Add `.github/workflows/nightly.yml`: on `schedule` (cron `0 3 * * *`) and `workflow_dispatch`; install the package; run `margingraph batch` with `DATABASE_URL` and `HF_TOKEN` from repository secrets; upload bundles (step above).
- [ ] Repository → Settings → Secrets and variables → Actions: add `DATABASE_URL`, `HF_TOKEN`.
- [ ] Never print the database URL in logs; never upload store data as a workflow artifact on a public repo (workflow artifacts on public repos can be downloaded by anyone).
- [ ] Note: scheduled workflows on public repos are disabled after 60 days without repository activity; a commit re-enables them.

### 4. Dashboard

- [ ] Run it as a second Space (Docker) or on the same host, with `MARGINGRAPH_DASHBOARD_TOKEN` set. Point the API at it with `MARGINGRAPH_DASHBOARD_URL` (PR #12 reads settings from it), and the dashboard at the service's `dashboard_events` view.

### 5. Write it down

- [ ] `docs/DEPLOYMENT.md`: a table of what runs where, URLs, which secrets exist (names only), how to redeploy, how to roll back a model, and the free-tier limits as checked on the date you set it up.

## When free is no longer enough

Move one piece at a time, only when a paying store needs it: first the API host (no sleeping, more RAM), then the database (backups, size). Student offers (GitHub Student Developer Pack and cloud student credits) can cover a few months; check what is offered when you apply.

## Files involved

| File | Role |
| --- | --- |
| `Dockerfile`, `docker-compose*.yml`, `.env.example` (PR #12) | Image and local stacks |
| `src/margingraph/service/train.py`, `cli.py` (PR #12) | Batch job; where the upload step goes |
| `.github/workflows/` | New `nightly.yml` |
| `space/` | Gradio demo |
| New: `docs/DEPLOYMENT.md` | |

## Prompt for a future Claude session

```text
Phase 6 of docs/industry-plan (06-free-deployment.md). PR #12 is merged. Please (1) add optional
upload of active model bundles to a private Hugging Face model repo after the batch job's quality
gate, and download at API start-up, both off unless MARGINGRAPH_HF_REPO and HF_TOKEN are set, with
tests that mock huggingface_hub; (2) add .github/workflows/nightly.yml that runs margingraph batch
with DATABASE_URL and HF_TOKEN from secrets and never uploads data as an artifact; (3) write
docs/DEPLOYMENT.md as a fill-in template. I will create the Neon database and the Space myself:
give me the click-by-click steps for those at the end. One PR against main.
```
