# Test Analytics Accuracy Skill

This skill provides sample test scripts and validation workflows for your Stock AI Options analytics modules.

## Files Included

- **`SKILL.md`**: Complete documentation and testing guidelines
- **`test_predictor_sample.py`**: Validate ML predictor model accuracy
- **`test_greeks_sample.py`**: Verify Black-Scholes Greeks calculations
- **`test_sentiment_sample.py`**: Check sentiment analysis consistency
- **`test_volume_sample.py`**: Test volume anomaly detection

## Quick Usage

### Run Individual Test
```bash
cd /Users/manjunaathkuracha/Stock_Ai_options
python .github/skills/test-analytics-accuracy/test_greeks_sample.py
python .github/skills/test-analytics-accuracy/test_volume_sample.py
```

### Add to Your Workflow
These tests are designed to be called when:
- Making changes to analytics modules
- Validating data accuracy before deployment
- Debugging why predictions aren't matching expectations
- Ensuring Greeks calculations are mathematically correct

## What Gets Tested

| Module | Test File | Validates |
|--------|-----------|-----------|
| `predictor.py` | `test_predictor_sample.py` | Feature preparation, model training, numeric outputs |
| `greeks.py` | `test_greeks_sample.py` | Delta/gamma ranges, edge cases, calculation accuracy |
| `sentiment.py` | `test_sentiment_sample.py` | Score ranges, label classification, scale conversion |
| `volume_detector.py` | `test_volume_sample.py` | Anomaly detection, z-scores, Put/Call ratios |

## Integration with Agents

Use with your **Stock Analytics Specialist** agent:

```
@analytics Fix this Greeks calculation and validate it with the test suite
@analytics Run volume tests after updating the anomaly threshold
@analytics Test predictor accuracy on the latest data
```

The agent will automatically run the appropriate test and validate your changes.

## Customization

To create additional tests:
1. Copy a sample test file
2. Add your specific test cases
3. Follow the validation pattern (assert conditions, print results)
4. Run to verify: `python your_test.py`
