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
