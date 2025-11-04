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


def check_files():
    scan_root = Path(SCAN_DIR) if SCAN_DIR else root
    # csv_file = f"Z:\\Data\\Herbarium\\VascularPlants\\attachment_list.csv"
    # missing_csv_path = csv_file.with_name(csv_file.stem + "_missing.csv")
    csv_file = Path(r"Z:\Data\Herbarium\VascularPlants\attachment_list.csv")
    missing_csv_path = csv_file.with_name(csv_file.stem + "_missing.csv")

    if not csv_file.exists():
        log.error("CSV file not found: %s", csv_file)
        return

    # Read CSV into memory and build lookup by attachment location (column 0)
    rows = []
    attach_index: dict[str, int] = {}
    try:
        with csv_file.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            for i, row in enumerate(reader):
                rows.append(row)
                if len(row) >= 1:
                    key = row[0].strip()
                    if key and key not in attach_index:
                        attach_index[key] = i  # record first occurrence
    except Exception:
        log.exception("Failed to read CSV: %s", csv_file)
        return

    missing: list[tuple[str, str]] = []

    # iterate files in the scan root (non-recursive to match sync_files)
    for path in scan_root.glob("*"):
        if not path.is_file():
            continue

        catalogue_number, valid = validators.is_filename_cat_num(path.name)
        if not valid:
            continue

        comment = validators.read_image_id(path)
        if not comment:
            continue

        # extract attachment location after "ImageID:" (case-insensitive)
        m = re.search(r"ImageID:\s*(\S+)", comment, flags=re.IGNORECASE)
        att_loc = m.group(1).strip() if m else comment.strip()
        if not att_loc:
            continue

        # lookup in CSV
        row_idx = attach_index.get(att_loc)
        if row_idx is not None:
            row = rows[row_idx]
            # get catalogue number from CSV third column if present
            csv_cat = row[2].strip() if len(row) >= 3 else ""
            # compare stems (ignore extensions)
            csv_cat_stem = Path(csv_cat).stem if csv_cat else ""
            file_cat = catalogue_number or ""

            # Ensure 4th column exists
            if len(row) < 4:
                row.extend([""] * (4 - len(row)))

            if csv_cat_stem == file_cat and file_cat != "":
                row[3] = "att_loc exists, same catalogue numbers"
            else:
                # per spec: include catalogue number from the file name in message
                row[3] = f"att_loc exists, but for catalogue number {file_cat}"
            rows[row_idx] = row
        else:
            # not found -> save for missing CSV
            missing.append((att_loc, catalogue_number or ""))

    # Write updated CSV back (overwrite original)
    try:
        with csv_file.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerows(rows)
        log.info("Updated CSV written: %s", csv_file)
    except Exception:
        log.exception("Failed to write updated CSV: %s", csv_file)

    # Write missing CSV if any missing entries found
    if missing:
        try:
            with missing_csv_path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["attachment_location", "catalogue_number"])
                writer.writerows(missing)
            log.info("Missing attachments written to: %s", missing_csv_path)
        except Exception:
            log.exception("Failed to write missing CSV: %s", missing_csv_path)

