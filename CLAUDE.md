# CLAUDE.md — ShippingRateCalculator (Claude Code Extension)
# This file extends AGENTS.md with Claude Code-specific context.
# READ AGENTS.md FIRST — all architecture, rules, and project identity live there.

---

## Claude Code Notes

- **Rate data is in Excel**: use `openpyxl` or `pandas` to read `price shared.xlsx` — already in requirements.txt
- **Pincode lookup**: `pincodes.csv` is large — use pandas for fast lookup, not line-by-line iteration
- **Carrier formulas**: each carrier has a different weight-slab formula. Read the existing function before changing any formula.
- **Mangum wraps Flask**: `module.exports = handler` equivalent is `handler = Mangum(app)` in Python

## Useful Claude Code Commands for This Project

```bash
# Test locally
catalyst serve

# Check carrier rate structure
python3 -c "import pandas; df = pandas.read_excel('price shared.xlsx', sheet_name=None); print(df.keys())"

# Count pincodes
wc -l pincodes.csv
```

## What to Read Before Touching Code

1. `AGENTS.md` — project context, carrier rules, critical files
2. `PROJECT_IDENTITY.md` — locked identity
3. `functions/shipping-calc-new/index.py` — main Flask function
4. `price shared.xlsx` — rate source of truth
5. `pincodes.csv` — serviceability database
