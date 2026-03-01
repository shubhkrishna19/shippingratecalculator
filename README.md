# Shipping Rate Calculator - Zoho Catalyst Deployment

A serverless API for calculating shipping rates from multiple carriers (Affinity, Bluedart, Delhivery) deployed on Zoho Catalyst.

## Prerequisites

### 1. Install Zoho Catalyst CLI

```bash
# Using npm (recommended)
npm install -g catalyst-cli

# Verify installation
catalyst --version
```

### 2. Authenticate with Zoho Catalyst

```bash
catalyst auth:login
```

Follow the prompts to authenticate with your Zoho account.

### 3. Configure Python Environment

Ensure you have Python 3.10 or higher installed:

```bash
python --version
```

## Project Structure

```
ShippingRateCalculator/
├── main.py                 # FastAPI application entry point
├── rate_calculator.py      # Shipping rate calculation logic
├── pincodes.csv            # Pincode zone mapping database
├── catalyst.json           # Zoho Catalyst configuration
└── README.md               # This file
```

## Deployment

### Step 1: Initialize Catalyst Project (if not already initialized)

```bash
cd ShippingRateCalculator
catalyst init
```

Select "Serverless Function" as the project type and choose Python 3.10+ as the runtime.

### Step 2: Deploy the Function

```bash
catalyst deploy
```

This will deploy the shipping rate calculator function to Zoho Catalyst. The CLI will show the deployed function URL upon successful deployment.

### Step 3: Note the API Endpoint

After deployment, you will receive an endpoint URL in the format:

```
https://<project-id>.catalystserverless.com/shipping-rate-calculator
```

## How to Call the API

### Endpoint

```
POST /shipping-rate-calculator/calculate
```

### Request Body

```json
{
  "weight": 5.0,
  "pincode": 500001
}
```

- `weight` (required): Weight in kilograms (must be greater than 0)
- `pincode` (required): Delivery pincode (6 digits, 100000-999999)

### Example Request

```bash
curl -X POST https://<project-id>.catalystserverless.com/shipping-rate-calculator/calculate \
  -H "Content-Type: application/json" \
  -d '{"weight": 5.0, "pincode": 500001}'
```

### Example Response

```json
{
  "success": true,
  "inputs": {
    "weight_kg": 5.0,
    "pincode": 500001
  },
  "zone_lookups": {
    "delhivery_zone": "B",
    "bluedart_zone": "South",
    "affinity_zone": "South 1",
    "state_code": "TS"
  },
  "carrier_prices": {
    "Affinity": 450.0,
    "Bluedart": 350.0,
    "D(1 Kg)": 108.0,
    "D(10 kg)": 120.0,
    "D(20 kg)": 230.0
  },
  "best_carrier": "D(1 Kg)",
  "best_price": 108.0,
  "pincode_info": {
    "city": "Hyderabad",
    "express_tat": 2.0,
    "surface_tat": 5.0
  }
}
```

### Additional Endpoints

- **Health Check**: `GET /shipping-rate-calculator/health`
- **Root**: `GET /shipping-rate-calculator/`

```bash
# Health check
curl https://<project-id>.catalystserverless.com/shipping-rate-calculator/health
```

## How to Update Pincodes

The `pincodes.csv` file contains the pincode zone mappings used by the rate calculator. To update it:

### Step 1: Edit the CSV File

Open `pincodes.csv` in a spreadsheet editor or text editor. The file has the following columns:

| Column | Description |
|--------|-------------|
| Pincode | 6-digit pincode |
| City | City name |
| State Code | State abbreviation (e.g., TS, DL) |
| Express TAT | Express delivery turnaround time (days) |
| Surface TAT | Surface delivery turnaround time (days) |
| Zone | Delhivery zone (A-F) |
| BD-Zone | Bluedart zone |
| BD-State Code | Bluedart state code |

### Step 2: Redeploy

After updating the CSV file, redeploy the function:

```bash
catalyst deploy
```

### Important Notes

- Ensure the CSV file is properly formatted with no extra columns
- Pincode values must be 6 digits
- Delhivery zones should be A-F
- Bluedart zones should be: East, North, South, West, North East &JK

## Supported Carriers

The calculator computes rates for:

- **Affinity** (8 zones: North 1, North 2, West, South 1, South 2, East, NE1, NE2)
- **Bluedart** (5 zones: East, North, South, West, North East &JK)
- **Delhivery 1KG** (8 zones: A-F + C2, D2)
- **Delhivery 10KG** (8 zones: A-F + C2, D2)
- **Delhivery 20KG** (8 zones: A-F + C2, D2)

All prices returned are GST exclusive.

## Troubleshooting

### Function not responding

- Check the function logs in Catalyst console
- Verify the function timeout settings (default: 30 seconds)
- Ensure pincodes.csv is included in the deployment package

### Pincode not found

- Verify the pincode exists in pincodes.csv
- Check pincode format (should be 6 digits)

### Rate calculation errors

- Ensure the pincode has valid zone mappings in pincodes.csv
- Check that all required columns are present in the CSV
