"""
Tests for database module.
Tests TokenDatabase CRUD operations, querying, filtering, and statistics.
"""
import pytest
from datetime import datetime
from database import TokenDatabase, EMPTY_FIELD_SENTINEL


class TestDatabaseInitialization:
    """Tests for database initialization."""

    def test_in_memory_database(self):
        """Should create in-memory database without errors."""
        db = TokenDatabase(':memory:')
        assert db.db_path == ':memory:'
        # Database connections are closed via context managers, no explicit close needed

    def test_database_tables_created(self, test_db):
        """Should create tokens table with correct schema."""
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tokens'")
            result = cursor.fetchone()

        assert result is not None
        assert result['name'] == 'tokens'

    def test_database_indexes_created(self, test_db):
        """Should create indexes for faster filtering."""
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row['name'] for row in cursor.fetchall()]

        assert 'idx_image_type' in indexes
        assert 'idx_species' in indexes
        assert 'idx_class' in indexes
        assert 'idx_source' in indexes
        assert 'idx_campaign' in indexes
        assert 'idx_filename' in indexes

    def test_pdf_files_table_created(self, test_db):
        """Should create pdf_files table."""
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pdf_files'")
            result = cursor.fetchone()

        assert result is not None
        assert result['name'] == 'pdf_files'

    def test_pdf_files_indexes_created(self, test_db):
        """Should create indexes for pdf_files filtering."""
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
            indexes = [row['name'] for row in cursor.fetchall()]

        assert 'idx_pdf_image_type' in indexes
        assert 'idx_pdf_source' in indexes
        assert 'idx_pdf_campaign' in indexes
        assert 'idx_pdf_filename' in indexes
        assert 'idx_pdf_file_hash' in indexes
        assert 'idx_pdf_is_missing' in indexes


class TestAddToken:
    """Tests for add_token method."""

    def test_add_token_minimal_data(self, test_db):
        """Should add token with minimal required fields."""
        token_data = {
            'filepath': '/test/token.png',
            'filename': 'token.png',
            'ImageType': 'Token'
        }

        token_id = test_db.add_token(token_data)

        assert token_id is not None
        assert isinstance(token_id, int)
        assert token_id > 0

    def test_add_token_full_data(self, test_db, sample_token_data):
        """Should add token with all fields populated."""
        token_id = test_db.add_token(sample_token_data)

        assert token_id is not None

        # Verify data was saved
        retrieved = test_db.get_token(token_id)
        assert retrieved is not None
        assert retrieved['filepath'] == sample_token_data['filepath']
        assert retrieved['name'] == sample_token_data['Name']
        assert retrieved['species'] == sample_token_data['Species']

    def test_add_duplicate_filepath(self, test_db):
        """Should not allow duplicate filepaths (UNIQUE constraint)."""
        token_data = {
            'filepath': '/test/duplicate.png',
            'filename': 'duplicate.png',
            'ImageType': 'Token'
        }

        # Add first token
        token_id1 = test_db.add_token(token_data)
        assert token_id1 is not None

        # Try to add duplicate
        token_id2 = test_db.add_token(token_data)
        assert token_id2 is None  # Should fail due to UNIQUE constraint

    def test_add_token_default_image_type(self, test_db):
        """Should default to 'Token' image type if not specified."""
        token_data = {
            'filepath': '/test/token.png',
            'filename': 'token.png'
        }

        token_id = test_db.add_token(token_data)
        retrieved = test_db.get_token(token_id)

        assert retrieved['image_type'] == 'Token'


class TestGetToken:
    """Tests for get_token method."""

    def test_get_existing_token(self, test_db, sample_token_data):
        """Should retrieve token by ID."""
        token_id = test_db.add_token(sample_token_data)
        token = test_db.get_token(token_id)

        assert token is not None
        assert token['id'] == token_id
        assert token['filepath'] == sample_token_data['filepath']
        assert token['filename'] == sample_token_data['filename']

    def test_get_nonexistent_token(self, test_db):
        """Should return None for non-existent token ID."""
        token = test_db.get_token(99999)
        assert token is None

    def test_get_token_by_filepath(self, test_db, sample_token_data):
        """Should retrieve token by filepath."""
        test_db.add_token(sample_token_data)
        token = test_db.get_token_by_filepath(sample_token_data['filepath'])

        assert token is not None
        assert token['filepath'] == sample_token_data['filepath']

    def test_get_token_by_nonexistent_filepath(self, test_db):
        """Should return None for non-existent filepath."""
        token = test_db.get_token_by_filepath('/nonexistent/path.png')
        assert token is None


