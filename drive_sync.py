"""
Google Drive synchronization service.
Scans monitored Drive folders and syncs with the database.
"""

from typing import Dict, List, Optional
from datetime import datetime
from database import TokenDatabase
from drive_client import DriveClient


class DriveSyncService:
    """Synchronizes Google Drive folders with the local database."""

    def __init__(self, database: TokenDatabase, drive_client: DriveClient):
        """
        Initialize the sync service.

        Args:
            database: TokenDatabase instance
            drive_client: DriveClient instance
        """
        self.database = database
        self.drive_client = drive_client

    def perform_full_sync(self) -> Dict[str, int]:
        """
        Perform a full synchronization of all monitored Drive folders.

        Returns:
            Dictionary with sync results:
            {
                'added': count of new files added,
                'updated': count of files updated,
                'removed': count of files removed,
                'errors': count of errors encountered
            }
        """
        results = {
            'added': 0,
            'updated': 0,
            'removed': 0,
            'errors': 0
        }

        # Get all monitored folders
        monitored_folders = self.database.get_all_monitored_folders()

        if not monitored_folders:
            print("No monitored folders found")
            return results

        # Track all Drive file IDs found during sync
        found_drive_ids = set()

        # Process each monitored folder
        for folder in monitored_folders:
            if not folder.get('is_active'):
                continue

            folder_id = folder['drive_folder_id']
            folder_name = folder.get('folder_name', 'Unknown')

            print(f"Syncing folder: {folder_name} ({folder_id})")

            try:
                # List all files in this folder recursively
                files = self.drive_client.list_files_in_folder(
                    folder_id=folder_id,
                    recursive=True,
                    page_size=100
                )

                # Process each file
                for file_info in files:
                    try:
                        drive_file_id = file_info['id']
                        found_drive_ids.add(drive_file_id)

                        # Process this file
                        file_result = self._sync_file(file_info, folder_id)

                        if file_result == 'added':
                            results['added'] += 1
                        elif file_result == 'updated':
                            results['updated'] += 1
                        elif file_result == 'error':
                            results['errors'] += 1

                    except Exception as e:
                        print(f"Error processing file {file_info.get('name', 'unknown')}: {e}")
                        results['errors'] += 1

            except Exception as e:
                print(f"Error syncing folder {folder_name}: {e}")
                results['errors'] += 1

        # Check for files in database that are no longer in Drive
        # Get all tokens with drive_file_id set
        all_tokens = self.database.search_tokens({})
        for token in all_tokens:
            drive_file_id = token.get('drive_file_id')
            if drive_file_id and drive_file_id not in found_drive_ids:
                # File was removed from Drive
                try:
                    # Verify the file is really gone by trying to get metadata
                    try:
                        self.drive_client.get_file_metadata(drive_file_id)
                        # File still exists but not in monitored folders - skip removal
                        continue
                    except Exception:
                        # File is gone - remove from database
                        if self.database.delete_token(token['id']):
                            results['removed'] += 1
                            print(f"Removed deleted file: {token.get('filename', 'unknown')}")
                        else:
                            results['errors'] += 1
                except Exception as e:
                    print(f"Error checking/removing token {token['id']}: {e}")
                    results['errors'] += 1

        return results

    def _sync_file(self, file_info: Dict, folder_id: str) -> str:
        """
        Synchronize a single file from Drive.

        Args:
            file_info: File metadata from Drive API
            folder_id: Parent folder ID

        Returns:
            'added', 'updated', 'skipped', or 'error'
        """
        try:
            drive_file_id = file_info['id']
            filename = file_info.get('name', 'unknown')
            modified_time = file_info.get('modifiedTime')

            # Check if file exists in database
            existing = self.database.get_token_by_drive_id(drive_file_id)

            # Extract metadata from Drive custom properties
            metadata = self._extract_metadata(file_info)

            if existing is None:
                # New file - add to database
                token_data = {
                    'drive_file_id': drive_file_id,
                    'drive_folder_id': folder_id,
                    'drive_web_view_link': file_info.get('webViewLink'),
                    'drive_thumbnail_link': file_info.get('thumbnailLink'),
                    'filepath': f"drive://{drive_file_id}",  # Virtual path
                    'filename': filename,
                    'file_modified': modified_time,
                    'last_synced_from_drive': datetime.now().isoformat(),
                    **metadata
                }

                # Add DateAdded if not present
                if not token_data.get('DateAdded'):
                    token_data['DateAdded'] = datetime.now().isoformat()

                # Default ImageType to 'Token' if not specified
                if not token_data.get('ImageType'):
                    token_data['ImageType'] = 'Token'

                if self.database.add_token(token_data):
                    print(f"Added new file: {filename}")
                    return 'added'
                else:
                    print(f"Error adding file: {filename}")
                    return 'error'

            else:
                # File exists - check if modified
                if existing.get('file_modified') != modified_time:
                    # File was modified - update from Drive metadata
                    update_data = {
                        'drive_web_view_link': file_info.get('webViewLink'),
                        'drive_thumbnail_link': file_info.get('thumbnailLink'),
                        'filename': filename,
                        'file_modified': modified_time,
                        'last_synced_from_drive': datetime.now().isoformat(),
                        **metadata
                    }

                    # Preserve ImageType from database if not in Drive metadata
                    if not metadata.get('ImageType') and existing.get('ImageType'):
                        update_data['ImageType'] = existing['ImageType']

                    if self.database.update_token(existing['id'], update_data):
                        print(f"Updated file: {filename}")
                        return 'updated'
                    else:
                        print(f"Error updating file: {filename}")
                        return 'error'
                else:
                    # File unchanged
                    return 'skipped'

        except Exception as e:
            print(f"Error syncing file: {e}")
            return 'error'

    def _extract_metadata(self, file_info: Dict) -> Dict:
        """
        Extract metadata from Drive file properties.

        Drive custom properties are stored in the 'properties' field.

        Args:
            file_info: File metadata from Drive API

        Returns:
            Dictionary with extracted metadata
        """
        metadata = {}

        # Get custom properties from Drive
        properties = file_info.get('properties', {})

        # Extract all custom properties
        # These are the metadata fields we store: ImageType, Species, Class, etc.
        for key, value in properties.items():
            metadata[key] = value

        return metadata

    def sync_folder(self, folder_id: str) -> Dict[str, int]:
        """
        Synchronize a specific Drive folder.

        Args:
            folder_id: Drive folder ID to sync

        Returns:
            Dictionary with sync results
        """
        results = {
            'added': 0,
            'updated': 0,
            'removed': 0,
            'errors': 0
        }

        try:
            # Check if folder is monitored
            if not self.database.is_folder_monitored(folder_id):
                return {
                    'added': 0,
                    'updated': 0,
                    'removed': 0,
                    'errors': 1,
                    'message': 'Folder is not monitored'
                }

            # List all files in this folder recursively
            files = self.drive_client.list_files_in_folder(
                folder_id=folder_id,
                recursive=True,
                page_size=100
            )

            # Process each file
            for file_info in files:
                try:
                    file_result = self._sync_file(file_info, folder_id)

                    if file_result == 'added':
                        results['added'] += 1
                    elif file_result == 'updated':
                        results['updated'] += 1
                    elif file_result == 'error':
                        results['errors'] += 1

                except Exception as e:
                    print(f"Error processing file {file_info.get('name', 'unknown')}: {e}")
                    results['errors'] += 1

        except Exception as e:
            print(f"Error syncing folder: {e}")
            results['errors'] += 1

        return results
