# AGENTS.md — ShippingRateCalculator
# Universal AI context file. Read this first, regardless of which AI tool you are.
# Works with: Claude Code, MiniMax, Antigravity, OpenClaw, Codex, Cursor, Copilot

---

## Project Identity

- **Name:** ShippingRateCalculator
- **Owner:** Shubh (Bluewud)
- **Platform:** Zoho Catalyst (Advanced I/O — Python Flask)
- **Status:** Live / Production
- **Purpose:** Calculates shipping rates for 5 carriers (Delhivery, Ecom Express, Xpressbees, Shadowfax, Bluedart) based on weight, pincode, and product type. Powers the Bluewud Shopify store's shipping widget.

---

## Tech Stack

| Layer       | Tech                                       |
|-------------|--------------------------------------------|
| Backend     | Python Flask + Mangum (ASGI adapter)       |
| Hosting     | Zoho Catalyst Advanced I/O function        |
| Rate data   | `pincodes.csv` (serviceability) + `price shared.xlsx` (rate tables) |
| Carriers    | 5 Indian logistics carriers                |
| Frontend    | `index.html` (standalone calculator tool)  |

---

## Critical Rules — Any AI Must Follow

1. **Rate table source is `price shared.xlsx`** — do not hardcode rates in Python. Always read from the file.
2. **`pincodes.csv`** — do not delete or rename. It's the serviceability database.
3. **Carrier formula rules are per-carrier** — each carrier has a different weight-slab formula. Read existing code before changing any formula.
4. **No credentials in this project** — Shopify CLI handles auth externally.
5. **Mangum adapter wraps Flask** — do not remove it.
6. **Never call `catalyst deploy`** — Shubh deploys.

---

## File Structure (important files)

```
functions/
  shipping-calc-new/
    index.py          ← Flask app, Mangum-wrapped
    requirements.txt  ← mangum, flask, openpyxl, pandas
pincodes.csv          ← pincode serviceability DB (do not delete)
price shared.xlsx     ← carrier rate tables (source of truth)
index.html            ← standalone HTML calculator (for offline use / reference)
deluge-shipping-calculator.txt  ← Zoho Creator Deluge script (reference)
catalyst.json         ← function config
.env.example          ← no secrets needed (documents this explicitly)
PROJECT_IDENTITY.md   ← locked identity
```

---

## How Rates Are Calculated

1. Lookup pincode in `pincodes.csv` → determines zone (A, B, C, D, E) per carrier
2. Look up zone + weight slab in `price shared.xlsx` → get base rate
3. Apply carrier-specific formula (forward/reverse, COD surcharge, fuel surcharge)
4. Return structured JSON with all carrier options

---

## When Working on This Project

- Update `price shared.xlsx` when carrier rates change (do not rewrite formulas)
- Replace `pincodes.csv` when carrier serviceability changes (full file replacement)
- Test with known pincodes: 110001 (Delhi), 400001 (Mumbai), 560001 (Bangalore)
- Keep response time under 500ms — it's called on Shopify product pages

---

## Handoff Protocol

When done: summarize changes, list modified files, flag TODOs. Do not deploy.


## Session Start Checklist

Every session, before writing any code:
1. Read this AGENTS.md fully
2. Read TASKS.md — check what's IN PROGRESS (don't duplicate work)
3. Claim your task in TASKS.md before starting
4. Work on a branch: feat/[agent-tag]-T[id]-[slug]
5. Full protocol: BluewudOrchestrator/COORDINATION.md