class TestUpdateToken:
    """Tests for update_token method."""

    def test_update_token_partial(self, test_db, sample_token_data):
        """Should update specified fields (note: current implementation sets unspecified fields to None)."""
        token_id = test_db.add_token(sample_token_data)

        update_data = {
            'Species': 'Goblin',
            'Class': 'Rogue'
        }

        success = test_db.update_token(token_id, update_data)
        assert success is True

        updated = test_db.get_token(token_id)
        assert updated['species'] == 'Goblin'
        assert updated['class'] == 'Rogue'
        # Note: update_token() sets all fields, so unspecified fields become None
        # This is current behavior, though it could be improved in the future

    def test_update_token_full(self, test_db, sample_token_data):
        """Should update all fields."""
        token_id = test_db.add_token(sample_token_data)

        update_data = {
            'Name': 'Updated Name',
            'Species': 'Dragon',
            'Class': 'Sorcerer',
            'Source': 'New Source',
            'Campaign': 'New Campaign',
            'Notes': 'Updated notes'
        }

        success = test_db.update_token(token_id, update_data)
        assert success is True

        updated = test_db.get_token(token_id)
        assert updated['name'] == 'Updated Name'
        assert updated['species'] == 'Dragon'
        assert updated['class'] == 'Sorcerer'

    def test_update_nonexistent_token(self, test_db):
        """Should return False when updating non-existent token."""
        success = test_db.update_token(99999, {'Species': 'Goblin'})
        assert success is False

    def test_update_token_by_filepath(self, test_db, sample_token_data):
        """Should update token by filepath."""
        test_db.add_token(sample_token_data)

        update_data = {'Species': 'Elf'}
        success = test_db.update_token_by_filepath(sample_token_data['filepath'], update_data)
        assert success is True

        updated = test_db.get_token_by_filepath(sample_token_data['filepath'])
        assert updated['species'] == 'Elf'


class TestDeleteToken:
    """Tests for delete_token method."""

    def test_delete_existing_token(self, test_db, sample_token_data):
        """Should delete token by ID."""
        token_id = test_db.add_token(sample_token_data)
        success = test_db.delete_token(token_id)

        assert success is True

        # Verify deletion
        token = test_db.get_token(token_id)
        assert token is None

    def test_delete_nonexistent_token(self, test_db):
        """Should return False when deleting non-existent token."""
        success = test_db.delete_token(99999)
        assert success is False

    def test_delete_token_by_filepath(self, test_db, sample_token_data):
        """Should delete token by filepath."""
        test_db.add_token(sample_token_data)
        success = test_db.delete_token_by_filepath(sample_token_data['filepath'])

        assert success is True

        # Verify deletion
        token = test_db.get_token_by_filepath(sample_token_data['filepath'])
        assert token is None


class TestGetAllTokens:
    """Tests for get_all_tokens method."""

    def test_get_all_tokens_empty(self, test_db):
        """Should return empty list when no tokens exist."""
        tokens = test_db.get_all_tokens()
        assert tokens == []

    def test_get_all_tokens_multiple(self, test_db):
        """Should return all tokens."""
        # Add multiple tokens
        for i in range(3):
            test_db.add_token({
                'filepath': f'/test/token{i}.png',
                'filename': f'token{i}.png',
                'ImageType': 'Token'
            })

        tokens = test_db.get_all_tokens()
        assert len(tokens) == 3

    def test_filter_by_image_type(self, test_db):
        """Should filter tokens by image type."""
        test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png',
            'ImageType': 'Token'
        })
        test_db.add_token({
            'filepath': '/test/map.png',
            'filename': 'map.png',
            'ImageType': 'Map'
        })

        tokens = test_db.get_all_tokens(filters={'image_type': 'Token'})
        assert len(tokens) == 1
        assert tokens[0]['image_type'] == 'Token'

    def test_filter_by_species(self, test_db):
        """Should filter tokens by species."""
        test_db.add_token({
            'filepath': '/test/orc.png',
            'filename': 'orc.png',
            'Species': 'Orc'
        })
        test_db.add_token({
            'filepath': '/test/elf.png',
            'filename': 'elf.png',
            'Species': 'Elf'
        })

        tokens = test_db.get_all_tokens(filters={'species': 'Orc'})
        assert len(tokens) == 1
        assert tokens[0]['species'] == 'Orc'

    def test_sort_by_filename_asc(self, test_db):
        """Should sort tokens by filename ascending."""
        test_db.add_token({'filepath': '/test/c.png', 'filename': 'c.png'})
        test_db.add_token({'filepath': '/test/a.png', 'filename': 'a.png'})
        test_db.add_token({'filepath': '/test/b.png', 'filename': 'b.png'})

        tokens = test_db.get_all_tokens(sort_by='filename', sort_order='ASC')

        assert tokens[0]['filename'] == 'a.png'
        assert tokens[1]['filename'] == 'b.png'
        assert tokens[2]['filename'] == 'c.png'

    def test_sort_by_filename_desc(self, test_db):
        """Should sort tokens by filename descending."""
        test_db.add_token({'filepath': '/test/a.png', 'filename': 'a.png'})
        test_db.add_token({'filepath': '/test/c.png', 'filename': 'c.png'})
        test_db.add_token({'filepath': '/test/b.png', 'filename': 'b.png'})

        tokens = test_db.get_all_tokens(sort_by='filename', sort_order='DESC')

        assert tokens[0]['filename'] == 'c.png'
        assert tokens[1]['filename'] == 'b.png'
        assert tokens[2]['filename'] == 'a.png'


