"""
Unit tests for scanner.py (TokenScanner, TokenFolderEventHandler, TokenFolderWatcher).
"""
import hashlib
import os
import time
from datetime import datetime

import pytest
from PIL import Image

from file_utils import FileOpTimeout
from metadata import TokenMetadata
from scanner import (
    TokenScanner,
    TokenFolderEventHandler,
    TokenFolderWatcher,
    is_supported_audio,
    get_audio_metadata,
    is_supported_pdf,
    get_pdf_page_count,
)


@pytest.fixture
def scanner(test_db, temp_dir):
    return TokenScanner(test_db, temp_dir)


def make_png(path, color='red'):
    img = Image.new('RGB', (10, 10), color=color)
    img.save(path, 'PNG')


def make_audio_file(path, content=b'not real audio data'):
    with open(path, 'wb') as f:
        f.write(content)


def make_pdf_file(path, content=b'%PDF-1.4 not a real pdf'):
    with open(path, 'wb') as f:
        f.write(content)


def make_real_pdf(path, page_count=2):
    import fitz
    doc = fitz.open()
    for _ in range(page_count):
        doc.new_page()
    doc.save(path)
    doc.close()


class TestIsSupportedAudio:
    @pytest.mark.parametrize('ext', ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.MP3', '.Wav'])
    def test_supported_extensions(self, ext):
        assert is_supported_audio(f'song{ext}') is True

    @pytest.mark.parametrize('ext', ['.png', '.jpg', '.txt', ''])
    def test_unsupported_extensions(self, ext):
        assert is_supported_audio(f'file{ext}') is False


class TestGetAudioMetadata:
    def test_returns_none_for_unparseable_file(self, temp_dir):
        filepath = os.path.join(temp_dir, 'bad.mp3')
        make_audio_file(filepath)
        assert get_audio_metadata(filepath) is None

    def test_returns_none_for_missing_file(self, temp_dir):
        assert get_audio_metadata(os.path.join(temp_dir, 'missing.mp3')) is None


class TestIsSupportedPdf:
    @pytest.mark.parametrize('ext', ['.pdf', '.PDF'])
    def test_supported_extensions(self, ext):
        assert is_supported_pdf(f'book{ext}') is True

    @pytest.mark.parametrize('ext', ['.png', '.mp3', '.txt', ''])
    def test_unsupported_extensions(self, ext):
        assert is_supported_pdf(f'file{ext}') is False


class TestGetPdfPageCount:
    def test_returns_none_for_unparseable_file(self, temp_dir):
        filepath = os.path.join(temp_dir, 'bad.pdf')
        make_pdf_file(filepath)
        assert get_pdf_page_count(filepath) is None

    def test_returns_none_for_missing_file(self, temp_dir):
        assert get_pdf_page_count(os.path.join(temp_dir, 'missing.pdf')) is None

    def test_returns_count_for_real_pdf(self, temp_dir):
        filepath = os.path.join(temp_dir, 'real.pdf')
        make_real_pdf(filepath, page_count=3)
        assert get_pdf_page_count(filepath) == 3


class TestFindImageFiles:
    def test_no_token_folder_returns_empty(self, test_db):
        scanner = TokenScanner(test_db, token_folder=None)
        assert scanner.find_image_files() == []

    def test_finds_nested_images_ignores_other_extensions(self, scanner, temp_dir):
        sub = os.path.join(temp_dir, 'sub')
        os.makedirs(sub)
        make_png(os.path.join(temp_dir, 'a.png'))
        make_png(os.path.join(sub, 'b.PNG'))
        with open(os.path.join(temp_dir, 'c.jpg'), 'wb') as f:
            f.write(b'fake jpg bytes')
        with open(os.path.join(temp_dir, 'notes.txt'), 'w') as f:
            f.write('hello')

        found = scanner.find_image_files()

        assert len(found) == 3
        assert all(os.path.isabs(p) for p in found)
        assert any(p.endswith('a.png') for p in found)
        assert any(p.endswith('b.PNG') for p in found)
        assert any(p.endswith('c.jpg') for p in found)


class TestScanAndSync:
    def test_new_file_defaults_image_type_to_token_and_persists_to_png(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'new_token.png')
        make_png(filepath)

        results = scanner.scan_and_sync()

        assert results == {'added': 1, 'updated': 0, 'removed': 0, 'errors': 0, 'timed_out': 0}
        db_row = scanner.database.get_token_by_filepath(filepath)
        assert db_row['image_type'] == 'Token'
        png_meta = TokenMetadata.read_token_metadata(filepath)
        assert png_meta['ImageType'] == 'Token'

    def test_existing_modified_file_gets_updated(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'token.png')
        make_png(filepath)
        scanner.scan_and_sync()

        TokenMetadata.write_token_metadata(filepath, {'Name': 'Renamed'})
        os.utime(filepath, (time.time() + 5, time.time() + 5))

        results = scanner.scan_and_sync()

        assert results['updated'] == 1
        assert results['added'] == 0
        db_row = scanner.database.get_token_by_filepath(filepath)
        assert db_row['name'] == 'Renamed'

    def test_unmodified_existing_file_not_recounted(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'token.png')
        make_png(filepath)
        scanner.scan_and_sync()

        results = scanner.scan_and_sync()

        assert results == {'added': 0, 'updated': 0, 'removed': 0, 'errors': 0, 'timed_out': 0}

    def test_get_file_info_none_counts_as_error(self, scanner, temp_dir, mocker):
        filepath = os.path.join(temp_dir, 'token.png')
        make_png(filepath)
        mocker.patch('scanner.TokenMetadata.get_file_info', return_value=None)

        results = scanner.scan_and_sync()

        assert results['errors'] == 1
        assert results['added'] == 0

    def test_progress_callback_invoked_per_file(self, scanner, temp_dir):
        make_png(os.path.join(temp_dir, 'a.png'))
        make_png(os.path.join(temp_dir, 'b.png'))
        calls = []

        scanner.scan_and_sync(progress_callback=lambda i, total, path: calls.append((i, total, path)))

        assert len(calls) == 2
        assert {c[0] for c in calls} == {1, 2}
        assert all(c[1] == 2 for c in calls)

    def test_existing_image_type_preserved_when_png_metadata_missing_it(self, scanner, temp_dir, mocker):
        filepath = os.path.join(temp_dir, 'map.png')
        make_png(filepath)
        scanner.scan_and_sync()
        scanner.database.update_token_by_filepath(filepath, {'ImageType': 'Map', 'file_modified': scanner.database.get_token_by_filepath(filepath)['file_modified']})

        mocker.patch(
            'scanner.TokenMetadata.get_file_info',
            return_value={
                'filepath': filepath,
                'filename': 'map.png',
                'file_modified': 'a-different-timestamp',
                'file_size': 123,
                'ImageType': None,
                'Name': None,
            },
        )

        results = scanner.scan_and_sync()

        assert results['updated'] == 1
        db_row = scanner.database.get_token_by_filepath(filepath)
        assert db_row['image_type'] == 'Map'


class TestAddNewFile:
    def test_success(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'token.png')
        make_png(filepath)

        assert scanner.add_new_file(filepath) is True
        db_row = scanner.database.get_token_by_filepath(filepath)
        assert db_row is not None
        assert db_row['date_added'] is not None

    def test_failure_when_file_info_unavailable(self, scanner, temp_dir, mocker):
        mocker.patch('scanner.TokenMetadata.get_file_info', return_value=None)
        assert scanner.add_new_file(os.path.join(temp_dir, 'missing.png')) is False


class TestUpdateExistingFile:
    def test_success(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'token.png')
        make_png(filepath)
        scanner.add_new_file(filepath)

        TokenMetadata.write_token_metadata(filepath, {'Name': 'Updated Name'})

        assert scanner.update_existing_file(filepath) is True
        db_row = scanner.database.get_token_by_filepath(filepath)
        assert db_row['name'] == 'Updated Name'

    def test_failure_when_file_info_unavailable(self, scanner, temp_dir, mocker):
        mocker.patch('scanner.TokenMetadata.get_file_info', return_value=None)
        assert scanner.update_existing_file(os.path.join(temp_dir, 'token.png')) is False


class TestVerifyAllReferences:
    def test_empty_database(self, scanner):
        results = scanner.verify_all_references()
        assert results == {'verified': 0, 'missing': [], 'errors': 0, 'timed_out': 0}

    def test_existing_and_missing_files(self, scanner, temp_dir):
        present_path = os.path.join(temp_dir, 'present.png')
        missing_path = os.path.join(temp_dir, 'missing.png')
        make_png(present_path)
        make_png(missing_path)
        scanner.scan_and_sync()
        os.remove(missing_path)

        results = scanner.verify_all_references()

        assert results['verified'] == 1
        assert results['errors'] == 0
        assert len(results['missing']) == 1
        assert results['missing'][0]['filepath'] == missing_path

        present_row = scanner.database.get_token_by_filepath(present_path)
        missing_row = scanner.database.get_token_by_filepath(missing_path)
        assert present_row['is_missing'] == 0
        assert missing_row['is_missing'] == 1


class TestFindAudioFiles:
    def test_no_token_folder_returns_empty(self, test_db):
        scanner = TokenScanner(test_db, token_folder=None)
        assert scanner.find_audio_files() == []

    def test_finds_nested_audio_ignores_other_extensions(self, scanner, temp_dir):
        sub = os.path.join(temp_dir, 'sub')
        os.makedirs(sub)
        make_audio_file(os.path.join(temp_dir, 'song.mp3'))
        make_audio_file(os.path.join(sub, 'ambience.WAV'))
        make_png(os.path.join(temp_dir, 'art.png'))

        found = scanner.find_audio_files()

        assert len(found) == 2
        assert all(os.path.isabs(p) for p in found)


class TestScanAudioAndSync:
    def test_adds_new_audio_file(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'song.mp3')
        content = b'fake mp3 bytes for hashing'
        make_audio_file(filepath, content)

        results = scanner.scan_audio_and_sync()

        assert results == {'added': 1, 'updated': 0, 'removed': 0, 'errors': 0, 'timed_out': 0}
        db_row = scanner.database.get_audio_file_by_filepath(filepath)
        assert db_row is not None
        assert db_row['file_hash'] == hashlib.sha256(content).hexdigest()
        assert db_row['format'] == 'MP3'
        assert db_row['file_size'] == len(content)
        assert db_row['audio_type'] == 'Music'

    def test_unmodified_audio_file_not_recounted(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'song.mp3')
        make_audio_file(filepath)
        scanner.scan_audio_and_sync()

        results = scanner.scan_audio_and_sync()

        assert results == {'added': 0, 'updated': 0, 'removed': 0, 'errors': 0, 'timed_out': 0}

    def test_modified_audio_file_gets_updated(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'song.mp3')
        make_audio_file(filepath)
        scanner.scan_audio_and_sync()

        time.sleep(0.01)
        os.utime(filepath, (time.time() + 5, time.time() + 5))

        results = scanner.scan_audio_and_sync()

        assert results['updated'] == 1
        assert results['added'] == 0


class TestAddNewAudioFile:
    def test_success(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'song.mp3')
        content = b'another fake mp3'
        make_audio_file(filepath, content)

        assert scanner.add_new_audio_file(filepath) is True
        db_row = scanner.database.get_audio_file_by_filepath(filepath)
        assert db_row['file_hash'] == hashlib.sha256(content).hexdigest()

    def test_rejects_non_audio_file(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'image.png')
        make_png(filepath)
        assert scanner.add_new_audio_file(filepath) is False


class TestVerifyAllAudioReferences:
    def test_empty_database(self, scanner):
        results = scanner.verify_all_audio_references()
        assert results == {'verified': 0, 'missing': [], 'errors': 0, 'timed_out': 0}

    def test_existing_and_missing_audio_files(self, scanner, temp_dir):
        present_path = os.path.join(temp_dir, 'present.mp3')
        missing_path = os.path.join(temp_dir, 'missing.mp3')
        make_audio_file(present_path)
        make_audio_file(missing_path)
        scanner.scan_audio_and_sync()
        os.remove(missing_path)

        results = scanner.verify_all_audio_references()

        assert results['verified'] == 1
        assert len(results['missing']) == 1
        assert results['missing'][0]['filepath'] == missing_path


class TestFindPdfFiles:
    def test_no_token_folder_returns_empty(self, test_db):
        scanner = TokenScanner(test_db, token_folder=None)
        assert scanner.find_pdf_files() == []

    def test_finds_nested_pdfs_ignores_other_extensions(self, scanner, temp_dir):
        sub = os.path.join(temp_dir, 'sub')
        os.makedirs(sub)
        make_pdf_file(os.path.join(temp_dir, 'rules.pdf'))
        make_pdf_file(os.path.join(sub, 'module.PDF'))
        make_png(os.path.join(temp_dir, 'art.png'))

        found = scanner.find_pdf_files()

        assert len(found) == 2
        assert all(os.path.isabs(p) for p in found)


class TestScanPdfsAndSync:
    def test_adds_new_pdf_file(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'rules.pdf')
        content = b'fake pdf bytes for hashing'
        make_pdf_file(filepath, content)

        results = scanner.scan_pdfs_and_sync()

        assert results == {'added': 1, 'updated': 0, 'removed': 0, 'errors': 0, 'timed_out': 0}
        db_row = scanner.database.get_pdf_file_by_filepath(filepath)
        assert db_row is not None
        assert db_row['file_hash'] == hashlib.sha256(content).hexdigest()
        assert db_row['image_type'] == 'Handout'
        assert db_row['page_count'] is None

    def test_adds_new_pdf_file_with_real_page_count(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'rules.pdf')
        make_real_pdf(filepath, page_count=5)

        results = scanner.scan_pdfs_and_sync()

        assert results['added'] == 1
        db_row = scanner.database.get_pdf_file_by_filepath(filepath)
        assert db_row['page_count'] == 5

    def test_unmodified_pdf_file_not_recounted(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'rules.pdf')
        make_pdf_file(filepath)
        scanner.scan_pdfs_and_sync()

        results = scanner.scan_pdfs_and_sync()

        assert results == {'added': 0, 'updated': 0, 'removed': 0, 'errors': 0, 'timed_out': 0}

    def test_modified_pdf_file_gets_updated(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'rules.pdf')
        make_pdf_file(filepath)
        scanner.scan_pdfs_and_sync()

        time.sleep(0.01)
        os.utime(filepath, (time.time() + 5, time.time() + 5))

        results = scanner.scan_pdfs_and_sync()

        assert results['updated'] == 1
        assert results['added'] == 0


class TestAddNewPdfFile:
    def test_success(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'rules.pdf')
        content = b'another fake pdf'
        make_pdf_file(filepath, content)

        assert scanner.add_new_pdf_file(filepath) is True
        db_row = scanner.database.get_pdf_file_by_filepath(filepath)
        assert db_row['file_hash'] == hashlib.sha256(content).hexdigest()

    def test_rejects_non_pdf_file(self, scanner, temp_dir):
        filepath = os.path.join(temp_dir, 'image.png')
        make_png(filepath)
        assert scanner.add_new_pdf_file(filepath) is False


class TestVerifyAllPdfReferences:
    def test_empty_database(self, scanner):
        results = scanner.verify_all_pdf_references()
        assert results == {'verified': 0, 'missing': [], 'errors': 0, 'timed_out': 0}

    def test_existing_and_missing_pdf_files(self, scanner, temp_dir):
        present_path = os.path.join(temp_dir, 'present.pdf')
        missing_path = os.path.join(temp_dir, 'missing.pdf')
        make_pdf_file(present_path)
        make_pdf_file(missing_path)
        scanner.scan_pdfs_and_sync()
        os.remove(missing_path)

        results = scanner.verify_all_pdf_references()

        assert results['verified'] == 1
        assert len(results['missing']) == 1
        assert results['missing'][0]['filepath'] == missing_path


class TestFileIOTimeoutHandling:
    """
    A hung NAS/SMB mount or ejected drive shouldn't block a scan or
    verification pass forever. These tests simulate that by making
    scanner.safe_file_op raise FileOpTimeout unconditionally, standing in
    for a blocking call that never returns.
    """

    @pytest.fixture
    def timeout_everywhere(self, mocker):
        return mocker.patch('scanner.safe_file_op', side_effect=FileOpTimeout('simulated timeout'))

    def test_scan_and_sync_counts_timeout_and_marks_existing_missing(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.png')
        make_png(filepath)
        scanner.database.add_token({'filepath': filepath, 'filename': 'a.png', 'ImageType': 'Token'})

        results = scanner.scan_and_sync()

        assert results['timed_out'] == 1
        assert results['errors'] == 0
        row = scanner.database.get_token_by_filepath(filepath)
        assert row['is_missing'] == 1

    def test_add_new_file_returns_false_on_timeout(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.png')
        make_png(filepath)

        assert scanner.add_new_file(filepath) is False

    def test_verify_all_references_counts_timeout_as_missing(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.png')
        scanner.database.add_token({'filepath': filepath, 'filename': 'a.png', 'ImageType': 'Token'})

        results = scanner.verify_all_references()

        assert results['timed_out'] == 1
        assert len(results['missing']) == 1

    def test_scan_audio_and_sync_counts_timeout_and_marks_existing_missing(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.mp3')
        make_audio_file(filepath)
        scanner.database.add_audio_file({'filepath': filepath, 'filename': 'a.mp3'})

        results = scanner.scan_audio_and_sync()

        assert results['timed_out'] == 1
        row = scanner.database.get_audio_file_by_filepath(filepath)
        assert row['is_missing'] == 1

    def test_add_new_audio_file_returns_false_on_timeout(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.mp3')
        make_audio_file(filepath)

        assert scanner.add_new_audio_file(filepath) is False

    def test_verify_all_audio_references_counts_timeout_as_missing(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.mp3')
        scanner.database.add_audio_file({'filepath': filepath, 'filename': 'a.mp3'})

        results = scanner.verify_all_audio_references()

        assert results['timed_out'] == 1
        assert len(results['missing']) == 1

    def test_scan_pdfs_and_sync_counts_timeout_and_marks_existing_missing(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.pdf')
        make_pdf_file(filepath)
        scanner.database.add_pdf_file({'filepath': filepath, 'filename': 'a.pdf'})

        results = scanner.scan_pdfs_and_sync()

        assert results['timed_out'] == 1
        row = scanner.database.get_pdf_file_by_filepath(filepath)
        assert row['is_missing'] == 1

    def test_add_new_pdf_file_returns_false_on_timeout(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.pdf')
        make_pdf_file(filepath)

        assert scanner.add_new_pdf_file(filepath) is False

    def test_verify_all_pdf_references_counts_timeout_as_missing(self, scanner, temp_dir, timeout_everywhere):
        filepath = os.path.join(temp_dir, 'a.pdf')
        scanner.database.add_pdf_file({'filepath': filepath, 'filename': 'a.pdf'})

        results = scanner.verify_all_pdf_references()

        assert results['timed_out'] == 1
        assert len(results['missing']) == 1


class TestTokenFolderEventHandlerPathMatching:
    @pytest.fixture
    def handler(self, scanner, temp_dir):
        return TokenFolderEventHandler(scanner, temp_dir)

    def test_image_inside_folder_matches(self, handler, temp_dir):
        assert handler._is_image_in_token_folder(os.path.join(temp_dir, 'a.png')) is True

    def test_image_outside_folder_does_not_match(self, handler):
        assert handler._is_image_in_token_folder('/somewhere/else/a.png') is False

    def test_wrong_extension_does_not_match(self, handler, temp_dir):
        assert handler._is_image_in_token_folder(os.path.join(temp_dir, 'a.txt')) is False

    def test_audio_inside_folder_matches(self, handler, temp_dir):
        assert handler._is_audio_in_token_folder(os.path.join(temp_dir, 'a.mp3')) is True

    def test_audio_outside_folder_does_not_match(self, handler):
        assert handler._is_audio_in_token_folder('/somewhere/else/a.mp3') is False

    def test_pdf_inside_folder_matches(self, handler, temp_dir):
        assert handler._is_pdf_in_token_folder(os.path.join(temp_dir, 'a.pdf')) is True

    def test_pdf_outside_folder_does_not_match(self, handler):
        assert handler._is_pdf_in_token_folder('/somewhere/else/a.pdf') is False


class TestTokenFolderEventHandlerDispatch:
    @pytest.fixture
    def handler(self, scanner, temp_dir, mocker):
        mocker.patch('scanner.time.sleep')
        return TokenFolderEventHandler(scanner, temp_dir)

    def make_event(self, src_path, is_directory=False):
        event = mocker_namespace()
        event.src_path = src_path
        event.is_directory = is_directory
        return event

    def test_on_created_image_calls_add_new_file(self, handler, temp_dir, mocker):
        add_new_file = mocker.patch.object(handler.scanner, 'add_new_file')
        event = self.make_event(os.path.join(temp_dir, 'new.png'))

        handler.on_created(event)

        add_new_file.assert_called_once_with(os.path.abspath(event.src_path))

    def test_on_created_audio_calls_add_new_audio_file(self, handler, temp_dir, mocker):
        add_new_audio_file = mocker.patch.object(handler.scanner, 'add_new_audio_file')
        event = self.make_event(os.path.join(temp_dir, 'new.mp3'))

        handler.on_created(event)

        add_new_audio_file.assert_called_once_with(os.path.abspath(event.src_path))

    def test_on_created_directory_event_ignored(self, handler, temp_dir, mocker):
        add_new_file = mocker.patch.object(handler.scanner, 'add_new_file')
        event = self.make_event(os.path.join(temp_dir, 'newdir'), is_directory=True)

        handler.on_created(event)

        add_new_file.assert_not_called()

    def test_on_modified_image_calls_update_existing_file(self, handler, temp_dir, mocker):
        update_existing_file = mocker.patch.object(handler.scanner, 'update_existing_file')
        event = self.make_event(os.path.join(temp_dir, 'existing.png'))

        handler.on_modified(event)

        update_existing_file.assert_called_once_with(os.path.abspath(event.src_path))

    def test_on_modified_audio_calls_update_existing_audio_file(self, handler, temp_dir, mocker):
        update_existing_audio_file = mocker.patch.object(handler.scanner, 'update_existing_audio_file')
        event = self.make_event(os.path.join(temp_dir, 'existing.mp3'))

        handler.on_modified(event)

        update_existing_audio_file.assert_called_once_with(os.path.abspath(event.src_path))

    def test_on_modified_directory_event_ignored(self, handler, temp_dir, mocker):
        update_existing_file = mocker.patch.object(handler.scanner, 'update_existing_file')
        event = self.make_event(os.path.join(temp_dir, 'somedir'), is_directory=True)

        handler.on_modified(event)

        update_existing_file.assert_not_called()

    def test_on_created_pdf_calls_add_new_pdf_file(self, handler, temp_dir, mocker):
        add_new_pdf_file = mocker.patch.object(handler.scanner, 'add_new_pdf_file')
        event = self.make_event(os.path.join(temp_dir, 'new.pdf'))

        handler.on_created(event)

        add_new_pdf_file.assert_called_once_with(os.path.abspath(event.src_path))

    def test_on_modified_pdf_calls_update_existing_pdf_file(self, handler, temp_dir, mocker):
        update_existing_pdf_file = mocker.patch.object(handler.scanner, 'update_existing_pdf_file')
        event = self.make_event(os.path.join(temp_dir, 'existing.pdf'))

        handler.on_modified(event)

        update_existing_pdf_file.assert_called_once_with(os.path.abspath(event.src_path))


def mocker_namespace():
    """A minimal attribute bag standing in for a watchdog FileSystemEvent."""
    class _Event:
        pass
    return _Event()


class TestTokenFolderWatcher:
    def test_start_sets_running_then_stop_clears_it(self, scanner, temp_dir):
        watcher = TokenFolderWatcher(scanner, temp_dir)
        try:
            watcher.start()
            assert watcher.is_running() is True
        finally:
            watcher.stop()
        assert watcher.is_running() is False

    def test_double_start_does_not_replace_observer(self, scanner, temp_dir):
        watcher = TokenFolderWatcher(scanner, temp_dir)
        try:
            watcher.start()
            first_observer = watcher.observer
            watcher.start()
            assert watcher.observer is first_observer
        finally:
            watcher.stop()

    def test_is_running_false_before_start(self, scanner, temp_dir):
        watcher = TokenFolderWatcher(scanner, temp_dir)
        assert watcher.is_running() is False

    def test_stop_without_start_is_safe(self, scanner, temp_dir):
        watcher = TokenFolderWatcher(scanner, temp_dir)
        watcher.stop()
        assert watcher.is_running() is False
