"""
GreenGuard AI - OCR Module

Extracts text (brand name, batch number, license number) from an uploaded
medicine package photo, and checks the packaging logo against known-good
logo hashes.

Fully OFFLINE by design - this is the module that must work with zero
internet connection, since it's often used in low-connectivity areas.

Requires:
    pip install easyocr imagehash Pillow
"""

import re
from typing import Optional

try:
    import easyocr
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

try:
    import imagehash
    from PIL import Image
    _IMAGEHASH_AVAILABLE = True
except ImportError:
    _IMAGEHASH_AVAILABLE = False

# Lazy-loaded singleton so the (heavy) OCR model only loads once
_reader = None


def _get_reader():
    global _reader
    if _reader is None:
        if not _EASYOCR_AVAILABLE:
            raise RuntimeError(
                "easyocr is not installed. Run: pip install easyocr --break-system-packages"
            )
        # English + Tamil + Hindi - swap/add language codes as needed
        _reader = easyocr.Reader(["en", "ta", "hi"], gpu=False)
    return _reader


# ---------- Text extraction ----------

def extract_text_from_image(image_path: str) -> str:
    """Run OCR on the image and return all detected text joined by newlines."""
    reader = _get_reader()
    results = reader.readtext(image_path, detail=0)  # detail=0 -> just strings
    return "\n".join(results)


# ---------- Field parsing (regex over the raw OCR text) ----------

BATCH_PATTERNS = [
    r"batch\s*(?:no\.?|number)?\s*[:\-]?\s*([A-Z0-9\-]{4,15})",
    r"b\.?no\.?\s*[:\-]?\s*([A-Z0-9\-]{4,15})",
]

LICENSE_PATTERNS = [
    r"lic\.?\s*(?:no\.?)?\s*[:\-]?\s*([A-Z0-9\-]{6,20})",
    r"license\s*(?:no\.?)?\s*[:\-]?\s*([A-Z0-9\-]{6,20})",
]


def parse_fields(raw_text: str) -> dict:
    """Pull out batch number / license number candidates from raw OCR text."""
    text_upper = raw_text.upper()

    def _first_match(patterns):
        for pattern in patterns:
            match = re.search(pattern, text_upper, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    return {
        "raw_text": raw_text,
        "batch_number": _first_match(BATCH_PATTERNS),
        "license_number": _first_match(LICENSE_PATTERNS),
    }


# ---------- Logo verification ----------

def compute_image_hash(image_path: str) -> Optional[str]:
    """Compute a perceptual hash of the uploaded package image (for logo comparison)."""
    if not _IMAGEHASH_AVAILABLE:
        return None
    img = Image.open(image_path)
    return str(imagehash.phash(img))


def compare_logo_hash(uploaded_hash: str, verified_hash: str, threshold: int = 8) -> dict:
    """
    Compare two perceptual hashes. Lower hamming distance = more similar.
    threshold: max allowed distance to still count as "matching" (tune this
    with real sample images - 8 is a reasonable starting point for phash).
    """
    if not uploaded_hash or not verified_hash:
        return {"match": False, "distance": None, "reason": "missing hash"}

    try:
        h1 = imagehash.hex_to_hash(uploaded_hash)
        h2 = imagehash.hex_to_hash(verified_hash)
        distance = h1 - h2
        return {"match": distance <= threshold, "distance": distance}
    except Exception as e:
        return {"match": False, "distance": None, "reason": str(e)}


def analyze_package_image(image_path: str) -> dict:
    """
    Full offline pipeline for a single uploaded image:
    1. OCR text extraction
    2. Field parsing (batch/license numbers)
    3. Perceptual hash for logo comparison (comparison against DB happens
       in trust_score.py, which has access to the medicines table)
    """
    raw_text = extract_text_from_image(image_path)
    fields = parse_fields(raw_text)
    fields["image_hash"] = compute_image_hash(image_path)
    return fields


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr_module.py <image_path>")
    else:
        result = analyze_package_image(sys.argv[1])
        print(result)