class TestGetAllTokensWithMultiFiltersEmptySentinel:
    """Tests for the (Untagged) empty-field filter on get_all_tokens_with_multi_filters."""

    def _make_tokens(self, test_db):
        test_db.add_token({'filepath': '/test/a.png', 'filename': 'a.png', 'Species': 'Orc'})
        test_db.add_token({'filepath': '/test/b.png', 'filename': 'b.png'})  # no species
        test_db.add_token({'filepath': '/test/c.png', 'filename': 'c.png', 'Species': 'Elf'})

    def test_single_sentinel_matches_only_empty(self, test_db):
        """A bare sentinel value should match only tokens with no species set."""
        self._make_tokens(test_db)

        tokens = test_db.get_all_tokens_with_multi_filters(filters={'species': EMPTY_FIELD_SENTINEL})

        assert [t['filename'] for t in tokens] == ['b.png']

    def test_list_sentinel_matches_only_empty(self, test_db):
        """A single-item list sentinel should behave the same as the bare value."""
        self._make_tokens(test_db)

        tokens = test_db.get_all_tokens_with_multi_filters(filters={'species': [EMPTY_FIELD_SENTINEL]})

        assert [t['filename'] for t in tokens] == ['b.png']

    def test_sentinel_mixed_with_real_value(self, test_db):
        """Sentinel and a real value in the same OR list should match both."""
        self._make_tokens(test_db)

        tokens = test_db.get_all_tokens_with_multi_filters(
            filters={'species': [EMPTY_FIELD_SENTINEL, 'Orc']}
        )

        assert sorted(t['filename'] for t in tokens) == ['a.png', 'b.png']

    def test_normal_filtering_unaffected(self, test_db):
        """Filtering by a real value should be unaffected by the sentinel handling."""
        self._make_tokens(test_db)

        tokens = test_db.get_all_tokens_with_multi_filters(filters={'species': 'Elf'})

        assert [t['filename'] for t in tokens] == ['c.png']


class TestSearchTokens:
    """Tests for search_tokens method."""

    def test_search_by_name(self, test_db):
        """Should search tokens by name."""
        test_db.add_token({
            'filepath': '/test/goblin.png',
            'filename': 'goblin.png',
            'Name': 'Goblin Warrior'
        })
        test_db.add_token({
            'filepath': '/test/orc.png',
            'filename': 'orc.png',
            'Name': 'Orc Chieftain'
        })

        results = test_db.search_tokens('Goblin')
        assert len(results) == 1
        assert 'Goblin' in results[0]['name']

    def test_search_by_filename(self, test_db):
        """Should search tokens by filename."""
        test_db.add_token({
            'filepath': '/test/dragon_red.png',
            'filename': 'dragon_red.png'
        })

        results = test_db.search_tokens('dragon')
        assert len(results) == 1

    def test_search_case_insensitive(self, test_db):
        """Search should be case-insensitive."""
        test_db.add_token({
            'filepath': '/test/elf.png',
            'filename': 'elf.png',
            'Name': 'Elf Ranger'
        })

        results = test_db.search_tokens('ELF')
        assert len(results) == 1


