"""Sample test script for Greeks calculation validation."""
import sys
sys.path.insert(0, '/Users/manjunaathkuracha/Stock_Ai_options')

from analytics.greeks import calculate_greeks
import numpy as np

print("Testing Greeks Calculations...\n")

# Test cases with known benchmarks
test_cases = [
    {
        'name': 'ATM Call (S=K)',
        'S': 100, 'K': 100, 'T': 0.25, 'r': 0.05, 'sigma': 0.2, 'option_type': 'call',
        'expected_delta_range': (0.4, 0.6),  # ATM delta ~0.5
        'expected_gamma_positive': True,
    },
    {
        'name': 'ITM Call (S > K)',
        'S': 110, 'K': 100, 'T': 0.25, 'r': 0.05, 'sigma': 0.2, 'option_type': 'call',
        'expected_delta_range': (0.7, 1.0),  # ITM delta > 0.5
        'expected_gamma_positive': True,
    },
    {
        'name': 'OTM Call (S < K)',
        'S': 90, 'K': 100, 'T': 0.25, 'r': 0.05, 'sigma': 0.2, 'option_type': 'call',
        'expected_delta_range': (0.0, 0.3),  # OTM delta < 0.5
        'expected_gamma_positive': True,
    },
    {
        'name': 'ATM Put (S=K)',
        'S': 100, 'K': 100, 'T': 0.25, 'r': 0.05, 'sigma': 0.2, 'option_type': 'put',
        'expected_delta_range': (-0.6, -0.4),  # Put delta ~-0.5
        'expected_gamma_positive': True,
    },
]

passed = 0
failed = 0

for test in test_cases:
    try:
        result = calculate_greeks(
            S=test['S'],
            K=test['K'],
            T=test['T'],
            r=test['r'],
            sigma=test['sigma'],
            option_type=test['option_type']
        )
        
        print(f"Test: {test['name']}")
        
        # Check for error key
        if 'error' in result:
            print(f"  ❌ FAILED: {result['error']}")
            failed += 1
            continue
        
        # Validate delta range
        delta = result.get('delta', 0)
        min_delta, max_delta = test['expected_delta_range']
        if not (min_delta <= delta <= max_delta):
            print(f"  ❌ Delta out of range: {delta} (expected {min_delta}-{max_delta})")
            failed += 1
            continue
        
        # Validate gamma is positive
        gamma = result.get('gamma', 0)
        if gamma <= 0:
            print(f"  ❌ Gamma not positive: {gamma}")
            failed += 1
            continue
        
        # Check numeric validity
        for key in ['delta', 'gamma', 'theta', 'vega', 'rho']:
            val = result.get(key, 0)
            if not isinstance(val, (int, float)) or np.isnan(val) or np.isinf(val):
                print(f"  ❌ Invalid {key} value: {val}")
                failed += 1
                continue
        
        print(f"  ✅ PASSED (delta={delta:.3f}, gamma={gamma:.4f}, premium={result.get('premium', 0):.2f})")
        passed += 1
        
    except Exception as e:
        print(f"Test: {test['name']}")
        print(f"  ❌ ERROR: {type(e).__name__}: {e}")
        failed += 1

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("✅ ALL GREEKS TESTS PASSED")
else:
    print(f"❌ {failed} test(s) failed")
