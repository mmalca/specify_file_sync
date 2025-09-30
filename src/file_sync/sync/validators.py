from pathlib import Path
import re
import piexif
from PIL import Image


#HELPER - check if filename is catalogue number
def is_filename_cat_num(filename):
    stem = Path(filename).stem  # e.g. "0123456789AB" from "0123456789AB.jpg"

    # Grab leading digits only (ignore any trailing letters or other chars)
    m = re.match(r'^(\d+)', stem)
    cat_num = m.group(1) if m else None

    is_valid_cat_num = bool(cat_num) and len(cat_num) == 10 and cat_num.startswith('0')

    return cat_num, is_valid_cat_num


PREFIXES = {
    b"ASCII\x00\x00\x00": "ascii",
    b"UNICODE\x00": "utf-16",            # EXIF "Unicode" (UTF-16 LE, no BOM)
    b"JIS\x00\x00\x00\x00\x00": "shift_jis",
}

def read_image_id(path: str | Path) -> str | None:
    """
    Returns the EXIF UserComment (what you wrote as b'ASCII\\0\\0\\0' + bytes),
    or None if missing/unsupported.
    Works for JPEG/TIFF that contain EXIF.
    """
    p = Path(path)
    try:
        exif = piexif.load(str(p))
    except Exception:
        return None

    raw = exif.get("Exif", {}).get(piexif.ExifIFD.UserComment)
    if not raw:
        return None

    if isinstance(raw, bytes):
        # Detect prefix then decode the remainder
        for prefix, enc in PREFIXES.items():
            if raw.startswith(prefix):
                data = raw[len(prefix):].rstrip(b"\x00 ")
                try:
                    return data.decode(enc, errors="ignore")
                except Exception:
                    # Fallback if decoding fails
                    return data.decode("latin-1", errors="ignore")
        # No known prefix → try UTF-8 then latin-1
        return raw.rstrip(b"\x00 ").decode("utf-8", errors="ignore") or None

    # Some tools may already return a str
    if isinstance(raw, str):
        return raw.strip() or None

    # Fallback representation
    return str(raw).strip() or None