class TestGetTagValues:
    """Tests for get_tag_values methods."""

    def test_get_species_values(self, test_db):
        """Should return unique species values."""
        test_db.add_token({'filepath': '/test/1.png', 'filename': '1.png', 'Species': 'Orc'})
        test_db.add_token({'filepath': '/test/2.png', 'filename': '2.png', 'Species': 'Elf'})
        test_db.add_token({'filepath': '/test/3.png', 'filename': '3.png', 'Species': 'Orc'})

        values = test_db.get_tag_values('species')
        assert len(values) == 2
        assert 'Orc' in values
        assert 'Elf' in values

    def test_get_tag_values_by_image_type(self, test_db):
        """Should filter tag values by image type."""
        test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png',
            'ImageType': 'Token',
            'Species': 'Orc'
        })
        test_db.add_token({
            'filepath': '/test/map.png',
            'filename': 'map.png',
            'ImageType': 'Map',
            'Scale': 'Large'
        })

        species_values = test_db.get_tag_values_by_type('Token', 'species')
        assert 'Orc' in species_values

        scale_values = test_db.get_tag_values_by_type('Map', 'scale')
        assert 'Large' in scale_values


class TestHashOperations:
    """Tests for hash-related operations."""

    def test_find_by_hash(self, test_db):
        """Should find token by file hash."""
        token_id = test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png'
        })

        test_hash = 'abc123def456'
        test_db.update_file_hash(token_id, test_hash)

        found = test_db.find_by_hash(test_hash)
        assert found is not None
        assert found['id'] == token_id

    def test_find_by_nonexistent_hash(self, test_db):
        """Should return None for non-existent hash."""
        found = test_db.find_by_hash('nonexistent_hash')
        assert found is None

    def test_update_file_hash(self, test_db):
        """Should update file hash for token."""
        token_id = test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png'
        })

        test_hash = 'new_hash_value'
        success = test_db.update_file_hash(token_id, test_hash)
        assert success is True

        found = test_db.find_by_hash(test_hash)
        assert found is not None


class TestFileTracking:
    """Tests for file tracking (missing files, verification)."""

    def test_mark_missing_true(self, test_db):
        """Should mark token as missing."""
        token_id = test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png'
        })

        success = test_db.mark_missing(token_id, True)
        assert success is True

        # Verify in missing files list
        missing = test_db.get_missing_files()
        assert len(missing) == 1
        assert missing[0]['id'] == token_id

    def test_mark_missing_false(self, test_db):
        """Should unmark token as missing."""
        token_id = test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png'
        })

        test_db.mark_missing(token_id, True)
        test_db.mark_missing(token_id, False)

        missing = test_db.get_missing_files()
        assert len(missing) == 0

    def test_update_last_verified(self, test_db):
        """Should update last verification timestamp."""
        token_id = test_db.add_token({
            'filepath': '/test/token.png',
            'filename': 'token.png'
        })

        success = test_db.update_last_verified(token_id)
        assert success is True

        token = test_db.get_token(token_id)
        assert token['last_verified'] is not None


class TestStatistics:
    """Tests for get_stats method."""

    def test_stats_empty_database(self, test_db):
        """Should return correct stats for empty database."""
        stats = test_db.get_stats()

        assert stats['total_tokens'] == 0
        assert stats['species'] == {}
        assert stats['classes'] == {}
        assert stats['sources'] == {}
        assert stats['campaigns'] == {}

    def test_stats_with_tokens(self, test_db):
        """Should calculate stats correctly."""
        # Add various tokens with different tags
        test_db.add_token({
            'filepath': '/test/1.png',
            'filename': '1.png',
            'ImageType': 'Token',
            'Species': 'Dragon',
            'Class': 'Fighter',
            'Source': 'Core'
        })
        test_db.add_token({
            'filepath': '/test/2.png',
            'filename': '2.png',
            'ImageType': 'Token',
            'Species': 'Dragon',
            'Source': 'Core'
        })
        test_db.add_token({
            'filepath': '/test/3.png',
            'filename': '3.png',
            'ImageType': 'Map',
            'Species': 'Goblin'
        })

        stats = test_db.get_stats()

        assert stats['total_tokens'] == 3
        assert stats['species']['Dragon'] == 2
        assert stats['species']['Goblin'] == 1
        assert stats['classes']['Fighter'] == 1
        assert stats['sources']['Core'] == 2


