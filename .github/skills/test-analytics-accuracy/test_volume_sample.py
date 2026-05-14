"""Sample test script for volume detection validation."""
import sys
sys.path.insert(0, '/Users/manjunaathkuracha/Stock_Ai_options')

import pandas as pd
import numpy as np
from analytics.volume_detector import detect_volume_anomaly, detect_put_call_ratio_anomaly

print("Testing Volume Detection...\n")

# Test 1: Normal volume (no anomaly)
print("Test 1: Normal Volume Pattern")
normal_volumes = pd.Series([1000000] * 25)
result = detect_volume_anomaly(normal_volumes, window=20, threshold_sigma=2.0)
print(f"  Volume: constant 1M")
print(f"  Result: anomaly={result['is_anomaly']}, score={result['anomaly_score']:.1f}")
if not result['is_anomaly']:
    print(f"  ✅ PASSED")
else:
    print(f"  ❌ FAILED: Should not detect anomaly in constant data")

# Test 2: Volume spike (should detect anomaly)
print("\nTest 2: Volume Spike Anomaly")
spike_volumes = pd.Series([1000000] * 20 + [5000000])  # 5x spike
result = detect_volume_anomaly(spike_volumes, window=20, threshold_sigma=2.0)
print(f"  Volume: 20×1M then spike to 5M")
print(f"  Result: anomaly={result['is_anomaly']}, z_score={result['z_score']:.2f}")
if result['is_anomaly']:
    print(f"  ✅ PASSED")
else:
    print(f"  ❌ FAILED: Should detect spike as anomaly")

# Test 3: Insufficient data
print("\nTest 3: Insufficient Data Handling")
short_volumes = pd.Series([1000000, 1100000])
result = detect_volume_anomaly(short_volumes, window=20, threshold_sigma=2.0)
print(f"  Volume: only 2 data points (window=20)")
print(f"  Result: is_anomaly={result['is_anomaly']}, message={result.get('message', 'N/A')}")
if not result['is_anomaly'] and 'Insufficient' in result.get('message', ''):
    print(f"  ✅ PASSED")
else:
    print(f"  ❌ FAILED: Should handle insufficient data gracefully")

# Test 4: Put/Call Ratio
print("\nTest 4: Put/Call Ratio Anomaly")
test_cases = [
    {'name': 'Bullish (low PCR)', 'put': 50000, 'call': 100000, 'expect_anomaly': True},
    {'name': 'Neutral PCR', 'put': 100000, 'call': 100000, 'expect_anomaly': False},
    {'name': 'Bearish (high PCR)', 'put': 150000, 'call': 100000, 'expect_anomaly': True},
]

for case in test_cases:
    result = detect_put_call_ratio_anomaly(case['put'], case['call'])
    pcr = case['put'] / case['call']
    is_anomaly = result.get('is_anomaly', False)
    print(f"  {case['name']}: PCR={pcr:.2f}, anomaly={is_anomaly}", end="")
    if is_anomaly == case['expect_anomaly']:
        print(" ✅")
    else:
        print(" ❌")

# Test 5: Edge cases
print("\nTest 5: Edge Cases")
edge_cases = [
    {'name': 'Zero average volume', 'put': 0, 'call': 0},
    {'name': 'Zero put volume', 'put': 0, 'call': 100000},
    {'name': 'Zero call volume', 'put': 100000, 'call': 0},
]

for case in edge_cases:
    try:
        result = detect_put_call_ratio_anomaly(case['put'], case['call'])
        print(f"  {case['name']}: ✅ No crash (result={result.get('is_anomaly', 'N/A')})")
    except Exception as e:
        print(f"  {case['name']}: ❌ ERROR: {e}")

print("\n" + "="*50)
print("✅ VOLUME DETECTION TESTS COMPLETED")
