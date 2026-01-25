"""
Google Drive API Client Wrapper
Provides methods for file and folder operations with retry logic and error handling.
"""

import io
import time
import random
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


class DriveClient:
    """Wrapper for Google Drive API operations with retry logic."""

    def __init__(self, credentials):
        """
        Initialize the Drive client with credentials.

        Args:
            credentials: Google OAuth2 credentials object
        """
        self.credentials = credentials
        self.service = build('drive', 'v3', credentials=credentials)

    def _execute_with_retry(self, request, max_retries=5):
        """
        Execute API request with exponential backoff retry logic.

        Args:
            request: The API request to execute
            max_retries: Maximum number of retry attempts

        Returns:
            The API response

        Raises:
            Exception: If max retries exceeded or non-retriable error
        """
        for attempt in range(max_retries):
            try:
                return request.execute()

            except HttpError as e:
                status = e.resp.status

                # Retriable errors: rate limit, server errors
                if status in [429, 500, 502, 503, 504]:
                    if attempt == max_retries - 1:
                        raise Exception(f"Max retries exceeded: {str(e)}")

                    # Exponential backoff with jitter
                    wait_time = min((2 ** attempt) + random.random(), 64)
                    print(f"Rate limited or server error. Waiting {wait_time:.2f}s before retry {attempt + 1}/{max_retries}")
                    time.sleep(wait_time)
                    continue

                # Non-retriable errors
                else:
                    raise

            except Exception as e:
                # Network or other errors
                if attempt == max_retries - 1:
                    raise
                wait_time = (2 ** attempt)
                print(f"Error occurred: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue

        raise Exception(f"Failed after {max_retries} retries")

    # ===== FILE OPERATIONS =====

    def upload_file(self, file_stream, filename, folder_id=None, metadata=None, mimetype='image/png'):
        """
        Upload a file to Google Drive with metadata as custom properties.

        Args:
            file_stream: BytesIO object containing file data
            filename: Name for the file in Drive
            folder_id: Optional Drive folder ID to upload to
            metadata: Optional dict of metadata to store as custom properties
            mimetype: MIME type of the file

        Returns:
            dict: File metadata including id, name, webViewLink, thumbnailLink
        """
        file_metadata = {
            'name': filename,
            'properties': metadata or {}
        }

        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaIoBaseUpload(
            file_stream,
            mimetype=mimetype,
            resumable=True,
            chunksize=1024*1024  # 1 MB chunks
        )

        request = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, mimeType, parents, webViewLink, thumbnailLink, modifiedTime, md5Checksum'
        )

        # Execute with resumable upload progress tracking
        response = None
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"Upload progress: {progress}%")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # Server error during upload - retry from this chunk
                    print(f"Server error during upload, retrying...")
                    time.sleep(2)
                    continue
                elif e.resp.status == 404:
                    # Upload session expired - need to restart
                    print(f"Upload session expired, restarting upload...")
                    request = self.service.files().create(
                        body=file_metadata,
                        media_body=media,
                        fields='id, name, mimeType, parents, webViewLink, thumbnailLink, modifiedTime, md5Checksum'
                    )
                    response = None
                    continue
                else:
                    raise

        return response

    def download_file(self, file_id):
        """
        Download a file from Google Drive.

        Args:
            file_id: The Drive file ID

        Returns:
            tuple: (file_bytes, mimetype)
        """
        # Get file metadata to determine mimetype
        file_metadata = self._execute_with_retry(
            self.service.files().get(fileId=file_id, fields='mimeType')
        )
        mimetype = file_metadata.get('mimeType', 'application/octet-stream')

        # Download file content
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024*1024)

        done = False
        while not done:
            try:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"Download progress: {progress}%")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    # Server error during download - retry
                    print(f"Server error during download, retrying...")
                    time.sleep(2)
                    continue
                else:
                    raise

        return fh.getvalue(), mimetype

    def delete_file(self, file_id):
        """
        Delete a file from Google Drive.

        Args:
            file_id: The Drive file ID

        Returns:
            bool: True if successful
        """
        try:
            self._execute_with_retry(
                self.service.files().delete(fileId=file_id)
            )
            return True
        except HttpError as e:
            if e.resp.status == 404:
                print(f"File {file_id} not found, already deleted")
                return True
            raise

    def get_file_metadata(self, file_id):
        """
        Get metadata for a file.

        Args:
            file_id: The Drive file ID

        Returns:
            dict: File metadata
        """
        return self._execute_with_retry(
            self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, parents, webViewLink, thumbnailLink, properties, modifiedTime, md5Checksum, size'
            )
        )

    def update_file_metadata(self, file_id, metadata):
        """
        Update file metadata (custom properties).

        Args:
            file_id: The Drive file ID
            metadata: dict of metadata to update

        Returns:
            dict: Updated file metadata
        """
        file_metadata = {
            'properties': metadata
        }

        return self._execute_with_retry(
            self.service.files().update(
                fileId=file_id,
                body=file_metadata,
                fields='id, name, properties, modifiedTime'
            )
        )

    # ===== FOLDER OPERATIONS =====

    def list_folders(self, parent_folder_id=None, page_size=100):
        """
        List folders in Drive.

        Args:
            parent_folder_id: Optional parent folder ID (None for root)
            page_size: Number of results per page

        Returns:
            list: List of folder metadata dicts
        """
        # Build query for folders only
        query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        folders = []
        page_token = None

        while True:
            try:
                results = self._execute_with_retry(
                    self.service.files().list(
                        q=query,
                        pageSize=page_size,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name, parents, modifiedTime)",
                        orderBy='name'
                    )
                )

                folders.extend(results.get('files', []))
                page_token = results.get('nextPageToken')

                if not page_token:
                    break

            except Exception as e:
                print(f"Error listing folders: {str(e)}")
                break

        return folders

    def list_files_in_folder(self, folder_id, page_size=100, recursive=False):
        """
        List all files in a folder.

        Args:
            folder_id: The Drive folder ID
            page_size: Number of results per page
            recursive: If True, recursively list files in subfolders

        Returns:
            list: List of file metadata dicts
        """
        files = []

        # Query for files (not folders) in this folder
        query = f"'{folder_id}' in parents and trashed=false and mimeType!='application/vnd.google-apps.folder'"

        page_token = None
        while True:
            try:
                results = self._execute_with_retry(
                    self.service.files().list(
                        q=query,
                        pageSize=page_size,
                        pageToken=page_token,
                        fields="nextPageToken, files(id, name, mimeType, parents, webViewLink, thumbnailLink, properties, modifiedTime, md5Checksum, size)",
                        orderBy='modifiedTime desc'
                    )
                )

                files.extend(results.get('files', []))
                page_token = results.get('nextPageToken')

                if not page_token:
                    break

            except Exception as e:
                print(f"Error listing files: {str(e)}")
                break

        # If recursive, also get files from subfolders
        if recursive:
            subfolders = self.list_folders(parent_folder_id=folder_id)
            for subfolder in subfolders:
                subfolder_files = self.list_files_in_folder(subfolder['id'], page_size, recursive=True)
                files.extend(subfolder_files)

        return files

    def get_folder_metadata(self, folder_id):
        """
        Get metadata for a folder.

        Args:
            folder_id: The Drive folder ID

        Returns:
            dict: Folder metadata
        """
        return self._execute_with_retry(
            self.service.files().get(
                fileId=folder_id,
                fields='id, name, parents, modifiedTime'
            )
        )

    def create_folder(self, folder_name, parent_folder_id=None):
        """
        Create a new folder in Drive.

        Args:
            folder_name: Name for the new folder
            parent_folder_id: Optional parent folder ID

        Returns:
            dict: Created folder metadata
        """
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        return self._execute_with_retry(
            self.service.files().create(
                body=file_metadata,
                fields='id, name, parents'
            )
        )

    # ===== UTILITY OPERATIONS =====

    def get_about(self):
        """
        Get information about the user's Drive (for connection testing).

        Returns:
            dict: Drive account information
        """
        return self._execute_with_retry(
            self.service.about().get(fields='user, storageQuota')
        )

    def refresh_credentials(self):
        """
        Refresh the OAuth access token if expired.

        Returns:
            bool: True if refresh successful
        """
        if self.credentials.expired and self.credentials.refresh_token:
            self.credentials.refresh(Request())
            self.service = build('drive', 'v3', credentials=self.credentials)
            return True
        return False
