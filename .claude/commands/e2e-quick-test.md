---
description: Quick end-to-end test of critical user workflows
---

# Quick E2E Test

Running quick end-to-end tests for critical user journeys.

---

## Test Environment Setup

### 1. Start Flask Server

!`timeout 5 python3 app.py --port 5001 > /tmp/flask_test.log 2>&1 & echo $! > /tmp/flask_test.pid && sleep 2 && echo "Flask started on port 5001"`

### 2. Verify Server Running

!`curl -s http://localhost:5001/ | head -20 || echo "Server not responding"`

---

## Critical Test Scenarios

### Test 1: Upload Workflow
**User Story**: As a user, I want to upload a token image

!`HEADLESS=1 pytest tests/chrome/test_upload.py::TestFileUpload::test_upload_single_png -v 2>&1 | tail -20`

**Status**: Check output above

---

### Test 2: Search and Filter
**User Story**: As a user, I want to search for tokens by name

!`HEADLESS=1 pytest tests/chrome/test_search_filter.py::TestSearchAndFiltering::test_search_by_filename -v 2>&1 | tail -20`

**Status**: Check output above

---

### Test 3: Edit Token Metadata
**User Story**: As a user, I want to update token information

!`HEADLESS=1 pytest tests/chrome/test_token_edit.py::TestTokenEdit::test_edit_token_name -v 2>&1 | tail -20`

**Status**: Check output above

---

### Test 4: Bulk Operations
**User Story**: As a user, I want to bulk edit multiple tokens

!`HEADLESS=1 pytest tests/chrome/test_bulk_ops.py::TestBulkOperations::test_bulk_edit_tags -v 2>&1 | tail -20`

**Status**: Check output above

---

### Test 5: View Switching
**User Story**: As a user, I want to switch between grid and list views

!`HEADLESS=1 pytest tests/chrome/test_gallery_views.py::TestGalleryViews::test_switch_to_list_view -v 2>&1 | tail -20`

**Status**: Check output above

---

## API Health Check

### Endpoints Test

!`curl -s http://localhost:5001/api/tokens | python -m json.tool | head -20 2>/dev/null || echo "Check API endpoint"`

!`curl -s http://localhost:5001/api/stats | python -m json.tool 2>/dev/null || echo "Check stats endpoint"`

---

## Cleanup

### Stop Flask Server

!`kill $(cat /tmp/flask_test.pid) 2>/dev/null || echo "Flask server stopped"`

---

## Test Summary

### ✅ Passing Tests
- (List passing tests)

### ❌ Failing Tests
- (List failing tests with details)

### Performance Notes
- (Any slow tests or timeouts)

---

## Smoke Test Results

**Overall Status**: ✅ PASS / ❌ FAIL

**Critical Path Verified**:
1. Upload → Search → Edit → Delete workflow
2. Bulk operations
3. UI interactions

**Recommendation**:
- If all pass: ✅ Safe to deploy
- If any fail: ❌ Investigate failures before deploying

---

## Manual Verification Checklist

For comprehensive testing, also verify manually:

- [ ] App starts without errors
- [ ] Images display correctly
- [ ] Filters work as expected
- [ ] Modal interactions smooth
- [ ] No console errors (F12)
- [ ] Responsive design on different screen sizes
- [ ] File upload progress indicators work
- [ ] Thumbnail generation works
- [ ] Google Drive sync (if configured)
- [ ] Electron mode (if applicable)

---

Quick test complete! Review results above before deploying.