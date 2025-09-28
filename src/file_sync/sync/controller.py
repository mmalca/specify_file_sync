import os
from logs.logging_setup import setup_run_logger
import logging
from pathlib import Path
from dotenv import load_dotenv

from api import client


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
    for p in it:
        if p.is_file():
            log.info(f"FILE: {p.name}")      # print p for full path instead of file name
            count += 1
            print(p)
            client.update_file_in_specify(p.name, p)


    log.info(f"Found {count} files under {root}")