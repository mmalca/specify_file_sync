from api import client
from sync import controller
from sync import helpers
from sync import fixes

import os

def main():
    controller.sync_files()

main()