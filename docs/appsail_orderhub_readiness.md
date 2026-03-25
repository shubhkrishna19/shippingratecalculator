# AppSail OrderHub Readiness

This note is the deploy-readiness checklist for running `ShippingRateCalculator` on Zoho Catalyst AppSail with live OrderHub SSOT integration.

## Required Runtime Env Vars

Manual env vars:

- `ORDER_HUB_BASE_URL`
  - Dev example: `https://orderhub.development.catalystappsail.com`
  - Prod example: `https://orderhub.catalystappsail.com`
  - Purpose: enables `Load from Zoho SSOT` and `Write Back to SSOT`

Platform-managed env vars:

- `X_ZOHO_CATALYST_LISTEN_PORT`
  - Set by AppSail at runtime
  - Do not hardcode or set manually

## AppSail Packaging Requirement

The AppSail bundle must include `order_hub_client.py` because `main.py` imports it for SSOT read/writeback routes.

Validated package source:

- `scripts/package_appsail.py`

## Post-Deploy Smoke Test

Use the deployed AppSail base URL below as `<APP_URL>`.

1. Health

```bash
curl "<APP_URL>/api/health"
```

Expected:

- HTTP `200`
- `"status": "healthy"`
- `"order_hub_configured": true`

2. Runtime settings

```bash
curl "<APP_URL>/api/settings"
```

Expected:

- HTTP `200`
- `settings.order_hub_base_url` resolves to the AppSail `ORDER_HUB_BASE_URL` unless an explicit UI override was saved

3. Live SSOT read

```bash
curl -X POST "<APP_URL>/api/jobs/ssot" ^
  -H "Content-Type: application/json" ^
  -d "{\"limit\":1}"
```

Expected:

- HTTP `200`
- response includes `job_id`
- `status` is `queued`, `processing`, or `completed`

4. Read back the first processed row

```bash
curl "<APP_URL>/api/jobs/<JOB_ID>/rows?page=1&page_size=1"
```

Expected:

- HTTP `200`
- at least one row returned
- returned row contains `canonical_line_id`
- returned row has either:
  - a resolved allocation (`best_carrier`, `best_rate`, `zone`)
  - or a non-empty `exception_reason`

5. Live SSOT writeback

Use one reviewed row from step 4.

```bash
curl -X POST "<APP_URL>/api/writeback" ^
  -H "Content-Type: application/json" ^
  -d "{\"rows\":[<ROW_JSON>],\"export_format\":\"csv\"}"
```

Expected:

- HTTP `200`
- `updated_rows` >= `1`
- `orders_touched` >= `1`
- `export_batch.batch_id` present
- `download_url` present

## Known Good Local Verification

Validated locally with:

- `C:\Users\shubh\Downloads\ShippingRateCalculator\.venv\Scripts\python.exe -m pytest tests\test_calculator.py tests\test_ssot_api.py -q` -> `9 passed`
- `C:\Users\shubh\Downloads\ShippingRateCalculator\.venv\Scripts\python.exe scripts\package_appsail.py` -> AppSail bundle built successfully
- `ORDER_HUB_BASE_URL=https://orderhub.development.catalystappsail.com` for the SSOT integration checks
- `/api/jobs/ssot` returning one live row
- `/api/writeback` succeeding with:
  - `updated_rows = 1`
  - `orders_touched = 1`

## Notes

- If `ORDER_HUB_BASE_URL` is set and `app_settings.json` has a blank `order_hub_base_url`, the runtime now correctly falls back to the env var.
- Use OrderHub dev for the first smoke test before pointing AppSail shipping to production.
