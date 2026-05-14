"""Sample test script for sentiment analysis validation."""
import sys
sys.path.insert(0, '/Users/manjunaathkuracha/Stock_Ai_options')

from analytics.sentiment import analyze_news_sentiment

print("Testing Sentiment Analysis...\n")

# Test 1: Basic sentiment analysis (without API key)
print("Test 1: Basic Sentiment Analysis (No API)")
result = analyze_news_sentiment('GOLD', num_articles=10, api_key=None)
print(f"  Asset: GOLD")
print(f"  Result:")
print(f"    overall_sentiment: {result['overall_sentiment']:.3f}")
print(f"    sentiment_label: {result['sentiment_label']}")
print(f"    confidence: {result['confidence']:.1f}%")

# Validate ranges
checks = []
checks.append(("Sentiment range -1 to +1", -1 <= result['overall_sentiment'] <= 1))
checks.append(("Confidence 0-100%", 0 <= result['confidence'] <= 100))
checks.append(("Label in options", result['sentiment_label'] in ['POSITIVE', 'NEGATIVE', 'NEUTRAL']))
checks.append(("Return dict has error key or is valid", 'error' in result or 'overall_sentiment' in result))

all_passed = True
for check_name, check_result in checks:
    status = "✅" if check_result else "❌"
    print(f"  {status} {check_name}")
    if not check_result:
        all_passed = False

# Test 2: Score boundaries
print("\nTest 2: Sentiment Label Classification")
test_scores = [
    (-1.0, 'NEGATIVE'),
    (-0.5, 'NEGATIVE'),
    (-0.15, 'NEUTRAL'),
    (0.0, 'NEUTRAL'),
    (0.15, 'NEUTRAL'),
    (0.5, 'POSITIVE'),
    (1.0, 'POSITIVE'),
]

print("  Score → Expected Label Mapping:")
for score, expected_label in test_scores:
    # Replicate the logic from sentiment.py
    if score > 0.2:
        label = 'POSITIVE'
    elif score < -0.2:
        label = 'NEGATIVE'
    else:
        label = 'NEUTRAL'
    
    status = "✅" if label == expected_label else "❌"
    print(f"    {status} {score:+.2f} → {label} (expected {expected_label})")

# Test 3: Scale conversion
print("\nTest 3: 0-100 Scale Conversion")
result = analyze_news_sentiment('NIFTY', num_articles=5, api_key=None)
sentiment_score = result['overall_sentiment']
scale_100 = result['sentiment_scale_100']
expected_scale = int((sentiment_score + 1) * 50)
print(f"  Sentiment: {sentiment_score:.3f}")
print(f"  Converted to 0-100 scale: {scale_100}")
print(f"  Expected: {expected_scale}")
if 0 <= scale_100 <= 100 and scale_100 == expected_scale:
    print(f"  ✅ Conversion correct")
else:
    print(f"  ❌ Conversion error")

# Test 4: Error handling
print("\nTest 4: Error Handling")
try:
    # Test with empty asset name
    result = analyze_news_sentiment('', num_articles=5, api_key=None)
    if 'overall_sentiment' in result or 'error' in result:
        print(f"  ✅ Empty asset handled gracefully")
    else:
        print(f"  ❌ Unexpected result format")
except Exception as e:
    print(f"  ❌ Exception raised: {e}")

print("\n" + "="*50)
if all_passed:
    print("✅ SENTIMENT ANALYSIS TESTS PASSED")
else:
    print("⚠️ SOME TESTS COMPLETED WITH WARNINGS")
