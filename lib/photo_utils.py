"""Photo handling utilities for the org chart.

Photos are stored in SQLite as BLOBs. To prevent the database from getting
too large, we resize incoming photos to a maximum dimension and re-encode
them as JPEG. This means even a 5MB phone photo becomes ~30KB after
processing, so 200 employees fit in roughly 6MB.
"""

from __future__ import annotations
import io
from PIL import Image, ImageOps

# Tunable limits
MAX_INPUT_BYTES = 5 * 1024 * 1024  # 5MB raw upload limit
TARGET_DIM = 200                    # Final dimension (square, 200x200)
TARGET_QUALITY = 85                 # JPEG quality (good balance)
MAX_OUTPUT_BYTES = 100 * 1024       # 100KB hard cap on stored size

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "GIF"}


def validate_and_resize_photo(file_bytes: bytes) -> tuple[bytes, str]:
    """Validate, resize, and re-encode a photo.

    Returns (processed_bytes, info_message).
    Raises ValueError with a user-friendly message if the input is bad.
    """
    if not file_bytes:
        raise ValueError("Empty file uploaded.")
    if len(file_bytes) > MAX_INPUT_BYTES:
        raise ValueError(
            f"File too large ({len(file_bytes)/1024/1024:.1f} MB). "
            f"Please use a photo under {MAX_INPUT_BYTES//1024//1024} MB."
        )

    try:
        img = Image.open(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not read this file as an image: {e}")

    if img.format not in ALLOWED_FORMATS:
        raise ValueError(
            f"Unsupported format '{img.format}'. "
            f"Use JPG, PNG, WebP, BMP, or GIF."
        )

    # Apply EXIF orientation (so phone photos aren't sideways)
    img = ImageOps.exif_transpose(img)

    # Convert to RGB (JPEG can't store alpha; flatten on white background)
    if img.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Crop to square (centered) before resizing — gives best portrait
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # Resize to target dim
    img = img.resize((TARGET_DIM, TARGET_DIM), Image.Resampling.LANCZOS)

    # Encode as JPEG, dropping quality if we exceed the byte cap
    quality = TARGET_QUALITY
    buf = io.BytesIO()
    while quality >= 50:
        buf.seek(0)
        buf.truncate(0)
        img.save(buf, "JPEG", quality=quality, optimize=True)
        if buf.tell() <= MAX_OUTPUT_BYTES:
            break
        quality -= 10

    out_bytes = buf.getvalue()
    info = (
        f"✓ Resized to {TARGET_DIM}×{TARGET_DIM}, "
        f"{len(out_bytes)/1024:.0f} KB (JPEG, quality {quality})"
    )
    return out_bytes, info


def write_photo_to_temp(emp_no: str, photo_bytes: bytes, temp_dir: str) -> str:
    """Write photo bytes to a temp file and return the path.
    Used at org-chart render time so graphviz can include the image."""
    import os
    safe_emp = "".join(c for c in str(emp_no) if c.isalnum())
    path = os.path.join(temp_dir, f"emp_{safe_emp}.jpg")
    with open(path, "wb") as f:
        f.write(photo_bytes)
    return path


def get_photo_recommendations() -> str:
    """Markdown text shown in the upload UI."""
    return (
        "**Photo guidelines / คำแนะนำเรื่องรูปภาพ:**\n\n"
        "- **Format / รูปแบบ:** JPG, PNG, WebP\n"
        "- **Recommended size / ขนาดแนะนำ:** 400×400 to 800×800 pixels (square crop ideal)\n"
        "- **Maximum file size / ขนาดไฟล์สูงสุด:** 5 MB\n"
        "- **The system automatically:** crops to square (center), "
        "resizes to 200×200 px, re-encodes as JPEG, "
        "and stores under 100 KB to keep the database lean.\n"
        "- **ระบบจะปรับอัตโนมัติ:** ครอปเป็นจตุรัส, ย่อเป็น 200×200 px, "
        "บีบอัดเป็น JPEG, จัดเก็บไม่เกิน 100 KB เพื่อไม่ให้ฐานข้อมูลใหญ่เกินไป"
    )
