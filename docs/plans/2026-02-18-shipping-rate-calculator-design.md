# Shipping Rate Calculator API - Design

## Overview
A serverless REST API that replicates the Bluewud shipping rate calculator from the Excel workbook, returning all 5 carrier rates with the best option for Zoho integration.

## Technical Stack
- **Framework:** FastAPI (Python)
- **Hosting:** Zoho Catalyst Serverless Functions
- **Data:** Pincode DB (CSV) loaded at runtime

## API Specification

### Endpoint
`POST /api/calculate`

### Request
```json
{
  "weight": 85,
  "pincode": 500001
}
```

### Response
```json
{
  "success": true,
  "inputs": {
    "weight_kg": 85,
    "pincode": 500001
  },
  "zone_lookups": {
    "delhivery_zone": "C2",
    "bluedart_zone": "SOUTH",
    "affinity_zone": "South 1",
    "state_code": "TS"
  },
  "carrier_prices": {
    "Affinity": 1468.5,
    "Bluedart": 1438.515,
    "D(1 Kg)": 2502,
    "D(10 kg)": 1665,
    "D(20 kg)": 1300
  },
  "best_carrier": "D(20 kg)",
  "best_price": 1300,
  "pincode_info": {
    "city": "Hyderabad",
    "express_tat": 3,
    "surface_tat": 4
  }
}
```

## Carriers & Rate Logic

### 1. Affinity (8 zones)
- Zones: North 1, North 2, West, South 1, South 2, East, NE1, NE2
- Rate: Per kg rate × max(weight, 20kg) + FOV/ROV (100) + Fuel (15%)
- Min freight: 300 INR
- Min weight: 20kg

### 2. Bluedart (5 zones)
- Zones: East, North, North East &JK, South, West
- Rate: Per kg rate × max(weight, 10kg) + FOV (75) + ROV (75) + Fuel (17%)
- Min weight: 10kg

### 3. Delhivery 1KG (8 zones)
- Zones: A, B, C1, C2, D1, D2, E, F
- Formula: base_first_kg + (weight - 1) × additional_per_kg

### 4. Delhivery 10KG (8 zones)
- Zones: A, B, C1, C2, D1, D2, E, F
- Formula: flat_10kg + (weight - 10) × additional_per_kg (if weight > 10)

### 5. Delhivery 20KG (8 zones)
- Zones: A, B, C1, C2, D1, D2, E, F
- Slab-based pricing: 0-20kg, 20-50kg, 50-100kg, 100kg+

## Zone Mapping
- Delhivery zones: From M sheet (Column I)
- Bluedart zones: From M sheet (Column J)
- Affinity zones: Derived from state code (M sheet Column F)

## Data Files
1. `rate_calculator.py` - Core calculation logic
2. `pincodes.csv` - Pincode database (21,519 records)
3. `main.py` - FastAPI app with Vercel adapter
4. `requirements.txt` - Python dependencies

## Deployment
- Platform: Zoho Catalyst
- Function: Catalyst Serverless Functions (Python)
- Integrated with Zoho ecosystem
- Easy to call from other Zoho apps

## Error Handling
- Invalid pincode: Returns error message
- Invalid weight: Returns error message
- Missing carrier service: Returns null for that carrier

## Notes
- All prices are GST EXCLUSIVE
- Pincode DB can be updated by replacing pincodes.csv
- Rate tables can be updated in rate_calculator.py
