import pytest
import sys
import os

# Add the function directory to path so rate_calculator can be imported
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "functions", "shipping-calc-new"))

from rate_calculator import (
    calculate_affinity,
    calculate_bluedart,
    calculate_delhivery_1kg,
    calculate_delhivery_10kg,
    calculate_delhivery_20kg,
    get_pincodes_data,
    find_best_rate,
)


class TestRateCalculator:
    """Test cases for shipping rate calculator"""

    @pytest.fixture
    def pincodes(self):
        """Load pincodes data"""
        return get_pincodes_data()

    def test_pincode_500001_zones(self, pincodes):
        """Test zone lookups for pincode 500001 (Hyderabad)"""
        pincode_info = pincodes.get(500001)
        assert pincode_info is not None, "Pincode 500001 should exist"

        assert pincode_info['delhivery_zone'] == 'C2', "Delhivery zone should be C2"
        assert pincode_info['bluedart_zone'] == 'SOUTH', "Bluedart zone should be SOUTH"
        assert pincode_info['state_code'] == 'TS', "State code should be TS"

    def test_affinity_calculation(self, pincodes):
        """Test Affinity calculation for weight=85, pincode=500001"""
        # Pincode 500001 -> State TS -> Affinity zone = South 1
        # From STATE_TO_AFFINITY_ZONE: TS -> South 1
        # Rate: 14 (per kg for South 1)
        # Formula: freight = max(max(85, 20) * 14, 300) = max(1190, 300) = 1190
        # total = freight + 100 + freight*0.15 = 1190 + 100 + 178.5 = 1468.5
        result = calculate_affinity(85, pincodes, pincode=500001)
        assert abs(result - 1468.5) < 0.01, f"Expected 1468.5, got {result}"

    def test_bluedart_calculation(self, pincodes):
        """Test Bluedart calculation for weight=85, pincode=500001"""
        # Pincode 500001 -> Bluedart zone = SOUTH
        # Rate: 12.7 (per kg for South)
        # Formula: freight = 12.7 * max(85, 10) = 12.7 * 85 = 1079.5
        # total = (1079.5 + 75 + 75) * 1.17 = 1229.5 * 1.17 = 1438.515
        result = calculate_bluedart(85, pincodes, pincode=500001)
        assert abs(result - 1438.515) < 0.01, f"Expected 1438.515, got {result}"

    def test_delhivery_1kg_calculation(self, pincodes):
        """Test Delhivery 1KG calculation for weight=85, pincode=500001"""
        # Pincode 500001 -> Delhivery zone = C2
        # Rate: base=66, additional=29
        # Formula: 66 + (85 - 1) * 29 = 66 + 84 * 29 = 66 + 2436 = 2502
        result = calculate_delhivery_1kg(85, pincodes, pincode=500001)
        assert result == 2502, f"Expected 2502, got {result}"

    def test_delhivery_10kg_calculation(self, pincodes):
        """Test Delhivery 10KG calculation for weight=85, pincode=500001"""
        # Pincode 500001 -> Delhivery zone = C2
        # Rate: flat_10kg=240, additional_per_kg=19
        # Formula: 240 + (85 - 10) * 19 = 240 + 75 * 19 = 240 + 1425 = 1665
        result = calculate_delhivery_10kg(85, pincodes, pincode=500001)
        assert result == 1665, f"Expected 1665, got {result}"

    def test_delhivery_20kg_calculation(self, pincodes):
        """Test Delhivery 20KG calculation for weight=85, pincode=500001"""
        # Pincode 500001 -> Delhivery zone = C2
        # Rate for C2: flat_20kg=330, rate_20_50=16, rate_50_100=14, rate_100_plus=12
        # Weight 85kg falls in 50-100kg slab
        # Formula: flat_20kg + 30*rate_20_50 + (weight-50)*rate_50_100
        # 330 + 30*16 + 35*14 = 330 + 480 + 490 = 1300
        result = calculate_delhivery_20kg(85, pincodes, pincode=500001)
        assert result == 1300, f"Expected 1300, got {result}"

    def test_find_best_rate(self, pincodes):
        """Test finding the best carrier rate"""
        rates = {
            'Affinity': 1468.5,
            'Bluedart': 1438.515,
            'D(1 Kg)': 2502,
            'D(10 kg)': 1665,
            'D(20 kg)': 1300,
        }
        best_carrier, best_price = find_best_rate(rates)
        assert best_carrier == 'D(20 kg)', f"Best carrier should be D(20 kg)"
        assert best_price == 1300, f"Best price should be 1300"

    def test_full_rate_calculation(self, pincodes):
        """Test full rate calculation for weight=85, pincode=500001"""
        weight = 85
        pincode = 500001

        affinity = calculate_affinity(weight, pincodes, pincode=pincode)
        bluedart = calculate_bluedart(weight, pincodes, pincode=pincode)
        delhivery_1kg = calculate_delhivery_1kg(weight, pincodes, pincode=pincode)
        delhivery_10kg = calculate_delhivery_10kg(weight, pincodes, pincode=pincode)
        delhivery_20kg = calculate_delhivery_20kg(weight, pincodes, pincode=pincode)

        rates = {
            'Affinity': affinity,
            'Bluedart': bluedart,
            'D(1 Kg)': delhivery_1kg,
            'D(10 kg)': delhivery_10kg,
            'D(20 kg)': delhivery_20kg,
        }

        # Verify each rate
        assert abs(affinity - 1468.5) < 0.01
        assert abs(bluedart - 1438.515) < 0.01
        assert delhivery_1kg == 2502
        assert delhivery_10kg == 1665
        assert delhivery_20kg == 1300

        # Find best
        best_carrier, best_price = find_best_rate(rates)
        assert best_carrier == 'D(20 kg)'
        assert best_price == 1300