class TestFindByFilename:
    """Tests for find_by_filename method."""

    def test_find_by_filename(self, test_db):
        """Should find tokens with matching filename."""
        test_db.add_token({
            'filepath': '/path1/token.png',
            'filename': 'token.png'
        })
        test_db.add_token({
            'filepath': '/path2/token.png',
            'filename': 'token.png'
        })

        results = test_db.find_by_filename('token.png')
        assert len(results) == 2

    def test_find_by_nonexistent_filename(self, test_db):
        """Should return empty list for non-existent filename."""
        results = test_db.find_by_filename('nonexistent.png')
        assert results == []


class TestAddPdfFile:
    """Tests for add_pdf_file method."""

    def test_add_pdf_file_minimal_data(self, test_db):
        """Should add PDF with minimal required fields."""
        pdf_data = {
            'filepath': '/test/rules.pdf',
            'filename': 'rules.pdf'
        }

        pdf_id = test_db.add_pdf_file(pdf_data)

        assert pdf_id is not None
        assert isinstance(pdf_id, int)
        assert pdf_id > 0

    def test_add_pdf_file_full_data(self, test_db):
        """Should add PDF with all fields populated."""
        pdf_data = {
            'filepath': '/test/rules.pdf',
            'filename': 'rules.pdf',
            'Name': 'Player Handbook',
            'ImageType': 'Handout',
            'Source': 'Core Rules',
            'Campaign': 'Curse of Strahd',
            'Notes': 'Reference for spellcasting',
            'page_count': 320,
            'DateAdded': '2026-01-01T00:00:00',
            'file_modified': '2026-01-01T00:00:00',
            'file_hash': 'abc123'
        }

        pdf_id = test_db.add_pdf_file(pdf_data)
        retrieved = test_db.get_pdf_file(pdf_id)

        assert retrieved is not None
        assert retrieved['name'] == 'Player Handbook'
        assert retrieved['image_type'] == 'Handout'
        assert retrieved['source'] == 'Core Rules'
        assert retrieved['campaign'] == 'Curse of Strahd'
        assert retrieved['page_count'] == 320

    def test_add_duplicate_filepath(self, test_db):
        """Should not allow duplicate filepaths (UNIQUE constraint)."""
        pdf_data = {'filepath': '/test/duplicate.pdf', 'filename': 'duplicate.pdf'}

        pdf_id1 = test_db.add_pdf_file(pdf_data)
        assert pdf_id1 is not None

        pdf_id2 = test_db.add_pdf_file(pdf_data)
        assert pdf_id2 is None

    def test_add_pdf_file_default_image_type(self, test_db):
        """Should default to 'Handout' image type if not specified."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})
        retrieved = test_db.get_pdf_file(pdf_id)

        assert retrieved['image_type'] == 'Handout'


class TestGetPdfFile:
    """Tests for get_pdf_file methods."""

    def test_get_existing_pdf_file(self, test_db):
        """Should retrieve PDF by ID."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})
        pdf = test_db.get_pdf_file(pdf_id)

        assert pdf is not None
        assert pdf['id'] == pdf_id
        assert pdf['filepath'] == '/test/rules.pdf'

    def test_get_nonexistent_pdf_file(self, test_db):
        """Should return None for non-existent PDF ID."""
        assert test_db.get_pdf_file(99999) is None

    def test_get_pdf_file_by_filepath(self, test_db):
        """Should retrieve PDF by filepath."""
        test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})
        pdf = test_db.get_pdf_file_by_filepath('/test/rules.pdf')

        assert pdf is not None
        assert pdf['filepath'] == '/test/rules.pdf'

    def test_get_pdf_file_by_nonexistent_filepath(self, test_db):
        """Should return None for non-existent filepath."""
        assert test_db.get_pdf_file_by_filepath('/nonexistent/path.pdf') is None


