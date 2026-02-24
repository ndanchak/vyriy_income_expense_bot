"""
Google Vision OCR service.

Mirrors Make.com module 5: sends image to TEXT_DETECTION with language hints uk, ru.
Uses raw HTTP via httpx for true async (no thread pool needed).
"""

import base64
import logging

import httpx

logger = logging.getLogger(__name__)

VISION_API_URL = "https://vision.googleapis.com/v1/images:annotate"


async def extract_text_from_image(image_bytes: bytes, api_key: str) -> str:
    """Run Google Vision TEXT_DETECTION on image bytes.

    Args:
        image_bytes: Raw image binary data.
        api_key: Google Cloud Vision API key.

    Returns:
        Full OCR text from the image, or empty string on failure.

    Equivalent to Make.com module 5:
        POST vision.googleapis.com/v1/images:annotate?key=...
        Feature: TEXT_DETECTION, maxResults: 1
        Language hints: uk, ru
        Response path: responses[0].fullTextAnnotation.text
    """
    payload = {
        "requests": [
            {
                "image": {"content": base64.b64encode(image_bytes).decode("utf-8")},
                "features": [{"type": "TEXT_DETECTION", "maxResults": 1}],
                "imageContext": {"languageHints": ["uk", "ru"]},
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                VISION_API_URL,
                params={"key": api_key},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        annotations = data.get("responses", [{}])[0]
        text = annotations.get("fullTextAnnotation", {}).get("text", "")
        logger.info("OCR extracted %d characters", len(text))
        return text

    except httpx.HTTPStatusError as e:
        logger.error("Vision API HTTP error: %s %s", e.response.status_code, e.response.text)
        return ""
    except Exception as e:
        logger.error("Vision API error: %s", e)
        return ""
