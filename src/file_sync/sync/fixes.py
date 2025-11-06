from api import client
from sync import validators

import pandas as pd
from pathlib import Path
import csv
import os
from logs.logging_setup import setup_run_logger
import logging
import re


# Set up logging
logfile = setup_run_logger(level="DEBUG")
log = logging.getLogger(__name__)

SCAN_DIR = os.getenv("SCAN_DIR")
root = Path(SCAN_DIR)


def fix_delete_image_id_and_unattach():
    # Load Excel file
    df = pd.read_excel(f"Z:\\Data\\Herbarium\\VascularPlants\\image_upload_verification\\tofix.xlsx", dtype=str, engine='openpyxl')
    count_image_id = 0
    count_unattached = 0

    # Select the column by name (change "ColumnName" to your actual name)
    for i in range(len(df)):
        attachment_location = df.iloc[i, 0]   # Column A (0 index)
        catalogue_number = df.iloc[i, 1]   # Column B (1 index)
        filename = df.iloc[i, 2]   # Column C (2 index)

        # image_id = validators.read_image_id(Path(os.getenv("SCAN_DIR") + '\\' + filename))
        # # Remove Image ID from EXIF
        # if image_id:
        #     print(f"Removing Image ID from file EXIF: {attachment_location}")
        #     cleared_comment = clear_comment_field(filename)
        #     if cleared_comment:
        #         count_image_id += 1

        # detach from catalogue number in specify
        s = client.api_login()
        x, y = client.api_col_obj_delete_attach(s, catalogue_number, filename, None, attachment_location)
        if x is None and y is None:
            print (f"Skipping unattaching file {filename} from catalogue number {catalogue_number} in Specify.")
        else:
            count_unattached += 1
            print (f"Unattached file {filename} from catalogue number {catalogue_number} in Specify.")
    s.close()
    print(f"\nTotal Image IDs removed from EXIF: {count_image_id}")
    print(f"Total files unattached in Specify: {count_unattached}") 
    print("Done.")



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