class TestUpdatePdfFile:
    """Tests for update_pdf_file method."""

    def test_update_pdf_file(self, test_db):
        """Should update PDF fields."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})

        update_data = {
            'Name': 'Updated Name',
            'ImageType': 'Map',
            'Source': 'New Source',
            'Campaign': 'New Campaign',
            'Notes': 'Updated notes'
        }

        success = test_db.update_pdf_file(pdf_id, update_data)
        assert success is True

        updated = test_db.get_pdf_file(pdf_id)
        assert updated['name'] == 'Updated Name'
        assert updated['image_type'] == 'Map'
        assert updated['source'] == 'New Source'
        assert updated['campaign'] == 'New Campaign'
        assert updated['notes'] == 'Updated notes'

    def test_update_nonexistent_pdf_file(self, test_db):
        """Should return False when updating non-existent PDF."""
        success = test_db.update_pdf_file(99999, {'Name': 'Nope'})
        assert success is False


class TestDeletePdfFile:
    """Tests for delete_pdf_file method."""

    def test_delete_existing_pdf_file(self, test_db):
        """Should delete PDF by ID."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})
        success = test_db.delete_pdf_file(pdf_id)

        assert success is True
        assert test_db.get_pdf_file(pdf_id) is None

    def test_delete_nonexistent_pdf_file(self, test_db):
        """Should return False when deleting non-existent PDF."""
        success = test_db.delete_pdf_file(99999)
        assert success is False


class TestGetAllPdfFiles:
    """Tests for get_all_pdf_files method."""

    def test_get_all_pdf_files_empty(self, test_db):
        """Should return empty list when no PDFs exist."""
        assert test_db.get_all_pdf_files() == []

    def test_get_all_pdf_files_multiple(self, test_db):
        """Should return all PDFs."""
        for i in range(3):
            test_db.add_pdf_file({'filepath': f'/test/doc{i}.pdf', 'filename': f'doc{i}.pdf'})

        pdfs = test_db.get_all_pdf_files()
        assert len(pdfs) == 3

    def test_filter_by_image_type(self, test_db):
        """Should filter PDFs by image type."""
        test_db.add_pdf_file({'filepath': '/test/handout.pdf', 'filename': 'handout.pdf', 'ImageType': 'Handout'})
        test_db.add_pdf_file({'filepath': '/test/map.pdf', 'filename': 'map.pdf', 'ImageType': 'Map'})

        pdfs = test_db.get_all_pdf_files(filters={'image_type': 'Map'})
        assert len(pdfs) == 1
        assert pdfs[0]['image_type'] == 'Map'

    def test_filter_by_source(self, test_db):
        """Should filter PDFs by source."""
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf', 'Source': 'Core'})
        test_db.add_pdf_file({'filepath': '/test/b.pdf', 'filename': 'b.pdf', 'Source': 'Homebrew'})

        pdfs = test_db.get_all_pdf_files(filters={'source': 'Core'})
        assert len(pdfs) == 1
        assert pdfs[0]['source'] == 'Core'

    def test_sort_by_filename_asc(self, test_db):
        """Should sort PDFs by filename ascending."""
        test_db.add_pdf_file({'filepath': '/test/c.pdf', 'filename': 'c.pdf'})
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf'})
        test_db.add_pdf_file({'filepath': '/test/b.pdf', 'filename': 'b.pdf'})

        pdfs = test_db.get_all_pdf_files(sort_by='filename', sort_order='ASC')

        assert [p['filename'] for p in pdfs] == ['a.pdf', 'b.pdf', 'c.pdf']

    def test_sort_by_filename_desc(self, test_db):
        """Should sort PDFs by filename descending."""
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf'})
        test_db.add_pdf_file({'filepath': '/test/c.pdf', 'filename': 'c.pdf'})
        test_db.add_pdf_file({'filepath': '/test/b.pdf', 'filename': 'b.pdf'})

        pdfs = test_db.get_all_pdf_files(sort_by='filename', sort_order='DESC')

        assert [p['filename'] for p in pdfs] == ['c.pdf', 'b.pdf', 'a.pdf']

    def test_search_by_name(self, test_db):
        """Should search PDFs by name."""
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf', 'Name': 'Player Handbook'})
        test_db.add_pdf_file({'filepath': '/test/b.pdf', 'filename': 'b.pdf', 'Name': 'Monster Manual'})

        pdfs = test_db.get_all_pdf_files(search_term='Handbook')
        assert len(pdfs) == 1
        assert 'Handbook' in pdfs[0]['name']

    def test_search_case_insensitive(self, test_db):
        """Search should be case-insensitive."""
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf', 'Name': 'Player Handbook'})

        pdfs = test_db.get_all_pdf_files(search_term='HANDBOOK')
        assert len(pdfs) == 1

    def test_empty_sentinel_matches_only_missing_source(self, test_db):
        """The (Untagged) sentinel should match only PDFs with no source set."""
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf', 'Source': 'Core'})
        test_db.add_pdf_file({'filepath': '/test/b.pdf', 'filename': 'b.pdf'})  # no source

        pdfs = test_db.get_all_pdf_files(filters={'source': EMPTY_FIELD_SENTINEL})

        assert [p['filename'] for p in pdfs] == ['b.pdf']

    def test_normal_source_filtering_unaffected(self, test_db):
        """Filtering by a real source value should be unaffected by the sentinel handling."""
        test_db.add_pdf_file({'filepath': '/test/a.pdf', 'filename': 'a.pdf', 'Source': 'Core'})
        test_db.add_pdf_file({'filepath': '/test/b.pdf', 'filename': 'b.pdf'})  # no source

        pdfs = test_db.get_all_pdf_files(filters={'source': 'Core'})

        assert [p['filename'] for p in pdfs] == ['a.pdf']


