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

def attach_file(path, catalogue_number, session):
    attached_location = client.attachment_to_col_object(path, catalogue_number, session)

    if attached_location:
            log.info(f"Attachment process completed for file {path.name} to catalog number {catalogue_number}.")
            # Write image id to file EXIF (comment field)
            id_set = helpers.set_image_id(path, attached_location)
            if id_set:
                log.info(f"Image ID {attached_location} is set in EXIF for file {path.name}.")
            else:
                log.error(f"Failed to set Image ID in EXIF for file {path.name}.")
            file_moved = helpers.move_to_uploaded_dir(path)
            if file_moved:
                log.info(f"File {path.name} moved to uploaded directory.")
            else:
                log.error(f"Failed to move file {path.name} to uploaded directory.")
    else:
        log.error(f"Attachment process FAILED for file {path.name} to catalog number {catalogue_number}.")
    return attached_location

# Scanning files in directory, check in Specify and update if needed
def sync_files():
    # Scan directory for files
    session = client.api_login()
    count = 0
    count_attach = 0

    stopped_by_limit = False
    for path in it:
        if path.is_file():
            count += 1
            log.info(f"\n\t\t\t\t***********************\nFILE ({count}): {path.name}")
            catalogue_number, valid = validators.is_filename_cat_num(path.name)
            print(catalogue_number)
            image_id = validators.read_image_id(path)
            log.info(f"File: {path.name}, Catalogue number: {catalogue_number}, Valid: {valid}, Image id: {image_id}")
            
            if not valid or image_id is not None:
                log.info(f"File {path.name} skipped")
                continue

            if catalogue_number and len(catalogue_number) > 1:
                uploaded_all_files = False
                log.info(f"Multiple catalogue numbers found in filename: {catalogue_number}")
                splitted = helpers.split_image_multiple_cat_nums(path)
                if splitted:
                    log.info(f"File {path.name} split into {len(splitted)} files to individual catalogue numbers.")
                    for idx, cat_num in enumerate(catalogue_number):
                        new_path = root / splitted[idx]
                        attached = attach_file(new_path, cat_num, session)
                        if attached and idx == 0:
                            count_attach += 1
                            uploaded_all_files = True
                        elif attached and idx > 0 and uploaded_all_files is False:
                            count_attach += 1
                            uploaded_all_files = False
                        elif attached and uploaded_all_files:
                            count_attach += 1
                        elif not attached:
                            uploaded_all_files = False
                    if uploaded_all_files:
                        log.info(f"All split files from {path.name} uploaded successfully.")
                        moved = helpers.move_to_uploaded_dir(path)
                        if moved:
                            log.info(f"Original file {path.name} moved to uploaded directory after splitting.")
                        else:
                            log.error(f"Failed to move original file {path.name} to uploaded directory after splitting.")
                else:
                    log.error(f"Failed to split file {path.name} to multiple catalogue numbers.")
                continue
           
            else:
                attach_file(path, catalogue_number, session)

    log.info(f"Scan completed. Iterated {count} files under {root}")