def files_list_to_csv():
    scan_root = Path(SCAN_DIR) if SCAN_DIR else root
    output_csv = Path("Z:\\Data\\Herbarium\\VascularPlants\\image_upload_verification\\files_list.csv")
    # CSV used by check_files
    csv_file = Path(r"Z:\\Data\\Herbarium\\VascularPlants\\attachment_list_updated.csv")

    # Build lookup tables from the check_files CSV (attachment_location -> catalogue_number) and reverse
    attach_to_cat: dict[str, str] = {}
    cat_to_attach: dict[str, str] = {}
    if csv_file.exists():
        try:
            with csv_file.open(newline="", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                for row in reader:
                    if not row:
                        continue
                    att_loc = row[0].strip() if len(row) >= 1 else ""
                    csv_cat = row[2].strip() if len(row) >= 3 else ""
                    if att_loc:
                        attach_to_cat.setdefault(att_loc, csv_cat)
                    if csv_cat:
                        cat_to_attach.setdefault(csv_cat, att_loc)
        except Exception:
            log.exception("Failed to read check CSV for lookups: %s", csv_file)

    try:
        with output_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            # Header: filename, catalogue_number, is_catalogue_number, image_id (string after Image ID:), same_row, found_with_mistake
            writer.writerow([
                "filename",
                "catalogue_number",
                "is_catalogue_number",
                "image_id",
                "match_in_check_csv",
                "found_with_mistake",
            ])

            for path in scan_root.glob("*"):
                if path.is_file():
                    catalogue_number, valid = validators.is_filename_cat_num(path.name)
                    comment = validators.read_image_id(path) or ""
                    # extract the string after "ImageID:" or "Image ID:" (case-insensitive)
                    m = re.search(r"(?:ImageID|Image ID)\s*:\s*(\S+)", comment, flags=re.IGNORECASE)
                    image_id_val = m.group(1).strip() if m else ""

                    # Determine match_in_check_csv: True if image_id exists and attach_to_cat[image_id] == catalogue_number
                    match_in_check = False
                    if image_id_val and image_id_val in attach_to_cat and catalogue_number:
                        csv_cat_for_att = attach_to_cat.get(image_id_val, "")
                        if csv_cat_for_att and csv_cat_for_att == catalogue_number:
                            match_in_check = True

                    # Determine found_with_mistake messages
                    mistakes = []
                    # Case A: catalogue number exists in CSV mapped to a different attachment location
                    if catalogue_number and catalogue_number in cat_to_attach:
                        mapped_att = cat_to_attach[catalogue_number]
                        if mapped_att and mapped_att != image_id_val:
                            mistakes.append(
                                f"catalogue number in filename {catalogue_number} maps to att_loc '{mapped_att}' in CSV (comment att_loc '{image_id_val}')"
                            )
                    # Case B: image_id/attachment loc exists in CSV but for a different catalogue number
                    if image_id_val and image_id_val in attach_to_cat:
                        csv_cat = attach_to_cat.get(image_id_val, "")
                        if csv_cat and csv_cat != catalogue_number:
                            mistakes.append(
                                f"attachment location in comment associated in CSV with catalogue number {csv_cat} (file catalogue {catalogue_number})"
                            )

                    found_with_mistake = "; ".join(mistakes) if mistakes else ""

                    writer.writerow([
                        path.name,
                        catalogue_number or "",
                        "yes" if valid else "no",
                        image_id_val,
                        "yes" if match_in_check else "no",
                        found_with_mistake,
                    ])
        log.info("Files list CSV written: %s", output_csv)
    except Exception:
        log.exception("Failed to write files list CSV: %s", output_csv)

from pathlib import Path
import csv
import re
import logging as log

# Assumed available in your module:
# - SCAN_DIR, root
# - validators.is_filename_cat_num(name) -> (catalogue_number:str|None, valid:bool)
# - validators.read_image_id(path) -> str|None

def att_loc_exist():
    """
    For each file in scan_root:
      - If the image comment contains an Image ID, write a row with:
        [attachment location, catalogue number, filename, found in DB csv, cat num equal, found in asset]
    Uses:
      files_csv = Z:\Data\Herbarium\VascularPlants\attachment_list.csv
      asset_csv = Z:\images\herbarium\asset_att_loc.csv
    Writes:
      Z:\Data\Herbarium\VascularPlants\attachment_list_att_loc_exist.csv
    """
    scan_root = Path(SCAN_DIR) if SCAN_DIR else root
    files_csv = Path(r"Z:\Data\Herbarium\VascularPlants\attachment_list.csv")
    asset_csv = Path(r"Z:\images\herbarium\asset_att_loc.csv")

    # Load base CSV for DB checks (image_id -> row index)
    if not files_csv.exists():
        log.error("Files CSV not found: %s", files_csv)
        return

    try:
        with files_csv.open(newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            try:
                base_header = next(reader)
            except StopIteration:
                log.error("Files CSV is empty: %s", files_csv)
                return
            base_rows = [row for row in reader]
    except Exception:
        log.exception("Failed to read files CSV: %s", files_csv)
        return

    # Build lookup by image ID (column index 3 in your layout)
    imageid_to_idx: dict[str, int] = {}
    for i, row in enumerate(base_rows):
        imgid = row[3].strip() if len(row) >= 4 else ""
        if imgid:
            imageid_to_idx[imgid] = i

    # Load asset attachment locations (column 0 = attachment location)
    asset_att_locs: set[str] = set()
    if asset_csv.exists():
        try:
            with asset_csv.open(newline="", encoding="utf-8") as fh:
                reader = csv.reader(fh)
                for row in reader:
                    if row and row[0].strip():
                        asset_att_locs.add(row[0].strip())
        except Exception:
            log.exception("Failed to read asset CSV: %s", asset_csv)
    else:
        log.warning("Asset CSV not found, 'found in asset' will be 'no': %s", asset_csv)

    # Prepare output
    out_header = [
        "attachment location",
        "catalogue number",
        "filename",
        "found in DB csv",
        "cat num equal",
        "found in asset",
    ]
    out_rows: list[list[str]] = []

    # Iterate the scan folder; keep only files with Image ID in comment
    imageid_regex = re.compile(r"(?:ImageID|Image ID)\s*:\s*(\S+)", flags=re.IGNORECASE)

    for path in scan_root.glob("*"):
        if not path.is_file():
            continue

        # Extract catalogue number from filename using your helper
        catalogue_number, _valid = validators.is_filename_cat_num(path.name)
        file_cat = (catalogue_number or "").strip()

        # Extract Image ID from the embedded comment
        comment = validators.read_image_id(path) or ""
        m = imageid_regex.search(comment)
        image_id_val = m.group(1).strip() if m else ""

        # Only process if an Image ID exists
        if not image_id_val:
            continue

        # found in DB csv?
        found_in_db = "yes" if image_id_val in imageid_to_idx else "no"

        # cat num equal? Only meaningful if found in DB
        if found_in_db == "yes":
            idx = imageid_to_idx[image_id_val]
            # Column 1 in your current layout stores the catalogue number reference
            csv_cat_raw = base_rows[idx][1].strip() if len(base_rows[idx]) >= 2 else ""
            # Compare stems to ignore extensions if the CSV stores filenames
            csv_cat_stem = Path(csv_cat_raw).stem if csv_cat_raw else ""
            cat_num_equal = "yes" if (file_cat and csv_cat_stem == file_cat) else "no"
        else:
            cat_num_equal = "no"

        # found in asset?
        found_in_asset = "yes" if image_id_val in asset_att_locs else "no"

        # Append row in the requested order
        out_rows.append([
            image_id_val,   # attachment location
            file_cat,       # catalogue number
            path.name,      # filename
            found_in_db,    # found in DB csv
            cat_num_equal,  # cat num equal
            found_in_asset, # found in asset
        ])

    # Write the new CSV next to the original
    out_csv = files_csv.with_name(f"{files_csv.stem}_att_loc_exist.csv")
    try:
        with out_csv.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(out_header)
            writer.writerows(out_rows)
        log.info("Wrote summary CSV: %s", out_csv)
    except Exception:
        log.exception("Failed to write summary CSV: %s", out_csv)
