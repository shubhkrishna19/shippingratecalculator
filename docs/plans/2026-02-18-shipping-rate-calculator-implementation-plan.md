# Shipping Rate Calculator - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Zoho Catalyst serverless function that calculates shipping rates from 5 carriers and returns the best option.

**Architecture:** FastAPI-based Python function that loads pincode DB at startup, calculates rates for all carriers, and returns comparison with best carrier highlighted.

**Tech Stack:** Python, FastAPI, Zoho Catalyst Serverless Functions

---

## Task 1: Export Pincode Database from Excel

**Files:**
- Create: `pincodes.csv`
- Source: Excel file "price shared.xlsx" sheet "M"

**Step 1: Export M sheet to CSV**

Run: `python -c "import pandas as pd; df = pd.read_excel('price shared.xlsx', sheet_name='M'); df.to_csv('pincodes.csv', index=False); print(f'Exported {len(df)} rows')"`

Expected: CSV file with 21,519 pincodes

**Step 2: Verify CSV columns**

Run: `python -c "import pandas as pd; df = pd.read_csv('pincodes.csv'); print(df.columns.tolist())"`

Expected columns: Pincode, Prepaid, Reverse Pickup, COD, City, State, Code, Express TAT, Surface TAT, Zone, BD-Zone, BD-State Code, BD-serviceable status

**Step 3: Commit**

```bash
git add pincodes.csv
git commit -m "feat: add pincode database CSV"
```

---

## Task 2: Create Rate Calculator Core Logic

**Files:**
- Create: `rate_calculator.py`
- Test: `tests/test_calculator.py`

**Step 1: Write the failing test**

```python
# tests/test_calculator.py
import pytest
import sys
sys.path.insert(0, '..')
from rate_calculator import calculate_best_rate

def test_calculate_85kg_500001():
    """Test case from Excel: Weight=85, Pincode=500001"""
    # Create test pincode DB
    test_db = {
        500001: {
            "delhivery_zone": "C2",
            "bluedart_zone": "SOUTH",
            "state_code": "TS",
            "city": "Hyderabad",
            "prepaid": "Y",
            "cod": "Y",
            "reverse_pickup": "Y",
            "express_tat": 3,
            "surface_tat": 4,
            "bd_serviceable": "Yes",
        }
    }

    result = calculate_best_rate(85, 500001, test_db)

    assert result["carrier_prices"]["Affinity"] == 1468.5
    assert result["carrier_prices"]["Bluedart"] == 1438.515
    assert result["carrier_prices"]["D(1 Kg)"] == 2502
    assert result["carrier_prices"]["D(10 kg)"] == 1665
    assert result["carrier_prices"]["D(20 kg)"] == 1300
    assert result["best_carrier"] == "D(20 kg)"
    assert result["best_price"] == 1300
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_calculator.py::test_calculate_85kg_500001 -v`

Expected: FAIL (module not found)

**Step 3: Write rate_calculator.py**

Create `rate_calculator.py` with:
- AFFINITY_RATES, BLUEDART_RATES, DELHIVERY_10KG, DELHIVERY_20KG, DELHIVERY_1KG dictionaries
- STATE_TO_AFFINITY_ZONE mapping
- calculate_affinity(), calculate_bluedart(), calculate_delhivery_10kg(), calculate_delhivery_20kg(), calculate_delhivery_1kg() functions
- calculate_best_rate() main function
- load_pincode_db_from_csv() function

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_calculator.py::test_calculate_85kg_500001 -v`

Expected: PASS

**Step 5: Commit**

```bash
git add rate_calculator.py tests/test_calculator.py
git commit -m "feat: add rate calculator core logic"
```

---

## Task 3: Create FastAPI App for Zoho Catalyst

**Files:**
- Create: `main.py` (Catalyst handler)
- Create: `requirements.txt`

**Step 1: Create requirements.txt**

```
fastapi>=0.100.0
uvicorn>=0.23.0
pandas>=2.0.0
python-multipart>=0.0.6
```

**Step 2: Create main.py**

Create FastAPI app with:
- `POST /calculate` endpoint
- Request model with weight, pincode
- Load pincode DB on startup
- Call calculate_best_rate() and return JSON

**Step 3: Test the API locally**

Run: `uvicorn main:app --reload`

In another terminal:
```bash
curl -X POST http://localhost:8000/calculate -H "Content-Type: application/json" -d '{"weight": 85, "pincode": 500001}'
```

Expected: JSON response with all carrier prices

**Step 4: Commit**

```bash
git add main.py requirements.txt
git commit -m "feat: add FastAPI app for Zoho Catalyst"
```

---

## Task 4: Create Zoho Catalyst Configuration

**Files:**
- Create: `catalyst.json` (Catalyst project config)
- Create: `README.md` (deployment instructions)

**Step 1: Create catalyst.json**

```json
{
  "project": {
    "project_name": "shipping-rate-calculator"
  },
  "functions": {
    "shipping-calculator": {
      "runtime": "python3.10",
      "handler": "main.app"
    }
  }
}
```

**Step 2: Create README.md with deployment steps**

Include:
- Prerequisites (Catalyst CLI installed)
- Deploy command
- API endpoint usage
- How to update pincodes.csv

**Step 3: Commit**

```bash
git add catalyst.json README.md
git commit -m "docs: add Zoho Catalyst configuration"
```

---

## Task 5: Final Verification

**Step 1: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests PASS

**Step 2: Test with multiple pincodes**

Run API and test:
- 110001 (Delhi) - North zone
- 400001 (Mumbai) - West zone
- 600001 (Chennai) - South zone

Verify zones and prices are correct for each.

**Step 3: Final commit**

```bash
git add .
git commit -m "feat: complete shipping rate calculator"
```

---

## Plan complete and saved to `docs/plans/2026-02-18-shipping-rate-calculator-design.md`

**Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
