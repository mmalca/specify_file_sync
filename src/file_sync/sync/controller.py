import os
from logs.logging_setup import setup_run_logger
import logging
from pathlib import Path
from dotenv import load_dotenv

from api import client
from sync import validators

# Set up logging
logfile = setup_run_logger(level="INFO")
log = logging.getLogger(__name__)

# Load environment variables from .env file
ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

SCAN_DIR = os.getenv("SCAN_DIR")
if not SCAN_DIR:
    log.error("Please set SCAN_DIR in your .env")
    raise SystemExit(1)

root = Path(SCAN_DIR)
if not root.is_dir():
    log.error("Folder not found: %s", root)
    raise SystemExit(1)

recursive = False
it = root.rglob("*") if recursive else root.glob("*")

#scanning files in directory and check in Specify, update if needed


def sync_files():
    # Scan directory for files
    count = 0
    for path in it:
        if path.is_file():
            #log.info(f"FILE: {path.name}")      # print p for full path instead of file name
            count += 1
            catalogue_number, valid = validators.is_filename_cat_num(path.name)
            #if valid is True and validators.has_imageid(path) is False:
            #    log.info(f"File {path.name} has valid catalogue number and Image ID.")
            #    client.attachment_to_col_object(path, catalogue_number)
            has_image_id = validators.read_exif_user_comment(path)
            if has_image_id:
                log.info(f"File {path.name} has Image ID.")
                print(has_image_id)

    log.info(f"Found {count} files under {root}")