"""
BLUEWUD SHIPPING RATE CALCULATOR - Complete Implementation
============================================================
Replicates the exact logic from: price shared.xlsx
Every formula, every rate, every surcharge - verified cell-by-cell.

IMPORTANT NOTES:
- All prices are GST EXCLUSIVE (confirmed by business)
- Affinity IS included in the MIN comparison (Excel updated per business request)
- Pincode lookup uses the M sheet data (21,519 pincodes)
"""

# ================================================================
# RATE TABLES (exact values from spreadsheet cells)
# ================================================================

# --- AFFINITY (Sheet: Affinity, Cells T7:T14 for rates, Y7:Y14 for min slabs) ---
# Surcharges: V7=100 (FOV+ROV), W formula=U*15% (fuel), X=SUM(U:W)
AFFINITY_RATES = {
    "North 1": 9,       # T7
    "North 2": 17,      # T8
    "West":    12,      # T9
    "South 1": 14,      # T10
    "South 2": 15.5,    # T11
    "East":    13,      # T12
    "NE1":     16,      # T13
    "NE2":     23,      # T14
}

AFFINITY_MIN_SLAB = {
    "North 1": 307, "North 2": 491, "West": 376, "South 1": 422,
    "South 2": 456.5, "East": 399, "NE1": 468, "NE2": 629,
}

AFFINITY_CFG = {
    "min_weight_kg": 20,    # V3: Minimum Chargeable weight = 20KG
    "min_freight": 300,     # A20: Minimum Docket Freight = Rs 300
    "fov_rov": 100,         # V7:V14 = 100 (combined FOV+ROV)
    "fuel_pct": 0.15,       # A17: Fuel Surcharge = 15%
    "docket_charge": 50,    # A18: NOT used in formula, label only
}

# --- BLUEDART SURFACE (Sheet: Bluedart, Cells F2:F6) ---
# Formula: F18 = (E18+$F$9+$F$10)+(17%*(E18+$F$9+$F$10))
BLUEDART_RATES = {
    "East":            12.7,   # F2
    "North":           9.85,   # F3
    "North East &JK": 22,      # F4
    "South":           12.7,   # F5
    "West":            12.7,   # F6
}

BLUEDART_CFG = {
    "min_weight_kg": 10,     # F1: Minimum Weight 10 Kg
    "fov": 75,               # F9
    "rov": 75,               # F10
    "fuel_pct": 0.17,        # F8
}

# --- DELHIVERY 10KG (Delhivery (All) rows 2-7) ---
# Formula D7: =IF($B$7<=10, D5, D5+($B$7-10)*D6)
# (flat_rate_10kg, additional_per_kg_above_10)
DELHIVERY_10KG = {
    "A": (120, 10), "B": (160, 14), "C1": (180, 15), "C2": (240, 19),
    "D1": (190, 16), "D2": (250, 20), "E": (310, 28), "F": (350, 30),
}

# --- DELHIVERY 20KG (Delhivery (All) rows 10-15) ---
# (flat_20kg, rate_20_50, rate_50_100, rate_100_plus)
DELHIVERY_20KG = {
    "A": (190, 9, 8, 6),   "B": (230, 11, 10, 8),
    "C1": (330, 16, 14, 12), "C2": (330, 16, 14, 12),
    "D1": (370, 18, 16, 14), "D2": (370, 18, 16, 14),
    "E": (490, 22, 21, 20), "F": (600, 26, 25, 24),
}

# --- DELHIVERY 1KG (Delhivery (All) rows 19-23) ---
# Formula D23: =D21+($B$23-1)*D22
# (base_first_kg, additional_per_kg)
DELHIVERY_1KG = {
    "A": (50, 20), "B": (58, 23), "C1": (63, 26), "C2": (66, 29),
    "D1": (67, 32), "D2": (70, 35), "E": (76, 38), "F": (90, 49),
}

