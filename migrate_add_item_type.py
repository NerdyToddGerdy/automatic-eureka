#!/usr/bin/env python3
"""
Migration script to add Item type support to existing databases.
Adds rarity, category, and attunement columns to the tokens table.
"""
import sqlite3
import os

def migrate_database(db_path='tokens.db'):
    """Add Item type columns to existing database."""
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Skipping migration.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if columns already exist
    cursor.execute("PRAGMA table_info(tokens)")
    columns = [col[1] for col in cursor.fetchall()]

    columns_to_add = []
    if 'rarity' not in columns:
        columns_to_add.append('rarity TEXT')
    if 'category' not in columns:
        columns_to_add.append('category TEXT')
    if 'attunement' not in columns:
        columns_to_add.append('attunement TEXT')

    if not columns_to_add:
        print("All Item type columns already exist. No migration needed.")
        conn.close()
        return

    # Add missing columns
    for column_def in columns_to_add:
        column_name = column_def.split()[0]
        print(f"Adding column: {column_name}")
        cursor.execute(f"ALTER TABLE tokens ADD COLUMN {column_def}")

    # Add indexes
    print("Creating indexes for Item type columns...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_rarity ON tokens(rarity)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON tokens(category)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_attunement ON tokens(attunement)')

    conn.commit()
    conn.close()

    print(f"Migration complete! Added {len(columns_to_add)} column(s) to {db_path}")

if __name__ == '__main__':
    migrate_database()
