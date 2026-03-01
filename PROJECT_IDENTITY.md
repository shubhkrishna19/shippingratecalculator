# PROJECT IDENTITY — ShippingRateCalculator
> ⚠️ THIS FILE IS LOCKED. No AI agent may modify it without explicit approval from Shubh Krishna.

## What This Project Is
A serverless API that calculates shipping rates across 5 carrier options (Affinity, Bluedart, Delhivery 1KG / 10KG / 20KG) for any Indian pincode. Used internally by Bluewud Industries for logistics cost comparison. Includes an embedded web UI for manual lookups and a JSON API for programmatic use.

## Deployment Target
**Zoho Catalyst** — Advanced I/O Serverless Function (Python 3.9)
- Catalyst Project: `CoreDev` (ID: 43182000000012177)
- Function name: `shipping-calc-new`
- Live URL pattern: `https://<project-id>.catalystserverless.com/server/shipping-calc-new/`

## Approved Tech Stack
| Layer | Technology | Notes |
|-------|-----------|-------|
| Runtime | Python 3.9 | Catalyst Advanced I/O |
| Handler | Flask (Request/Response only) | NOT a full Flask server — only used for Catalyst's request objects |
| Data | CSV (pincodes.csv) | 21,519 Indian pincodes with zone data |
| Rate logic | Pure Python | No ORM, no DB, no external API calls |
| Frontend | Vanilla HTML/CSS/JS | Embedded in main.py as `UI_HTML` string |

**NOT ALLOWED:** FastAPI, Mangum, SQLAlchemy, pandas, external API calls for rate lookup, replacing pincodes.csv with a database without Shubh's approval.

## Folder Structure (DO NOT CHANGE)
```
ShippingRateCalculator/
├── .gitignore              ← LOCKED - security critical
├── .env.example            ← credential template
├── catalyst.json           ← LOCKED - Catalyst project config
├── catalyst-user-rules.json← LOCKED - API gateway routing rules
├── PROJECT_IDENTITY.md     ← LOCKED - this file
├── CLAUDE.md               ← AI agent instructions
├── README.md               ← deployment guide
├── tests/
│   └── test_calculator.py  ← unit tests — keep passing
└── functions/
    └── shipping-calc-new/
        ├── main.py         ← Catalyst handler (can be carefully modified)
        ├── rate_calculator.py ← core rate logic (can be modified for rate updates)
        ├── pincodes.csv    ← pincode database (update when carriers update zones)
        ├── catalyst-config.json ← LOCKED
        └── requirements.txt   ← LOCKED unless adding approved package
```

## Business Logic Rules
- **Carrier rates are in the rate tables inside rate_calculator.py** — update these when carriers send new rate cards
- **pincodes.csv is the zone database** — replace the whole file when updating, do NOT edit individual rows manually
- **Minimum weights:** Affinity = 20kg, Bluedart = 10kg, Delhivery = 1kg
- **Formula components:** freight + fuel surcharge + FOV/ROV charges — do not simplify or remove any component

## Files That Are UNTOUCHABLE
- `catalyst-config.json` inside the function — runtime config, breaking it breaks the deployment
- `catalyst.json` at root — project config
- `catalyst-user-rules.json` — API gateway routing

## No Environment Variables Required
This project has no secrets. The pincode database is a CSV file bundled with the function. No external API calls are made. If you think you need to add a secret, STOP and ask Shubh first.

## Owner
Shubh Krishna — shubhkrishna.19@gmail.com
