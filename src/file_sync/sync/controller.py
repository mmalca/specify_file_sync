import os
from logs.logging_setup import setup_run_logger
import logging
from pathlib import Path
from dotenv import load_dotenv

from api import client
from sync import validators
from sync import helpers


# Set up logging
logfile = setup_run_logger(level="DEBUG")
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

# Scanning files in directory, check in Specify and update if needed
def sync_files():
    # Scan directory for files
    count = 0
    for path in it:
        if path.is_file():
            log.info(f"FILE: {path.name}")
            count += 1
            catalogue_number, valid = validators.is_filename_cat_num(path.name)
            image_id = validators.read_image_id(path)
            log.info(f"File: {path.name}, Catalogue number: {catalogue_number}, Valid: {valid}, Image id: {image_id}")
            if valid is True and image_id is None:
                attached_location = client.attachment_to_col_object(path, catalogue_number)
                if attached_location:
                        log.info(f"Attachment process completed for file {path.name} to catalog number {catalogue_number}.")
                        # Write image id to file EXIF (comment field)
                        helpers.set_image_id(path, attached_location)
                        print(f"Set attch_loc {attached_location} to image ID in file EXIF for {path.name}")
                else:
                    log.error(f"Attachment process FAILED for file {path.name} to catalog number {catalogue_number}.")
            else:
                log.info(f"File {path.name} skipped")#, either invalid catalogue number or already has image id.")
            

    log.info(f"Found {count} files under {root}")