class TestGetPdfTagValues:
    """Tests for get_pdf_tag_values method."""

    def test_get_source_values(self, test_db):
        """Should return unique source values."""
        test_db.add_pdf_file({'filepath': '/test/1.pdf', 'filename': '1.pdf', 'Source': 'Core'})
        test_db.add_pdf_file({'filepath': '/test/2.pdf', 'filename': '2.pdf', 'Source': 'Homebrew'})
        test_db.add_pdf_file({'filepath': '/test/3.pdf', 'filename': '3.pdf', 'Source': 'Core'})

        values = test_db.get_pdf_tag_values('source')
        assert len(values) == 2
        assert 'Core' in values
        assert 'Homebrew' in values

    def test_invalid_tag_type_returns_empty(self, test_db):
        """Should return empty list for an unrecognized tag field."""
        assert test_db.get_pdf_tag_values('not_a_real_field') == []


class TestPdfHashOperations:
    """Tests for PDF hash-related operations."""

    def test_find_pdf_by_hash(self, test_db):
        """Should find PDF by file hash."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})

        test_db.update_pdf_file_hash(pdf_id, 'abc123def456')

        found = test_db.find_pdf_by_hash('abc123def456')
        assert found is not None
        assert found['id'] == pdf_id

    def test_find_pdf_by_nonexistent_hash(self, test_db):
        """Should return None for non-existent hash."""
        assert test_db.find_pdf_by_hash('nonexistent_hash') is None


class TestPdfFileTracking:
    """Tests for PDF missing-file tracking."""

    def test_mark_pdf_missing_true(self, test_db):
        """Should mark PDF as missing."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})

        success = test_db.mark_pdf_missing(pdf_id, True)
        assert success is True

        pdf = test_db.get_pdf_file(pdf_id)
        assert pdf['is_missing'] == 1

    def test_mark_pdf_missing_false(self, test_db):
        """Should unmark PDF as missing."""
        pdf_id = test_db.add_pdf_file({'filepath': '/test/rules.pdf', 'filename': 'rules.pdf'})

        test_db.mark_pdf_missing(pdf_id, True)
        test_db.mark_pdf_missing(pdf_id, False)

        pdf = test_db.get_pdf_file(pdf_id)
        assert pdf['is_missing'] == 0


class TestPdfStatistics:
    """Tests for get_pdf_stats method."""

    def test_stats_empty_database(self, test_db):
        """Should return correct stats for empty database."""
        stats = test_db.get_pdf_stats()

        assert stats['total_pdf_files'] == 0
        assert stats['total_pages'] == 0
        assert stats['image_types'] == {}

    def test_stats_with_pdfs(self, test_db):
        """Should calculate stats correctly."""
        test_db.add_pdf_file({
            'filepath': '/test/1.pdf', 'filename': '1.pdf',
            'ImageType': 'Handout', 'page_count': 100
        })
        test_db.add_pdf_file({
            'filepath': '/test/2.pdf', 'filename': '2.pdf',
            'ImageType': 'Handout', 'page_count': 50
        })
        test_db.add_pdf_file({
            'filepath': '/test/3.pdf', 'filename': '3.pdf',
            'ImageType': 'Map', 'page_count': 1
        })

        stats = test_db.get_pdf_stats()

        assert stats['total_pdf_files'] == 3
        assert stats['total_pages'] == 151
        assert stats['image_types']['Handout'] == 2
        assert stats['image_types']['Map'] == 1
