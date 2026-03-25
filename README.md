# Shipping Rate Calculator

Internal Bluewud tool for:

- manual `weight + pincode` carrier calculation
- async batch upload of raw marketplace order files
- SKU to dead-weight resolution from the dimensions master
- merged review/export with `best_carrier`, `best_rate`, and `zone`

## Runtime

- Local dev: FastAPI
- Preview deploy: Vercel Python function
- Production deploy: Zoho Catalyst AppSail

## Current Assets

- `price shared.xlsx`: source of truth for carrier logic
- `Dimensions Master.xlsx`: dead-weight source from `Billing Dimensions`
- `SKU Aliases, Parent & Child Master Data (1).xlsx`: fallback alias resolver
- `pincodes.csv`: generated from the calculator workbook

## Local Run

```bash
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Verified Sample Run

The current Aug-25 sample pack processes successfully:

- files: 9
- rows: 1732
- successful rows: 1708
- exception rows: 24

## Vercel

Vercel config is included through `vercel.json` and `app.py`.

Important:

- Vercel is suitable for preview and lighter operational runs.
- Vercel functions currently have a hard request body limit of `4.5 MB`, so very large multi-file batches are not a safe production assumption there.
- The current sample upload pack is about `0.86 MB`, so it fits comfortably.
- Vercel uses a stateless batch mode: the processed review rows stay in the browser session and export is posted back statelessly.

## Zoho Catalyst

This repo is now prepared for AppSail deployment instead of the old function-only layout.

Current confirmed Catalyst project:

- project name: `salestrends`
- org: `BluewudCoreDev`
- existing URL shared by you is the legacy serverless implementation, not the new AppSail target

Files used for Catalyst deployment:

- `catalyst.json`
- `app-config.json`
- `appsail_main.py`
- `scripts/package_appsail.py`

Packaging behavior:

- bundles only the runtime files into `dist/appsail`
- excludes sample order templates, tests, and local runtime cache
- keeps the workbook assets inside the AppSail build
- uses background batch processing on Zoho AppSail and server-side job storage on local development

Deploy flow:

```bash
python scripts/package_appsail.py
catalyst deploy
```

Catalyst notes:

- AppSail managed Python runtime is `python_3_9`
- the app code has been adjusted to stay compatible with that runtime
- `appsail_main.py` respects `X_ZOHO_CATALYST_LISTEN_PORT`

## OrderHub integration

The app can now pull live order lines from OrderHub and write reviewed shipping allocations back to the shared SSOT.

Runtime config options:

- UI/settings file: order_hub_base_url
- Environment fallback: ORDER_HUB_BASE_URL

Recommended deploy setup:

- set ORDER_HUB_BASE_URL in AppSail
- keep the UI field available for internal override if needed
- use Load from Zoho SSOT for review batches
- use Write Back to SSOT after review to persist carrier/rate decisions centrally
- deploy checklist and smoke test: `docs/appsail_orderhub_readiness.md`

Verification:

- `tests\\test_calculator.py`
- `tests\\test_ssot_api.py`

Current local verification result: 9 passed
## OrderHub Deploy Readiness

Required runtime env var for AppSail:

- `ORDER_HUB_BASE_URL` = base URL of the target OrderHub environment, with no trailing slash
- current development value used for verification: `https://orderhub.development.catalystappsail.com`

No additional auth env vars are required in this app today because OrderHub shipping endpoints are reached directly by base URL.

Recommended post-deploy smoke test sequence:

1. Open `GET /api/health` on the deployed AppSail URL and confirm `order_hub_configured=true`.
2. Call `POST /api/jobs/ssot` with `{ "limit": 1, "statuses": ["Pending"] }` and confirm `200`, `job_mode`, and `summary.total_rows >= 1`.
3. In the UI, use `Load from Zoho SSOT` and confirm at least one row resolves to a `resolved_mtp_sku` and a `best_carrier`.
4. Use `POST /api/writeback` only with a single known-safe dev row, then confirm `200`, `updated_rows >= 1`, and that OrderHub returns an `export_batch.batch_id`.
5. Re-open the same item in OrderHub and confirm the reviewed carrier/rate fields landed as expected.

Deploy-ready checklist:

- AppSail env var `ORDER_HUB_BASE_URL` set to the intended OrderHub environment
- `app_settings.json` does not contain a conflicting non-empty `order_hub_base_url` override
- `python scripts/package_appsail.py` completes successfully before deploy
- `tests/test_calculator.py` and `tests/test_ssot_api.py` pass in the project `.venv`
- Smoke-test steps above are run immediately after deploy

## Operational Caveat

Row review data and editable settings are currently stored in local files:

- `.runtime/jobs/*.json`
- `app_settings.json`

That works locally and is acceptable for development. It is not the final durable production persistence layer for a scaled multi-instance deployment.

For hardened Zoho production, the next step is moving:

- job state to Catalyst Data Store or Stratus
- settings persistence to Catalyst Data Store

## Main Endpoints

- `GET /`
- `GET /api/health`
- `POST /api/calculate`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/settings/assets`
- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/rows`
- `PATCH /api/jobs/{job_id}/rows/{row_id}`
- `POST /api/jobs/{job_id}/bulk-carrier`
- `GET /api/jobs/{job_id}/export`

