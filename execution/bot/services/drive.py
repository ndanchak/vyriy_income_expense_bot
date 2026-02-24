"""
Google Drive upload service for expense receipts.

Uploads receipt photos to a shared Google Drive folder and returns
a shareable link that gets stored in both PostgreSQL and Google Sheets.
"""

import base64
import io
import json
import logging
from datetime import datetime
from typing import Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import GOOGLE_SHEETS_CREDS_JSON, GOOGLE_DRIVE_FOLDER_ID

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]

_service = None


def _get_drive_service():
    """Initialize or return cached Google Drive API v3 service."""
    global _service
    if _service is None:
        creds_json = json.loads(base64.b64decode(GOOGLE_SHEETS_CREDS_JSON))
        credentials = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
        _service = build("drive", "v3", credentials=credentials)
        logger.info("Google Drive service initialized")
    return _service


def _detect_mimetype(image_bytes: bytes) -> tuple[str, str]:
    """Detect image MIME type from magic bytes. Returns (mimetype, extension)."""
    if image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
        return "image/png", ".png"
    if image_bytes[:2] == b'\xff\xd8':
        return "image/jpeg", ".jpg"
    if image_bytes[:4] == b'RIFF' and image_bytes[8:12] == b'WEBP':
        return "image/webp", ".webp"
    # Default to JPEG (most common from Telegram)
    return "image/jpeg", ".jpg"


def upload_receipt(image_bytes: bytes, filename: Optional[str] = None) -> str:
    """Upload receipt photo to Google Drive folder.

    Args:
        image_bytes: Raw image binary data.
        filename: Optional custom filename. Defaults to receipt_YYYYMMDD_HHMMSS.ext.

    Returns:
        Shareable link (anyone with link can view).
        Empty string on failure.
    """
    mimetype, ext = _detect_mimetype(image_bytes)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"receipt_{timestamp}{ext}"

    try:
        service = _get_drive_service()

        # Create file in the receipts folder
        file_metadata = {
            "name": filename,
            "parents": [GOOGLE_DRIVE_FOLDER_ID],
        }

        media = MediaIoBaseUpload(
            io.BytesIO(image_bytes),
            mimetype=mimetype,
            resumable=False,
        )

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, webViewLink",
        ).execute()

        file_id = file.get("id")

        # Set permission: anyone with link can view
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
        ).execute()

        link = file.get("webViewLink", f"https://drive.google.com/file/d/{file_id}/view")
        logger.info("Receipt uploaded to Drive: %s → %s", filename, link)
        return link

    except Exception as e:
        logger.error("Failed to upload receipt to Drive: %s", e)
        return ""
