"""Quick test: send a Monobank screenshot to Vision OCR and show parsed results."""
import asyncio
import sys
from pathlib import Path

# Add bot dir to path
sys.path.insert(0, str(Path(__file__).parent))

from config import GOOGLE_VISION_API_KEY
from services.ocr import extract_text_from_image
from utils.parsers import parse_monobank_ocr


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_ocr.py <image_path>")
        print("  Drag a Monobank screenshot onto this command.")
        return

    image_path = sys.argv[1]
    image_bytes = Path(image_path).read_bytes()

    print(f"Image: {image_path} ({len(image_bytes)} bytes)")
    print(f"API key: {GOOGLE_VISION_API_KEY[:10]}...")
    print()

    # 1. OCR
    ocr_text = await extract_text_from_image(image_bytes, GOOGLE_VISION_API_KEY)

    print("=" * 60)
    print("RAW OCR TEXT:")
    print("=" * 60)
    print(repr(ocr_text))  # repr shows \n, \u00a0, etc.
    print()
    print("--- Human-readable ---")
    print(ocr_text)
    print("=" * 60)

    # 2. Parse
    parsed = parse_monobank_ocr(ocr_text)

    print()
    print("PARSED RESULT:")
    print(f"  sender:  {parsed['sender_name']!r}")
    print(f"  amount:  {parsed['amount']!r}")
    print(f"  date:    {parsed['date']!r}")
    print(f"  purpose: {parsed['purpose']!r}")


asyncio.run(main())
