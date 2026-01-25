from PIL import Image
from PIL.PngImagePlugin import PngInfo
from datetime import datetime
from typing import Dict, Optional
import os


class TokenMetadata:
    """Handles reading and writing metadata to PNG files."""

    METADATA_PREFIX = "ImageVault:"
    OLD_PREFIX = "TokenVault:"  # For backwards compatibility
    FIELDS = ["Name", "ImageType", "Species", "Class", "Source", "Campaign", "Notes", "DateAdded",
              "Scale", "Theme", "Type", "Subject", "Style", "Location", "Mood",
              "Rarity", "Category", "Attunement"]

    @staticmethod
    def detect_image_format(filepath: str) -> str:
        """
        Detect if file is PNG or JPEG.

        Args:
            filepath: Path to the image file

        Returns:
            'PNG' or 'JPEG'

        Raises:
            ValueError: If file format is unsupported
        """
        # Fast path: check extension first
        ext = filepath.lower()
        if ext.endswith('.png'):
            return 'PNG'
        elif ext.endswith(('.jpg', '.jpeg')):
            return 'JPEG'

        # Fallback: Use PIL to detect format
        try:
            with Image.open(filepath) as img:
                return img.format  # Returns 'PNG' or 'JPEG'
        except Exception as e:
            raise ValueError(f"Unsupported image format: {filepath}") from e

    @staticmethod
    def _write_png_metadata(filepath: str, metadata: Dict[str, str]) -> bool:
        """
        Write metadata to a PNG file using PNG text chunks.

        Args:
            filepath: Path to the PNG file
            metadata: Dictionary of metadata to write (without TokenVault: prefix)

        Returns:
            True if successful, False otherwise
        """
        try:
            img = Image.open(filepath)
            pnginfo = PngInfo()

            # Preserve existing chunks that aren't ImageVault or TokenVault metadata
            if hasattr(img, 'text'):
                for key, value in img.text.items():
                    if not key.startswith(TokenMetadata.METADATA_PREFIX) and not key.startswith(TokenMetadata.OLD_PREFIX):
                        pnginfo.add_text(key, value)

            # Add our metadata
            for key, value in metadata.items():
                if value is not None:  # Only write non-None values
                    pnginfo.add_text(f'{TokenMetadata.METADATA_PREFIX}{key}', str(value))

            # Save the image with metadata
            img.save(filepath, pnginfo=pnginfo)
            return True

        except Exception as e:
            print(f"Error writing PNG metadata to {filepath}: {e}")
            return False

    @staticmethod
    def _write_jpeg_metadata(filepath: str, metadata: Dict[str, str]) -> bool:
        """
        Write metadata to JPEG using EXIF UserComment as JSON.

        Args:
            filepath: Path to the JPEG file
            metadata: Dictionary of metadata to write (without TokenVault: prefix)

        Returns:
            True if successful, False otherwise
        """
        try:
            import json

            img = Image.open(filepath)
            exif_dict = img.getexif() if hasattr(img, 'getexif') else {}

            # Convert metadata to JSON with TokenVault prefix
            vault_metadata = {
                f'{TokenMetadata.METADATA_PREFIX}{key}': str(value)
                for key, value in metadata.items()
                if value is not None
            }

            # Store as JSON in UserComment (EXIF tag 0x9286)
            json_str = json.dumps(vault_metadata)
            exif_dict[0x9286] = json_str.encode('utf-8')

            # Save with updated EXIF (quality=95 to preserve image quality)
            img.save(filepath, exif=exif_dict, quality=95, subsampling=0)
            return True

        except Exception as e:
            print(f"Error writing JPEG metadata to {filepath}: {e}")
            return False

    @staticmethod
    def _read_jpeg_metadata(filepath: str) -> Dict[str, Optional[str]]:
        """
        Read metadata from JPEG EXIF UserComment JSON.

        Args:
            filepath: Path to the JPEG file

        Returns:
            Dictionary of metadata (without TokenVault: prefix)
        """
        import json

        metadata = {}

        try:
            img = Image.open(filepath)
            exif_dict = img.getexif() if hasattr(img, 'getexif') else {}

            # UserComment is EXIF tag 0x9286
            if 0x9286 in exif_dict:
                try:
                    user_comment = exif_dict[0x9286]

                    # Decode if bytes
                    if isinstance(user_comment, bytes):
                        user_comment = user_comment.decode('utf-8')

                    # Parse JSON
                    vault_metadata = json.loads(user_comment)

                    # Extract fields (remove ImageVault: or TokenVault: prefix)
                    for key, value in vault_metadata.items():
                        if key.startswith(TokenMetadata.METADATA_PREFIX):
                            field = key.replace(TokenMetadata.METADATA_PREFIX, '')
                            metadata[field] = value
                        elif key.startswith(TokenMetadata.OLD_PREFIX):  # Backwards compatibility
                            field = key.replace(TokenMetadata.OLD_PREFIX, '')
                            metadata[field] = value

                except Exception as e:
                    print(f"Error parsing JPEG metadata JSON: {e}")

        except Exception as e:
            print(f"Error reading JPEG metadata from {filepath}: {e}")

        return metadata

    @staticmethod
    def write_token_metadata(filepath: str, metadata: Dict[str, str]) -> bool:
        """
        Write metadata to PNG or JPEG file.

        Args:
            filepath: Path to the image file
            metadata: Dictionary of metadata to write (without TokenVault: prefix)

        Returns:
            True if successful, False otherwise
        """
        try:
            format_type = TokenMetadata.detect_image_format(filepath)

            if format_type == 'PNG':
                return TokenMetadata._write_png_metadata(filepath, metadata)
            elif format_type == 'JPEG':
                return TokenMetadata._write_jpeg_metadata(filepath, metadata)
            else:
                raise ValueError(f"Unsupported format: {format_type}")

        except Exception as e:
            print(f"Error writing metadata to {filepath}: {e}")
            return False

    @staticmethod
    def _read_png_metadata(filepath: str) -> Dict[str, Optional[str]]:
        """
        Read metadata from a PNG file using PNG text chunks.

        Args:
            filepath: Path to the PNG file

        Returns:
            Dictionary of metadata (without TokenVault: prefix)
        """
        metadata = {}

        try:
            img = Image.open(filepath)

            if hasattr(img, 'text'):
                for key, value in img.text.items():
                    if key.startswith(TokenMetadata.METADATA_PREFIX):
                        field = key.replace(TokenMetadata.METADATA_PREFIX, '')
                        metadata[field] = value
                    elif key.startswith(TokenMetadata.OLD_PREFIX):  # Backwards compatibility
                        field = key.replace(TokenMetadata.OLD_PREFIX, '')
                        metadata[field] = value

        except Exception as e:
            print(f"Error reading PNG metadata from {filepath}: {e}")

        return metadata

    @staticmethod
    def read_token_metadata(filepath: str) -> Dict[str, Optional[str]]:
        """
        Read metadata from PNG or JPEG file.

        Args:
            filepath: Path to the image file

        Returns:
            Dictionary of metadata (without TokenVault: prefix)
        """
        try:
            format_type = TokenMetadata.detect_image_format(filepath)

            if format_type == 'PNG':
                metadata = TokenMetadata._read_png_metadata(filepath)
            elif format_type == 'JPEG':
                metadata = TokenMetadata._read_jpeg_metadata(filepath)
            else:
                metadata = {}

            # Return all expected fields, even if not present
            result = {field: metadata.get(field) for field in TokenMetadata.FIELDS}

            # DO NOT default ImageType - let it be None if not in PNG
            # Database is source of truth; PNG metadata may be incomplete
            # Scanner will preserve database value when PNG is missing ImageType
            if not result.get('ImageType'):
                result['ImageType'] = None

            return result

        except Exception as e:
            print(f"Error reading metadata from {filepath}: {e}")
            result = {field: None for field in TokenMetadata.FIELDS}
            # Do NOT default ImageType to 'Token' on error
            # Let all fields be None on error
            return result

    @staticmethod
    def add_date_if_missing(filepath: str) -> None:
        """
        Add DateAdded metadata if it doesn't exist.

        Args:
            filepath: Path to the PNG file
        """
        metadata = TokenMetadata.read_token_metadata(filepath)

        if not metadata.get('DateAdded'):
            metadata['DateAdded'] = datetime.now().isoformat()
            TokenMetadata.write_token_metadata(filepath, metadata)

    @staticmethod
    def update_metadata(filepath: str, updates: Dict[str, str]) -> bool:
        """
        Update specific metadata fields without overwriting others.

        Args:
            filepath: Path to the PNG file
            updates: Dictionary of fields to update

        Returns:
            True if successful, False otherwise
        """
        try:
            # Read existing metadata
            metadata = TokenMetadata.read_token_metadata(filepath)

            # Update with new values
            for key, value in updates.items():
                if key in TokenMetadata.FIELDS:
                    metadata[key] = value

            # Write back
            return TokenMetadata.write_token_metadata(filepath, metadata)

        except Exception as e:
            print(f"Error updating metadata for {filepath}: {e}")
            return False

    @staticmethod
    def get_file_info(filepath: str) -> Dict[str, any]:
        """
        Get file information including metadata.

        Args:
            filepath: Path to the PNG file

        Returns:
            Dictionary with file info and metadata
        """
        try:
            stat = os.stat(filepath)
            metadata = TokenMetadata.read_token_metadata(filepath)

            return {
                'filepath': filepath,
                'filename': os.path.basename(filepath),
                'file_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'file_size': stat.st_size,
                **metadata
            }

        except Exception as e:
            print(f"Error getting file info for {filepath}: {e}")
            return None