# ================================================================
# AFFINITY ZONE MAPPING (Affinity sheet A7:B14)
# Maps state_code (M sheet Column F) -> Affinity zone
# ================================================================
STATE_TO_AFFINITY_ZONE = {
    # North 1: Delhi NCR, Haryana, HP, Rajasthan, Chandigarh, Punjab, UP, Uttarakhand
    "DL": "North 1", "HR": "North 1", "HP": "North 1", "RJ": "North 1",
    "CH": "North 1", "PB": "North 1", "UP": "North 1", "UK": "North 1",
    # North 2: Jammu & Kashmir, Ladakh
    "JK": "North 2", "LA": "North 2",
    # East: Bihar, Odisha, Jharkhand, West Bengal
    "BR": "East", "OR": "East", "JH": "East", "WB": "East",
    # NE2 (default for Assam, override NE1 for Guwahati pincodes)
    "AS": "NE2", "AR": "NE2", "MN": "NE2", "ML": "NE2",
    "MZ": "NE2", "NL": "NE2", "SK": "NE2", "TR": "NE2",
    # South 1: AP, Karnataka, Telangana, Tamil Nadu
    "AP": "South 1", "KA": "South 1", "TS": "South 1", "TN": "South 1",
    # South 2: Kerala
    "KL": "South 2",
    # West: Maharashtra, Gujarat, Goa, MP, Chhattisgarh
    "MH": "West", "GJ": "West", "GA": "West", "MP": "West", "CG": "West",
}


# ================================================================
# CALCULATION FUNCTIONS (exact replicas of Excel formulas)
# ================================================================

def calculate_affinity(weight_kg, zone):
    """
    Affinity sheet cells U7:X14
    U7 = MAX((MAX($V$4,$V$3)*T7), 300)  -> freight
    V7 = 100  -> fov/rov (hardcoded)
    W7 = U7*15%  -> fuel surcharge
    X7 = SUM(U7:W7)  -> final price
    """
    if zone not in AFFINITY_RATES:
        return None
    rate = AFFINITY_RATES[zone]
    chargeable = max(weight_kg, AFFINITY_CFG["min_weight_kg"])  # MAX($V$4,$V$3)
    freight = max(chargeable * rate, AFFINITY_CFG["min_freight"])  # MAX(..., 300)
    fuel = freight * AFFINITY_CFG["fuel_pct"]  # U7*15%
    return round(freight + AFFINITY_CFG["fov_rov"] + fuel, 4)  # SUM(U7:W7)


def calculate_bluedart(weight_kg, zone):
    """
    Bluedart sheet cells E18:F22
    E18 = F2 * MAX($B$17, 10)  -> freight
    F18 = (E18+$F$9+$F$10) + (17% * (E18+$F$9+$F$10))  -> final price
    """
    if zone == "No service" or zone is None:
        return None
    # Normalize zone case (M sheet has uppercase, rates have title case)
    zone_match = None
    for key in BLUEDART_RATES:
        if key.upper() == zone.upper():
            zone_match = key
            break
    if zone_match is None:
        return None
    rate = BLUEDART_RATES[zone_match]
    chargeable = max(weight_kg, BLUEDART_CFG["min_weight_kg"])  # MAX($B$17,10)
    freight = rate * chargeable  # E18 = F2 * MAX(...)
    subtotal = freight + BLUEDART_CFG["fov"] + BLUEDART_CFG["rov"]  # E18+F9+F10
    return round(subtotal * (1 + BLUEDART_CFG["fuel_pct"]), 4)  # +17%


def calculate_delhivery_10kg(weight_kg, zone):
    """
    Delhivery (All) D7: =IF($B$7<=10, D5, D5+($B$7-10)*D6)
    """
    if zone not in DELHIVERY_10KG:
        return None
    flat_10, additional = DELHIVERY_10KG[zone]
    if weight_kg <= 10:
        return round(flat_10, 4)
    return round(flat_10 + (weight_kg - 10) * additional, 4)


def calculate_delhivery_20kg(weight_kg, zone):
    """
    Delhivery (All) D15:
    =IF($B$15<20, D11,
       IF($B$15<50, D11+($B$15-20)*D12,
         IF($B$15<100, (D11+30*D12)+($B$15-50)*D13,
           (D11+30*D12+50*D13)+($B$15-100)*D14)))
    """
    if zone not in DELHIVERY_20KG:
        return None
    f20, r20_50, r50_100, r100p = DELHIVERY_20KG[zone]
    if weight_kg < 20:
        return round(f20, 4)
    elif weight_kg < 50:
        return round(f20 + (weight_kg - 20) * r20_50, 4)
    elif weight_kg < 100:
        return round((f20 + 30 * r20_50) + (weight_kg - 50) * r50_100, 4)
    else:
        return round((f20 + 30 * r20_50 + 50 * r50_100) + (weight_kg - 100) * r100p, 4)


def calculate_delhivery_1kg(weight_kg, zone):
    """
    Delhivery (All) D23: =D21+($B$23-1)*D22
    """
    if zone not in DELHIVERY_1KG:
        return None
    base, additional = DELHIVERY_1KG[zone]
    return round(base + (weight_kg - 1) * additional, 4)


