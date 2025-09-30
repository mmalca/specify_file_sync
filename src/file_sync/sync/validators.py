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


def has_imageid(file_path):
    pass


def read_image_unique_id(path: str | Path) -> str | None:
    """
    Returns the EXIF ImageUniqueID (what Windows shows as 'Image ID')
    for JPEG/TIFF files, or None if not present / unsupported.
    """
    p = Path(path)
    try:
        exif = piexif.load(str(p))
        val = exif.get("Exif", {}).get(piexif.ExifIFD.ImageUniqueID)
        if val is None:
            return None
        if isinstance(val, bytes):
            return val.decode("ascii", "ignore").strip("\x00").strip()
        return str(val).strip()
    except Exception:
        return None

def has_image_id(path) -> bool:
    # got = read_image_unique_id(path)
    # if got is None:
    #     print("F")
    #     return False
    # print("T")
    # return True


    ##########
    # img = None  # Initialize img to None

    # # Open the image
    # img = Image.open(path)

    # # Get existing EXIF data or create an empty dict if none exists
    # exif_data = img.info.get('exif')
    # if exif_data:
    #     exif_dict = piexif.load(exif_data)
    #     print(exif_dict)
    #     return True
    ###################
    pass

PREFIXES = {
    b"ASCII\x00\x00\x00": "ascii",
    b"UNICODE\x00": "utf-16",            # EXIF "Unicode" (UTF-16 LE, no BOM)
    b"JIS\x00\x00\x00\x00\x00": "shift_jis",
}

def read_exif_user_comment(path: str | Path) -> str | None:
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


def has_user_comment(path: str | Path, expected: str) -> bool:
    val = read_exif_user_comment(path)
    return val == expected


