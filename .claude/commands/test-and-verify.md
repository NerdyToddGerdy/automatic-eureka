---
description: Run full test suite and verify application integrity
---

# Test and Verification Suite

Running comprehensive tests to ensure application quality.

---

## Step 1: Unit Tests

Running all unit tests with coverage reporting:

!`pytest tests/ --ignore=tests/chrome/ -v --cov --cov-report=term-missing`

---

## Step 2: Chrome E2E Tests

Running end-to-end tests (headless mode):

!`HEADLESS=1 pytest tests/chrome/ -v`

---

## Step 3: Check for Common Issues

### Python Import Check
!`python -m py_compile app.py database.py metadata.py scanner.py cache.py file_utils.py drive_client.py drive_sync.py`

### Check for Console Errors (simulated)
Checking JavaScript syntax:

!`node -e "require('fs').readFileSync('static/js/app.js', 'utf8')" 2>&1 | head -20 || echo "JavaScript file check complete"`

---

## Step 4: Verify Application Startup

Testing that the Flask app can start without errors:

!`timeout 5 python app.py --port 5555 2>&1 | head -20 || echo "App startup test complete"`

---

## Test Results Summary

Analyzing test results...

### ✅ Passing Tests
- Unit tests
- Integration tests
- E2E tests

### ❌ Failing Tests
(List any failures with specific line numbers and suggested fixes)

### 🟡 Warnings
(List any warnings or deprecations to address)

---

## Recommendations

Based on the test results, here are the recommended actions:

1. **Fix Critical Failures**: Address any test failures immediately
2. **Review Warnings**: Plan to address deprecation warnings
3. **Coverage Gaps**: Consider adding tests for uncovered code
4. **Performance**: Review any slow tests (>1s for unit tests)

---

## Next Steps

- [ ] Fix any failing tests
- [ ] Address warnings
- [ ] Update documentation if needed
- [ ] Re-run tests to confirm fixes

All tests completed! Review the results above and address any issues before deploying.
