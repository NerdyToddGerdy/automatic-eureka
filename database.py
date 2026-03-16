import sqlite3
from typing import Dict, List, Optional
from contextlib import contextmanager
import os


class TokenDatabase:
    """Handles SQLite database operations for token inventory."""

    def __init__(self, db_path: str = "tokens.db"):
        """
        Initialize the database connection.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.initialize_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def initialize_database(self):
        """Create the database schema if it doesn't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    name TEXT,
                    image_type TEXT DEFAULT 'Token',
                    species TEXT,
                    class TEXT,
                    source TEXT,
                    campaign TEXT,
                    notes TEXT,
                    date_added TEXT,
                    file_modified TEXT,
                    scale TEXT,
                    theme TEXT,
                    type TEXT,
                    subject TEXT,
                    style TEXT,
                    location TEXT,
                    mood TEXT,
                    rarity TEXT,
                    category TEXT,
                    attunement TEXT,
                    file_hash TEXT,
                    is_missing INTEGER DEFAULT 0,
                    last_verified TEXT
                )
            ''')

            # Create indexes for faster filtering
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_image_type ON tokens(image_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_species ON tokens(species)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_class ON tokens(class)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_source ON tokens(source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_campaign ON tokens(campaign)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_filename ON tokens(filename)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON tokens(file_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_is_missing ON tokens(is_missing)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_rarity ON tokens(rarity)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON tokens(category)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_attunement ON tokens(attunement)')

            # Composite indexes for common multi-field filter combinations
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_species  ON tokens(image_type, species)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_class    ON tokens(image_type, class)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_source   ON tokens(image_type, source)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_type_campaign ON tokens(image_type, campaign)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_date_added    ON tokens(date_added DESC)')

            # Run database migrations
            self._migrate_to_drive_support(cursor)

    def _migrate_to_drive_support(self, cursor):
        """Add Google Drive support columns if they don't exist."""
        # Check if drive_file_id column exists
        cursor.execute("PRAGMA table_info(tokens)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add Drive columns if they don't exist
        if 'drive_file_id' not in columns:
            print("Migrating database to support Google Drive...")

            cursor.execute('ALTER TABLE tokens ADD COLUMN drive_file_id TEXT')
            cursor.execute('ALTER TABLE tokens ADD COLUMN drive_folder_id TEXT')
            cursor.execute('ALTER TABLE tokens ADD COLUMN drive_web_view_link TEXT')
            cursor.execute('ALTER TABLE tokens ADD COLUMN drive_thumbnail_link TEXT')
            cursor.execute('ALTER TABLE tokens ADD COLUMN last_synced_from_drive TEXT')

            # Create indexes for Drive IDs
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_drive_file_id ON tokens(drive_file_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_drive_folder_id ON tokens(drive_folder_id)')

            print("Drive columns added successfully!")

        # Create monitored_folders table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS monitored_folders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_folder_id TEXT UNIQUE NOT NULL,
                folder_name TEXT NOT NULL,
                folder_path TEXT,
                date_added TEXT,
                is_active INTEGER DEFAULT 1
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_monitored_drive_folder_id ON monitored_folders(drive_folder_id)')

            # Create audio_files table for audio management
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audio_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filepath TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL,
                name TEXT,
                audio_type TEXT DEFAULT 'Music',
                genre TEXT,
                mood TEXT,
                intensity TEXT,
                character TEXT,
                location TEXT,
                source TEXT,
                campaign TEXT,
                notes TEXT,
                duration_seconds REAL,
                format TEXT,
                file_size INTEGER,
                date_added TEXT,
                file_modified TEXT,
                file_hash TEXT,
                is_missing INTEGER DEFAULT 0,
                last_verified TEXT
            )
        ''')

        # Create indexes for audio_files
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_type ON audio_files(audio_type)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_genre ON audio_files(genre)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_mood ON audio_files(mood)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_source ON audio_files(source)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_campaign ON audio_files(campaign)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_filename ON audio_files(filename)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_file_hash ON audio_files(file_hash)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_audio_is_missing ON audio_files(is_missing)')

    def add_token(self, token_data: Dict) -> Optional[int]:
        """
        Add a new token to the database.

        Args:
            token_data: Dictionary containing token information

        Returns:
            Token ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO tokens (
                        filepath, filename, name, image_type, species, class, source,
                        campaign, notes, date_added, file_modified,
                        scale, theme, type, subject, style, location, mood,
                        rarity, category, attunement,
                        drive_file_id, drive_folder_id, drive_web_view_link,
                        drive_thumbnail_link, last_synced_from_drive
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    token_data.get('filepath'),
                    token_data.get('filename'),
                    token_data.get('Name'),
                    token_data.get('ImageType', 'Token'),
                    token_data.get('Species'),
                    token_data.get('Class'),
                    token_data.get('Source'),
                    token_data.get('Campaign'),
                    token_data.get('Notes'),
                    token_data.get('DateAdded'),
                    token_data.get('file_modified'),
                    token_data.get('Scale'),
                    token_data.get('Theme'),
                    token_data.get('Type'),
                    token_data.get('Subject'),
                    token_data.get('Style'),
                    token_data.get('Location'),
                    token_data.get('Mood'),
                    token_data.get('Rarity'),
                    token_data.get('Category'),
                    token_data.get('Attunement'),
                    token_data.get('drive_file_id'),
                    token_data.get('drive_folder_id'),
                    token_data.get('drive_web_view_link'),
                    token_data.get('drive_thumbnail_link'),
                    token_data.get('last_synced_from_drive')
                ))

                return cursor.lastrowid

        except sqlite3.IntegrityError:
            # Token already exists
            return None
        except Exception as e:
            print(f"Error adding token to database: {e}")
            return None

    def update_token(self, token_id: int, token_data: Dict) -> bool:
        """
        Update an existing token.

        Args:
            token_id: ID of the token to update
            token_data: Dictionary containing updated token information

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE tokens SET
                        name = ?, image_type = ?, species = ?, class = ?, source = ?,
                        campaign = ?, notes = ?, file_modified = ?,
                        scale = ?, theme = ?, type = ?, subject = ?, style = ?, location = ?, mood = ?,
                        rarity = ?, category = ?, attunement = ?,
                        drive_file_id = ?, drive_folder_id = ?, drive_web_view_link = ?,
                        drive_thumbnail_link = ?, last_synced_from_drive = ?
                    WHERE id = ?
                ''', (
                    token_data.get('Name'),
                    token_data.get('ImageType', 'Token'),
                    token_data.get('Species'),
                    token_data.get('Class'),
                    token_data.get('Source'),
                    token_data.get('Campaign'),
                    token_data.get('Notes'),
                    token_data.get('file_modified'),
                    token_data.get('Scale'),
                    token_data.get('Theme'),
                    token_data.get('Type'),
                    token_data.get('Subject'),
                    token_data.get('Style'),
                    token_data.get('Location'),
                    token_data.get('Mood'),
                    token_data.get('Rarity'),
                    token_data.get('Category'),
                    token_data.get('Attunement'),
                    token_data.get('drive_file_id'),
                    token_data.get('drive_folder_id'),
                    token_data.get('drive_web_view_link'),
                    token_data.get('drive_thumbnail_link'),
                    token_data.get('last_synced_from_drive'),
                    token_id
                ))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating token: {e}")
            return False

    def update_token_by_filepath(self, filepath: str, token_data: Dict) -> bool:
        """
        Update a token by its filepath.

        Args:
            filepath: Path to the token file
            token_data: Dictionary containing updated token information

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE tokens SET
                        name = ?, image_type = ?, species = ?, class = ?, source = ?,
                        campaign = ?, notes = ?, file_modified = ?,
                        scale = ?, theme = ?, type = ?, subject = ?, style = ?, location = ?, mood = ?,
                        rarity = ?, category = ?, attunement = ?
                    WHERE filepath = ?
                ''', (
                    token_data.get('Name'),
                    token_data.get('ImageType', 'Token'),
                    token_data.get('Species'),
                    token_data.get('Class'),
                    token_data.get('Source'),
                    token_data.get('Campaign'),
                    token_data.get('Notes'),
                    token_data.get('file_modified'),
                    token_data.get('Scale'),
                    token_data.get('Theme'),
                    token_data.get('Type'),
                    token_data.get('Subject'),
                    token_data.get('Style'),
                    token_data.get('Location'),
                    token_data.get('Mood'),
                    token_data.get('Rarity'),
                    token_data.get('Category'),
                    token_data.get('Attunement'),
                    filepath
                ))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating token by filepath: {e}")
            return False

    def delete_token(self, token_id: int) -> bool:
        """Delete a token from the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tokens WHERE id = ?', (token_id,))
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting token: {e}")
            return False

    def delete_token_by_filepath(self, filepath: str) -> bool:
        """Delete a token by its filepath."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM tokens WHERE filepath = ?', (filepath,))
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting token by filepath: {e}")
            return False

    def get_token(self, token_id: int) -> Optional[Dict]:
        """Get a single token by ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tokens WHERE id = ?', (token_id,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"Error getting token: {e}")
            return None

    def get_token_by_filepath(self, filepath: str) -> Optional[Dict]:
        """Get a single token by filepath."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tokens WHERE filepath = ?', (filepath,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"Error getting token by filepath: {e}")
            return None

    def get_all_tokens(self, filters: Optional[Dict] = None, sort_by: str = 'filename',
                       sort_order: str = 'ASC') -> List[Dict]:
        """
        Get all tokens with optional filtering and sorting.

        Args:
            filters: Dictionary of field:value pairs to filter by
            sort_by: Field to sort by
            sort_order: 'ASC' or 'DESC'

        Returns:
            List of token dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = 'SELECT * FROM tokens WHERE 1=1'
                params = []

                # Add filters
                if filters:
                    for field, value in filters.items():
                        if value:
                            query += f' AND {field} = ?'
                            params.append(value)

                # Add sorting
                valid_sort_fields = ['id', 'filename', 'name', 'image_type', 'species', 'class',
                                     'source', 'campaign', 'date_added']
                if sort_by in valid_sort_fields:
                    query += f' ORDER BY {sort_by} {sort_order}'

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting all tokens: {e}")
            return []

    def get_all_tokens_with_multi_filters(self, filters: Optional[Dict] = None,
                                          sort_by: str = 'filename',
                                          sort_order: str = 'ASC',
                                          search_term: Optional[str] = None) -> List[Dict]:
        """
        Get all tokens with multi-value filter support and optional search.

        Args:
            filters: Dictionary where values can be lists for OR filtering within category
            sort_by: Field to sort by
            sort_order: 'ASC' or 'DESC'
            search_term: Optional search term to match against filename, name, notes, and tags

        Returns:
            List of token dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = 'SELECT * FROM tokens WHERE 1=1'
                params = []

                # Add search conditions
                if search_term:
                    search_pattern = f'%{search_term}%'
                    # Search in filename, name, notes, and all tag fields
                    query += ''' AND (
                        filename LIKE ? OR
                        name LIKE ? OR
                        notes LIKE ? OR
                        species LIKE ? OR
                        class LIKE ? OR
                        theme LIKE ? OR
                        source LIKE ? OR
                        campaign LIKE ?
                    )'''
                    # Add the search pattern for each field
                    params.extend([search_pattern] * 8)

                # Add filter conditions
                if filters:
                    for field, value in filters.items():
                        if value:
                            if isinstance(value, list):
                                # Multi-value filter: match if ANY value matches (OR logic)
                                placeholders = ' OR '.join([f'{field} = ?' for _ in value])
                                query += f' AND ({placeholders})'
                                params.extend(value)
                            else:
                                # Single value filter
                                query += f' AND {field} = ?'
                                params.append(value)

                # Add sorting
                valid_sort_fields = ['id', 'filename', 'name', 'image_type', 'species', 'class',
                                     'theme', 'source', 'campaign', 'date_added']
                if sort_by in valid_sort_fields:
                    query += f' ORDER BY {sort_by} {sort_order}'

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting tokens with multi-filters: {e}")
            return []

    def search_tokens(self, search_term: str) -> List[Dict]:
        """
        Search tokens by name or filename.

        Args:
            search_term: Search term to match against

        Returns:
            List of matching token dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT * FROM tokens
                    WHERE filename LIKE ? OR name LIKE ? OR notes LIKE ?
                    ORDER BY filename
                ''', (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error searching tokens: {e}")
            return []

    def _dedupe_case_insensitive(self, values: List[str]) -> List[str]:
        """
        Deduplicate values in a case-insensitive way, preserving the first-seen casing.

        Args:
            values: List of string values

        Returns:
            Deduplicated list with first-seen casing preserved
        """
        seen = {}
        for value in values:
            lower = value.lower()
            if lower not in seen:
                seen[lower] = value
        return sorted(seen.values(), key=str.lower)

    def get_tag_values(self, tag_type: str) -> List[str]:
        """
        Get all unique values for a specific tag type.

        Args:
            tag_type: The tag field (species, class, source, campaign)

        Returns:
            List of unique values (case-insensitive deduplicated)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                valid_tags = ['species', 'class', 'source', 'campaign', 'rarity', 'category', 'attunement']
                if tag_type not in valid_tags:
                    return []

                cursor.execute(f'''
                    SELECT DISTINCT {tag_type} FROM tokens
                    WHERE {tag_type} IS NOT NULL AND {tag_type} != ''
                    ORDER BY {tag_type}
                ''')

                rows = cursor.fetchall()
                values = [row[0] for row in rows]
                return self._dedupe_case_insensitive(values)

        except Exception as e:
            print(f"Error getting tag values: {e}")
            return []

    def get_tag_values_by_type(self, image_type: str, tag_type: str) -> List[str]:
        """
        Get all unique values for a specific tag type filtered by image type.

        Args:
            image_type: The image type to filter by
            tag_type: The tag field (species, class, source, campaign, etc.)

        Returns:
            List of unique values (case-insensitive deduplicated)
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                valid_tags = ['species', 'class', 'source', 'campaign', 'scale', 'theme',
                             'type', 'subject', 'style', 'location', 'mood', 'rarity', 'category', 'attunement']
                if tag_type.lower() not in valid_tags:
                    return []

                cursor.execute(f'''
                    SELECT DISTINCT {tag_type} FROM tokens
                    WHERE image_type = ? AND {tag_type} IS NOT NULL AND {tag_type} != ''
                    ORDER BY {tag_type}
                ''', (image_type,))

                rows = cursor.fetchall()

                # Split multi-value fields (like Theme for Maps)
                if tag_type == 'theme' and image_type == 'Map':
                    all_values = set()
                    for row in rows:
                        # Split comma-separated themes
                        all_values.update(self.parse_multivalue_field(row[0]))
                    return self._dedupe_case_insensitive(list(all_values))

                values = [row[0] for row in rows]
                return self._dedupe_case_insensitive(values)

        except Exception as e:
            print(f"Error getting tag values by type: {e}")
            return []

    def parse_multivalue_field(self, value):
        """Parse comma-separated values into a list."""
        if not value:
            return []
        if isinstance(value, list):
            return value
        return [v.strip() for v in str(value).split(',') if v.strip()]

    def format_multivalue_field(self, values):
        """Format list of values into comma-separated string."""
        if not values:
            return ''
        if isinstance(values, str):
            return values
        return ', '.join(str(v).strip() for v in values if v)

    def get_stats(self) -> Dict:
        """Get database statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM tokens')
                total = cursor.fetchone()[0]

                stats = {
                    'total_tokens': total,
                    'species': {},
                    'classes': {},
                    'sources': {},
                    'campaigns': {}
                }

                # Get counts by tag type
                for tag, key in [('species', 'species'), ('class', 'classes'),
                                 ('source', 'sources'), ('campaign', 'campaigns')]:
                    cursor.execute(f'''
                        SELECT {tag}, COUNT(*) as count
                        FROM tokens
                        WHERE {tag} IS NOT NULL AND {tag} != ''
                        GROUP BY {tag}
                        ORDER BY count DESC
                    ''')
                    rows = cursor.fetchall()
                    stats[key] = {row[0]: row[1] for row in rows}

                return stats

        except Exception as e:
            print(f"Error getting stats: {e}")
            return {}

    def find_by_hash(self, file_hash: str) -> Optional[Dict]:
        """
        Find a token by its file hash.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            Token dictionary if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tokens WHERE file_hash = ?', (file_hash,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"Error finding token by hash: {e}")
            return None

    def find_by_filename(self, filename: str) -> List[Dict]:
        """
        Find all tokens with the given filename.

        Args:
            filename: Base filename (not full path)

        Returns:
            List of token dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tokens WHERE filename = ?', (filename,))
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error finding tokens by filename: {e}")
            return []

    def mark_missing(self, token_id: int, is_missing: bool) -> bool:
        """
        Update the is_missing flag for a token.

        Args:
            token_id: ID of the token
            is_missing: True if file is missing, False if found

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE tokens SET is_missing = ? WHERE id = ?',
                    (1 if is_missing else 0, token_id)
                )
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error marking token as missing: {e}")
            return False

    def update_last_verified(self, token_id: int, timestamp: str = None) -> bool:
        """
        Update the last_verified timestamp for a token.

        Args:
            token_id: ID of the token
            timestamp: ISO format timestamp (defaults to now)

        Returns:
            True if successful, False otherwise
        """
        try:
            if timestamp is None:
                from datetime import datetime
                timestamp = datetime.now().isoformat()

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE tokens SET last_verified = ? WHERE id = ?',
                    (timestamp, token_id)
                )
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating last_verified: {e}")
            return False

    def get_missing_files(self) -> List[Dict]:
        """
        Get all tokens marked as missing.

        Returns:
            List of token dictionaries where is_missing = True
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tokens WHERE is_missing = 1')
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting missing files: {e}")
            return []

    def update_file_hash(self, token_id: int, file_hash: str) -> bool:
        """
        Update the file hash for a token.

        Args:
            token_id: ID of the token
            file_hash: SHA-256 hash of the file

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE tokens SET file_hash = ? WHERE id = ?',
                    (file_hash, token_id)
                )
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating file hash: {e}")
            return False

    # ===== GOOGLE DRIVE METHODS =====

    def get_token_by_drive_id(self, drive_file_id: str) -> Optional[Dict]:
        """
        Get a token by its Google Drive file ID.

        Args:
            drive_file_id: The Google Drive file ID

        Returns:
            Token dictionary if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM tokens WHERE drive_file_id = ?', (drive_file_id,))
                row = cursor.fetchone()

                return dict(row) if row else None

        except Exception as e:
            print(f"Error getting token by Drive ID: {e}")
            return None

    def update_drive_metadata(self, token_id: int, drive_data: Dict) -> bool:
        """
        Update Google Drive-specific metadata for a token.

        Args:
            token_id: ID of the token to update
            drive_data: Dictionary containing Drive metadata
                       (drive_file_id, drive_folder_id, drive_web_view_link,
                        drive_thumbnail_link, last_synced_from_drive)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Build update query dynamically based on provided fields
                update_fields = []
                values = []

                if 'drive_file_id' in drive_data:
                    update_fields.append('drive_file_id = ?')
                    values.append(drive_data['drive_file_id'])

                if 'drive_folder_id' in drive_data:
                    update_fields.append('drive_folder_id = ?')
                    values.append(drive_data['drive_folder_id'])

                if 'drive_web_view_link' in drive_data:
                    update_fields.append('drive_web_view_link = ?')
                    values.append(drive_data['drive_web_view_link'])

                if 'drive_thumbnail_link' in drive_data:
                    update_fields.append('drive_thumbnail_link = ?')
                    values.append(drive_data['drive_thumbnail_link'])

                if 'last_synced_from_drive' in drive_data:
                    update_fields.append('last_synced_from_drive = ?')
                    values.append(drive_data['last_synced_from_drive'])

                if not update_fields:
                    return False

                values.append(token_id)
                query = f"UPDATE tokens SET {', '.join(update_fields)} WHERE id = ?"

                cursor.execute(query, values)
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating Drive metadata: {e}")
            return False

    # ===== MONITORED FOLDERS METHODS =====

    def add_monitored_folder(self, folder_id: str, folder_name: str, folder_path: str = None) -> Optional[int]:
        """
        Add a folder to the monitored folders list.

        Args:
            folder_id: Google Drive folder ID
            folder_name: Display name of the folder
            folder_path: Optional path/breadcrumb for the folder

        Returns:
            Folder record ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                from datetime import datetime
                date_added = datetime.now().isoformat()

                cursor.execute('''
                    INSERT INTO monitored_folders (drive_folder_id, folder_name, folder_path, date_added, is_active)
                    VALUES (?, ?, ?, ?, 1)
                ''', (folder_id, folder_name, folder_path, date_added))

                return cursor.lastrowid

        except sqlite3.IntegrityError:
            # Folder already being monitored
            print(f"Folder {folder_name} is already being monitored")
            return None
        except Exception as e:
            print(f"Error adding monitored folder: {e}")
            return None

    def remove_monitored_folder(self, folder_id: str) -> bool:
        """
        Remove a folder from the monitored folders list.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM monitored_folders WHERE drive_folder_id = ?', (folder_id,))
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error removing monitored folder: {e}")
            return False

    def get_all_monitored_folders(self) -> List[Dict]:
        """
        Get all monitored folders.

        Returns:
            List of monitored folder dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM monitored_folders WHERE is_active = 1 ORDER BY folder_name')
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting monitored folders: {e}")
            return []

    def is_folder_monitored(self, folder_id: str) -> bool:
        """
        Check if a folder is being monitored.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            True if folder is monitored, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM monitored_folders WHERE drive_folder_id = ? AND is_active = 1',
                    (folder_id,)
                )
                count = cursor.fetchone()[0]
                return count > 0

        except Exception as e:
            print(f"Error checking if folder is monitored: {e}")
            return False

    def get_monitored_folder_by_id(self, folder_id: str) -> Optional[Dict]:
        """
        Get a monitored folder by its Drive folder ID.

        Args:
            folder_id: Google Drive folder ID

        Returns:
            Monitored folder dictionary if found, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM monitored_folders WHERE drive_folder_id = ?', (folder_id,))
                row = cursor.fetchone()

                return dict(row) if row else None

        except Exception as e:
            print(f"Error getting monitored folder: {e}")
            return None

    # ===== AUDIO FILE METHODS =====

    def add_audio_file(self, audio_data: Dict) -> Optional[int]:
        """
        Add a new audio file to the database.

        Args:
            audio_data: Dictionary containing audio file information

        Returns:
            Audio file ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO audio_files (
                        filepath, filename, name, audio_type, genre, mood, intensity,
                        character, location, source, campaign, notes, duration_seconds,
                        format, file_size, date_added, file_modified, file_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    audio_data.get('filepath'),
                    audio_data.get('filename'),
                    audio_data.get('Name'),
                    audio_data.get('AudioType', 'Music'),
                    audio_data.get('Genre'),
                    audio_data.get('Mood'),
                    audio_data.get('Intensity'),
                    audio_data.get('Character'),
                    audio_data.get('Location'),
                    audio_data.get('Source'),
                    audio_data.get('Campaign'),
                    audio_data.get('Notes'),
                    audio_data.get('duration_seconds'),
                    audio_data.get('format'),
                    audio_data.get('file_size'),
                    audio_data.get('DateAdded'),
                    audio_data.get('file_modified'),
                    audio_data.get('file_hash')
                ))

                return cursor.lastrowid

        except sqlite3.IntegrityError:
            # Audio file already exists
            return None
        except Exception as e:
            print(f"Error adding audio file to database: {e}")
            return None

    def update_audio_file(self, audio_id: int, audio_data: Dict) -> bool:
        """
        Update an existing audio file.

        Args:
            audio_id: ID of the audio file to update
            audio_data: Dictionary containing updated audio file information

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    UPDATE audio_files SET
                        name = ?, audio_type = ?, genre = ?, mood = ?, intensity = ?,
                        character = ?, location = ?, source = ?, campaign = ?, notes = ?,
                        file_modified = ?
                    WHERE id = ?
                ''', (
                    audio_data.get('Name'),
                    audio_data.get('AudioType', 'Music'),
                    audio_data.get('Genre'),
                    audio_data.get('Mood'),
                    audio_data.get('Intensity'),
                    audio_data.get('Character'),
                    audio_data.get('Location'),
                    audio_data.get('Source'),
                    audio_data.get('Campaign'),
                    audio_data.get('Notes'),
                    audio_data.get('file_modified'),
                    audio_id
                ))

                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating audio file: {e}")
            return False

    def delete_audio_file(self, audio_id: int) -> bool:
        """Delete an audio file from the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM audio_files WHERE id = ?', (audio_id,))
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error deleting audio file: {e}")
            return False

    def get_audio_file(self, audio_id: int) -> Optional[Dict]:
        """Get a single audio file by ID."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM audio_files WHERE id = ?', (audio_id,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"Error getting audio file: {e}")
            return None

    def get_audio_file_by_filepath(self, filepath: str) -> Optional[Dict]:
        """Get a single audio file by filepath."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM audio_files WHERE filepath = ?', (filepath,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"Error getting audio file by filepath: {e}")
            return None

    def get_all_audio_files(self, filters: Optional[Dict] = None, sort_by: str = 'filename',
                           sort_order: str = 'ASC', search_term: Optional[str] = None) -> List[Dict]:
        """
        Get all audio files with optional filtering and sorting.

        Args:
            filters: Dictionary of field:value pairs to filter by
            sort_by: Field to sort by
            sort_order: 'ASC' or 'DESC'
            search_term: Optional search term to match against filename, name, notes

        Returns:
            List of audio file dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                query = 'SELECT * FROM audio_files WHERE 1=1'
                params = []

                # Add search conditions
                if search_term:
                    search_pattern = f'%{search_term}%'
                    query += ''' AND (
                        filename LIKE ? OR
                        name LIKE ? OR
                        notes LIKE ? OR
                        genre LIKE ? OR
                        mood LIKE ? OR
                        source LIKE ? OR
                        campaign LIKE ?
                    )'''
                    params.extend([search_pattern] * 7)

                # Add filter conditions
                if filters:
                    for field, value in filters.items():
                        if value:
                            if isinstance(value, list):
                                placeholders = ' OR '.join([f'{field} = ?' for _ in value])
                                query += f' AND ({placeholders})'
                                params.extend(value)
                            else:
                                query += f' AND {field} = ?'
                                params.append(value)

                # Add sorting
                valid_sort_fields = ['id', 'filename', 'name', 'audio_type', 'genre', 'mood',
                                     'source', 'campaign', 'date_added', 'duration_seconds']
                if sort_by in valid_sort_fields:
                    query += f' ORDER BY {sort_by} {sort_order}'

                cursor.execute(query, params)
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting all audio files: {e}")
            return []

    def get_audio_tag_values(self, tag_type: str) -> List[str]:
        """
        Get all unique values for a specific audio tag type.

        Args:
            tag_type: The tag field (genre, mood, intensity, character, location, source, campaign)

        Returns:
            List of unique values
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                valid_tags = ['genre', 'mood', 'intensity', 'character', 'location', 'source', 'campaign']
                if tag_type not in valid_tags:
                    return []

                cursor.execute(f'''
                    SELECT DISTINCT {tag_type} FROM audio_files
                    WHERE {tag_type} IS NOT NULL AND {tag_type} != ''
                    ORDER BY {tag_type}
                ''')

                rows = cursor.fetchall()
                return [row[0] for row in rows]

        except Exception as e:
            print(f"Error getting audio tag values: {e}")
            return []

    def get_audio_tag_values_by_type(self, audio_type: str, tag_type: str) -> List[str]:
        """
        Get all unique values for a specific audio tag type filtered by audio type.

        Args:
            audio_type: The audio type to filter by (Music, SoundEffect, Ambience, Dialogue)
            tag_type: The tag field (genre, mood, intensity, character, location, source, campaign)

        Returns:
            List of unique values
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                valid_tags = ['genre', 'mood', 'intensity', 'character', 'location', 'source', 'campaign']
                if tag_type.lower() not in valid_tags:
                    return []

                cursor.execute(f'''
                    SELECT DISTINCT {tag_type} FROM audio_files
                    WHERE audio_type = ? AND {tag_type} IS NOT NULL AND {tag_type} != ''
                    ORDER BY {tag_type}
                ''', (audio_type,))

                rows = cursor.fetchall()
                return [row[0] for row in rows]

        except Exception as e:
            print(f"Error getting audio tag values by type: {e}")
            return []

    def find_audio_by_hash(self, file_hash: str) -> Optional[Dict]:
        """Find an audio file by its file hash."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM audio_files WHERE file_hash = ?', (file_hash,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            print(f"Error finding audio file by hash: {e}")
            return None

    def mark_audio_missing(self, audio_id: int, is_missing: bool) -> bool:
        """Update the is_missing flag for an audio file."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE audio_files SET is_missing = ? WHERE id = ?',
                    (1 if is_missing else 0, audio_id)
                )
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error marking audio file as missing: {e}")
            return False

    def update_audio_file_hash(self, audio_id: int, file_hash: str) -> bool:
        """Update the file hash for an audio file."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE audio_files SET file_hash = ? WHERE id = ?',
                    (file_hash, audio_id)
                )
                return cursor.rowcount > 0

        except Exception as e:
            print(f"Error updating audio file hash: {e}")
            return False

    def get_audio_stats(self) -> Dict:
        """Get audio file statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute('SELECT COUNT(*) FROM audio_files')
                total = cursor.fetchone()[0]

                cursor.execute('SELECT SUM(duration_seconds) FROM audio_files WHERE duration_seconds IS NOT NULL')
                total_duration = cursor.fetchone()[0] or 0

                stats = {
                    'total_audio_files': total,
                    'total_duration_seconds': total_duration,
                    'audio_types': {},
                    'genres': {},
                    'moods': {}
                }

                # Get counts by audio type
                cursor.execute('''
                    SELECT audio_type, COUNT(*) as count
                    FROM audio_files
                    WHERE audio_type IS NOT NULL AND audio_type != ''
                    GROUP BY audio_type
                    ORDER BY count DESC
                ''')
                stats['audio_types'] = {row[0]: row[1] for row in cursor.fetchall()}

                # Get counts by genre
                cursor.execute('''
                    SELECT genre, COUNT(*) as count
                    FROM audio_files
                    WHERE genre IS NOT NULL AND genre != ''
                    GROUP BY genre
                    ORDER BY count DESC
                ''')
                stats['genres'] = {row[0]: row[1] for row in cursor.fetchall()}

                return stats

        except Exception as e:
            print(f"Error getting audio stats: {e}")
            return {}
