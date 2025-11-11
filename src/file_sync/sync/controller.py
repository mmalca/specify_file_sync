import os
from logs.logging_setup import setup_run_logger
import logging
from pathlib import Path
from dotenv import load_dotenv

from api import client
from sync import validators
from sync import helpers
import pandas as pd


import csv
import re

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
    session = client.api_login()
    count = 0
    count_attach = 0
    # Attachment write limit (stop creating new entries once reached)
    try:
        ATT_LIMIT = int(os.getenv("ATT_LIMIT", "3000"))
    except Exception:
        ATT_LIMIT = 3000
    stopped_by_limit = False
    for path in it:
        if path.is_file():
            count += 1
            log.info(f"\n\t\t\t\t***********************\nFILE ({count}): {path.name}")
            catalogue_number, valid = validators.is_filename_cat_num(path.name)
            image_id = validators.read_image_id(path)
            log.info(f"File: {path.name}, Catalogue number: {catalogue_number}, Valid: {valid}, Image id: {image_id}")
            if valid is True and image_id is None:
                attached_location = client.attachment_to_col_object(path, catalogue_number, session)
                if attached_location:
                        count_attach += 1
                        log.info(f"Attachment process completed for file {path.name} to catalog number {catalogue_number}.")
                        # Write image id to file EXIF (comment field)
                        helpers.set_image_id(path, attached_location)
                        helpers.move_to_uploaded_dir(path)
                        log.info(f"Setting attch_loc {attached_location} to image ID in file EXIF for {path.name}")
                        # Stop iterating once we've reached the attachment limit
                        if ATT_LIMIT and count_attach >= ATT_LIMIT:
                            log.info(f"Attachment limit reached (count_attach={count_attach}); stopping iteration.")
                            stopped_by_limit = True
                            break
                else:
                    log.error(f"Attachment process FAILED for file {path.name} to catalog number {catalogue_number}.")
            else:
                log.info(f"File {path.name} skipped")#, either invalid catalogue number or already has image id.")
            

            

    if not stopped_by_limit:
        log.info("Scan completed: no more files in folder")
    log.info(f"Iterated {count} files under {root}")