# ================================================================
# MAIN CALCULATOR (replicates Master sheet comparison engine)
# ================================================================

def calculate_best_rate(weight_kg, pincode, pincode_db, include_affinity=True):
    """
    Replicates the Master sheet logic:
    1. D1 = weight (from X12)
    2. AB13 = XLOOKUP(pincode, M!A:A, M!J:J) -> Bluedart zone
    3. AB14-AB16 = XLOOKUP(pincode, M!A:A, M!I:I) -> Delhivery zone
    4. AB17 = SWITCH(state_code, ...) -> Affinity zone
    5. AA13 = XLOOKUP(zone, rates...) -> Bluedart price
    6. AA14 = Delhivery 1kg price
    7. AA15 = Delhivery 10kg price
    8. AA16 = Delhivery 20kg price
    9. AA17 = Affinity price
    10. X19 = MIN(AA13:AA17) -> Minimum fee
    11. X20 = XLOOKUP(X19, AA13:AA17, Z13:Z17) -> Best carrier
    
    Args:
        weight_kg: Shipment weight in kg
        pincode: 6-digit Indian destination pincode
        pincode_db: Dict { pincode: { delhivery_zone, bluedart_zone, state_code,
                    city, prepaid, cod, reverse_pickup, express_tat, surface_tat,
                    bd_state_code, bd_serviceable } }
        include_affinity: Include Affinity in MIN comparison (default: True)
    """
    # --- STEP 1: Pincode lookup ---
    pin = pincode_db.get(pincode) or pincode_db.get(str(pincode))
    if not pin:
        return {"error": f"Pincode {pincode} not found in database"}
    
    delhivery_zone = pin.get("delhivery_zone")   # M sheet Column I
    bluedart_zone = pin.get("bluedart_zone")      # M sheet Column J
    state_code = pin.get("state_code")            # M sheet Column F
    
    # Derive Affinity zone from state code (SWITCH formula in AB17)
    affinity_zone = STATE_TO_AFFINITY_ZONE.get(state_code)
    # Special: Guwahati pincodes (781xxx) in Assam -> NE1 instead of NE2
    if state_code == "AS" and str(pincode).startswith("781"):
        affinity_zone = "NE1"
    
    # --- STEP 2: Calculate all carrier prices ---
    price_affinity = calculate_affinity(weight_kg, affinity_zone) if affinity_zone else None
    price_bluedart = calculate_bluedart(weight_kg, bluedart_zone)
    price_d1kg = calculate_delhivery_1kg(weight_kg, delhivery_zone) if delhivery_zone else None
    price_d10kg = calculate_delhivery_10kg(weight_kg, delhivery_zone) if delhivery_zone else None
    price_d20kg = calculate_delhivery_20kg(weight_kg, delhivery_zone) if delhivery_zone else None
    
    # --- STEP 3: Build comparison (Z13:Z17 + AA13:AA17) ---
    comparison = {}
    if price_bluedart is not None:
        comparison["Bluedart"] = price_bluedart          # AA13
    if price_d1kg is not None:
        comparison["D(1 Kg)"] = price_d1kg               # AA14
    if price_d10kg is not None:
        comparison["D(10 kg)"] = price_d10kg             # AA15
    if price_d20kg is not None:
        comparison["D(20 kg)"] = price_d20kg             # AA16
    if include_affinity and price_affinity is not None:
        comparison["Affinity"] = price_affinity          # AA17
    
    if not comparison:
        return {"error": "No carrier serviceable for this pincode/zone"}
    
    # --- STEP 4: Find minimum (X19 and X20) ---
    min_carrier = min(comparison, key=comparison.get)
    min_price = comparison[min_carrier]
    
    # --- STEP 5: Return complete result ---
    return {
        "inputs": {"weight_kg": weight_kg, "pincode": pincode},
        "zone_lookups": {
            "delhivery_zone": delhivery_zone,
            "bluedart_zone": bluedart_zone,
            "affinity_zone": affinity_zone,
            "state_code": state_code,
        },
        "pincode_info": {
            "city": pin.get("city", ""),
            "prepaid": pin.get("prepaid", ""),
            "cod": pin.get("cod", ""),
            "reverse_pickup": pin.get("reverse_pickup", ""),
            "express_tat": pin.get("express_tat", ""),
            "surface_tat": pin.get("surface_tat", ""),
            "bd_serviceable": pin.get("bd_serviceable", ""),
        },
        "carrier_prices": {
            "Affinity": price_affinity,
            "Bluedart": price_bluedart,
            "D(1 Kg)": price_d1kg,
            "D(10 kg)": price_d10kg,
            "D(20 kg)": price_d20kg,
        },
        "comparison_candidates": comparison,
        "minimum_logistics_fee": min_price,       # X19
        "preferred_partner": min_carrier,          # X20
        "gst": "excluded_from_all_prices",
    }


