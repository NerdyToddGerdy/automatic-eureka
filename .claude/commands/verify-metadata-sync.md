---
description: Verify PNG metadata and database are in sync
---

# Metadata Sync Verification

Checking that PNG file metadata matches database entries (our critical invariant).

---

## Current Database State

!`sqlite3 tokens.db "SELECT COUNT(*) as total_tokens FROM tokens" 2>/dev/null || echo "Database not found or empty"`

!`sqlite3 tokens.db "SELECT image_type, COUNT(*) as count FROM tokens GROUP BY image_type" 2>/dev/null || echo "Run app to create database"`

---

## Verification Steps

### 1. Check Database Integrity

!`sqlite3 tokens.db "PRAGMA integrity_check" 2>/dev/null || echo "Database check skipped"`

### 2. Find Tokens with Missing Files

!`python -c "
from database import TokenDatabase
import os

db = TokenDatabase('tokens.db')
tokens = db.get_all_tokens()
missing = [t for t in tokens if not os.path.exists(t['filepath'])]

if missing:
    print(f'⚠️  Found {len(missing)} tokens with missing files:')
    for t in missing[:10]:
        print(f'  - {t[\"filename\"]} (ID: {t[\"id\"]})')
else:
    print('✅ All token files exist')
" 2>/dev/null || echo "Run Python script to check files"`

### 3. Verify Metadata Consistency

Checking a sample of tokens to ensure PNG metadata matches database:

!`python -c "
from database import TokenDatabase
from metadata import TokenMetadata
import os

db = TokenDatabase('tokens.db')
tokens = db.get_all_tokens()[:10]  # Sample first 10

mismatches = []
for token in tokens:
    if not os.path.exists(token['filepath']):
        continue

    # Read PNG metadata
    try:
        png_meta = TokenMetadata.read_token_metadata(token['filepath'])
        db_meta = token

        # Compare key fields
        if png_meta.get('ImageType') != db_meta.get('image_type'):
            mismatches.append(f\"{token['filename']}: ImageType mismatch\")
        if png_meta.get('Name') != db_meta.get('name'):
            mismatches.append(f\"{token['filename']}: Name mismatch\")
    except Exception as e:
        mismatches.append(f\"{token['filename']}: Error reading PNG - {str(e)}\")

if mismatches:
    print(f'⚠️  Found {len(mismatches)} mismatches:')
    for m in mismatches:
        print(f'  - {m}')
else:
    print('✅ Sampled tokens have consistent metadata')
" 2>/dev/null || echo "Run Python script to verify metadata"`

---

## Common Issues and Fixes

### Issue: Missing Files
**Cause**: Files moved/deleted after being added to database
**Fix**: Mark as missing or remove from database

!`python -c "
from database import TokenDatabase
import os

db = TokenDatabase('tokens.db')
tokens = db.get_all_tokens()

for token in tokens:
    if not os.path.exists(token['filepath']):
        db.mark_missing(token['id'], True)
        print(f'Marked as missing: {token[\"filename\"]}')
" 2>/dev/null || echo "Run to mark missing files"`

### Issue: Metadata Out of Sync
**Cause**: Database updated but PNG not written (violation of contract)
**Fix**: Rescan to rebuild from PNG files (PNG is source of truth)

!`curl -X POST http://localhost:5000/api/scan 2>/dev/null || echo "Start app and run: curl -X POST http://localhost:5000/api/scan"`

### Issue: Duplicate Entries
**Cause**: Same file added multiple times
**Fix**: Remove duplicates keeping the most recent

!`sqlite3 tokens.db "
SELECT filepath, COUNT(*) as count
FROM tokens
GROUP BY filepath
HAVING count > 1
" 2>/dev/null || echo "Check for duplicates"`

---

## Metadata Contract Verification

### ✅ Expected Behavior
1. PNG files contain metadata in text chunks
2. Database mirrors PNG metadata
3. Updates go to PNG first, then database
4. PNG files can be moved; database rebuilt by scanning

### ❌ Contract Violations
- Writing to database without updating PNG
- Deleting PNG but leaving database entry
- Manually editing database instead of using API

---

## Recommendations

Based on the verification:

1. **If all checks pass**: ✅ Metadata sync is healthy
2. **If missing files found**: Run cleanup or rescan
3. **If mismatches found**: Investigate cause and rescan
4. **If duplicates found**: Deduplicate database

### Preventive Measures
- Always use the API for updates (enforces PNG-first)
- Regular backup of both PNG files and database
- Monitor for file system changes
- Use reference mode for large collections

---

## Manual Rescan (if needed)

!`curl -X POST http://localhost:5000/api/scan 2>/dev/null || echo "Start Flask app first: python3 app.py"`

---

Verification complete! Address any issues found above.