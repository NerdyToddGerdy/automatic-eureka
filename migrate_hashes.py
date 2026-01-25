#!/usr/bin/env python3
"""
Migration script to calculate and store file hashes for existing tokens.
Run this once to populate the file_hash column for all existing database entries.
"""

import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import TokenDatabase
from file_utils import calculate_file_hash


def migrate_hashes():
    """Calculate and store hashes for all existing tokens."""
    db = TokenDatabase('tokens.db')

    print("Image Vault - Hash Migration")
    print("=" * 50)
    print()

    # Get all tokens
    tokens = db.get_all_tokens()
    total = len(tokens)

    if total == 0:
        print("No tokens found in database.")
        return

    print(f"Found {total} tokens. Calculating hashes...")
    print()

    success_count = 0
    missing_count = 0
    error_count = 0

    for i, token in enumerate(tokens, 1):
        token_id = token['id']
        filepath = token['filepath']
        filename = token['filename']

        # Progress indicator
        print(f"[{i}/{total}] {filename}...", end=" ")

        try:
            # Check if file exists
            if not os.path.exists(filepath):
                print("MISSING")
                db.mark_missing(token_id, True)
                missing_count += 1
                continue

            # Calculate hash
            file_hash = calculate_file_hash(filepath)

            # Update database
            db.update_file_hash(token_id, file_hash)
            db.mark_missing(token_id, False)
            db.update_last_verified(token_id, datetime.now().isoformat())

            print(f"OK ({file_hash[:12]}...)")
            success_count += 1

        except Exception as e:
            print(f"ERROR: {str(e)}")
            db.mark_missing(token_id, True)
            error_count += 1

    print()
    print("=" * 50)
    print("Migration Complete")
    print(f"  ✓ Success: {success_count}")
    print(f"  ⚠ Missing: {missing_count}")
    print(f"  ✗ Errors: {error_count}")
    print()

    # Check for duplicates
    if success_count > 0:
        print("Checking for duplicate content...")
        duplicates = find_duplicates(db)

        if duplicates:
            print(f"\n⚠ Found {len(duplicates)} sets of duplicate files:")
            for dup_set in duplicates:
                print(f"\n  Hash: {dup_set['hash'][:12]}...")
                for token in dup_set['tokens']:
                    print(f"    - {token['filename']} ({token['filepath']})")
        else:
            print("  No duplicates found.")

    print()


def find_duplicates(db):
    """Find tokens with duplicate hashes."""
    try:
        # Query for hashes that appear more than once
        import sqlite3
        conn = sqlite3.connect('tokens.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT file_hash, COUNT(*) as count
            FROM tokens
            WHERE file_hash IS NOT NULL
            GROUP BY file_hash
            HAVING count > 1
        ''')

        duplicate_hashes = cursor.fetchall()

        duplicates = []
        for row in duplicate_hashes:
            file_hash = row['file_hash']

            # Get all tokens with this hash
            cursor.execute('SELECT * FROM tokens WHERE file_hash = ?', (file_hash,))
            tokens = [dict(t) for t in cursor.fetchall()]

            duplicates.append({
                'hash': file_hash,
                'count': row['count'],
                'tokens': tokens
            })

        conn.close()
        return duplicates

    except Exception as e:
        print(f"Error checking duplicates: {e}")
        return []


if __name__ == '__main__':
    try:
        migrate_hashes()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)