# ================================================================
# PINCODE DATABASE LOADER
# ================================================================

def load_pincode_db_from_csv(filepath):
    """
    Load M sheet data exported as CSV.
    Expected columns: Pincode (A), Prepaid (B), Reverse Pickup (C),
    COD (D), City (E), State (F), Express TAT (G), Surface TAT (H),
    Zone (I), BD-Zone (J), State Code (K), BD Serviceable (L)
    """
    import csv
    db = {}
    with open(filepath, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pin = row.get("Pincode", "").strip()
            if pin:
                db[pin] = {
                    "delhivery_zone": row.get("Zone", "").strip(),
                    "bluedart_zone": row.get("BD-Zone", "").strip(),
                    "state_code": row.get("State", "").strip(),
                    "city": row.get("City", "").strip(),
                    "prepaid": row.get("Prepaid", "").strip(),
                    "cod": row.get("COD", "").strip(),
                    "reverse_pickup": row.get("Reverse Pickup", "").strip(),
                    "express_tat": row.get("Express TAT", "").strip(),
                    "surface_tat": row.get("Surface TAT", "").strip(),
                    "bd_state_code": row.get("State Code", "").strip(),
                    "bd_serviceable": row.get("BD Serviceable", "").strip(),
                }
    return db


# ================================================================
# VERIFICATION TEST
# ================================================================

if __name__ == "__main__":
    # Test case: Weight=85kg, Pincode=500001 (Hyderabad, Telangana)
    # Expected: Delhivery zone C2, Bluedart zone SOUTH, State TS
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
            "bd_state_code": "HYD",
            "bd_serviceable": "Yes",
        }
    }
    
    result = calculate_best_rate(85, 500001, test_db)
    
    print("=" * 60)
    print("VERIFICATION: Weight=85kg, Pincode=500001")
    print("=" * 60)
    print(f"Zones: Del={result['zone_lookups']['delhivery_zone']}, "
          f"BD={result['zone_lookups']['bluedart_zone']}, "
          f"Aff={result['zone_lookups']['affinity_zone']}")
    print()
    print("Carrier Prices:")
    for c, p in result["carrier_prices"].items():
        tag = " <-- MIN" if p == result["minimum_logistics_fee"] else ""
        print(f"  {c:15s}: Rs {p:,.4f}{tag}" if p else f"  {c:15s}: N/A")
    print()
    print(f"Minimum Fee: Rs {result['minimum_logistics_fee']:,.2f}")
    print(f"Best Carrier: {result['preferred_partner']}")
    
    # Verify against spreadsheet values
    expected = {
        "Affinity": 1468.5,
        "Bluedart": 1438.515,
        "D(1 Kg)": 2502,
        "D(10 kg)": 1665,
        "D(20 kg)": 1300,
    }
    
    print()
    print("Verification vs Excel:")
    for c, exp in expected.items():
        actual = result["carrier_prices"][c]
        ok = "PASS" if abs(actual - exp) < 0.01 else "FAIL"
        print(f"  {c:15s}: Expected {exp:>10,.4f} | Got {actual:>10,.4f} | {ok}")
    
    assert result["minimum_logistics_fee"] == 1300
    assert result["preferred_partner"] == "D(20 kg)"
    print()
    print(f"MIN fee: Rs 1,300.00 PASS")
    print(f"Partner: D(20 kg) PASS")
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


# ================================================================
# USAGE GUIDE
# ================================================================
# 
# 1. Export M sheet from Excel as CSV (columns A through L)
# 2. In your app:
#    pincode_db = load_pincode_db_from_csv("m_sheet.csv")
#    result = calculate_best_rate(weight_kg=50, pincode=110001, pincode_db=pincode_db)
#    print(result["minimum_logistics_fee"])    # cheapest price
#    print(result["preferred_partner"])         # carrier name
#    print(result["carrier_prices"])            # all 5 prices
# 
# 3. To update rates later:
#    - Update AFFINITY_RATES, BLUEDART_RATES, DELHIVERY_10KG/20KG/1KG dicts
#    - Update AFFINITY_CFG/BLUEDART_CFG surcharge values
#    - Zone mappings rarely change
# 
# 4. All prices are GST EXCLUSIVE. Apply GST in your app if needed.
# ================================================================
