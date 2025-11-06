from api import client
from sync import controller
from sync import helpers

def main():
    controller.sync_files()
    #controller.files_list_to_csv()
    #helpers.fix_delete_image_id_and_unattach()
main()