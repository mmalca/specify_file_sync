import requests
import mimetypes
import os
from logs.logging_setup import setup_run_logger
import logging
from pathlib import Path
from dotenv import load_dotenv

import re

# Set up logging
logfile = setup_run_logger(level="INFO")
log = logging.getLogger(__name__)

# Load environment variables from .env file
ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

#catalogue number
#cotaloger-possible
#file_path
#file name = os.path.basename(file_path)

# Create a new session
def new_session():
    return requests.Session()


# Login to Specify API
def api_login(session):#, username, password, collection_id):
    log.info(f"Logging in to Specify API using {os.getenv("API_USER")}...")
    endpoint = "/context/login/"
    login_url = os.getenv("API_DOMAIN") + endpoint   
    
    #Get CSRF token
    get_response = session.get(login_url)
    csrf_token_login = get_response.cookies.get('csrftoken')
    login_info = {'username': os.getenv("API_USER"), 'password': os.getenv("API_PASS"), 'collection': int(os.getenv("API_COLLECTIONID"))}
    headers = {"X-CSRFToken": csrf_token_login}

    response = session.put(login_url, json=login_info, headers=headers)
    if response.status_code == 200:
        log.info("Login successful.")
        log.info(f"Response: {response.text}")
    else:
        log.error(f"Login failed with status code {response.status_code}.")
        if response.text:
            log.error(f"Response text: {response.text}")


# Get upload token for uploading file by file name
# Returns csrf token
def api_attach_file_token(session, filename):
    log.info(f"Getting attachment token for {filename}...")
    params = {"filename": filename}
    att_token = "/attachment_gw/get_token/"
    att_token_url = os.getenv("API_DOMAIN") + att_token
    response = session.get(att_token_url,params=params)
    if response.status_code != 200:
        log.error(f"Failed to get attachment token with status code {response.status_code}.")
    else:
        log.info("successfully got attachment token.")
    csrf_token_tok = response.text
    return csrf_token_tok

# Get params for uploading file
# Returns attachmentLocation, token
def api_get_upload_params(session, filename):
    endp = "/attachment_gw/get_upload_params/"
    url_attachment = os.getenv("API_DOMAIN") + endp
    
    params = {"filenames": [filename]}
    
    headers = {
        "Accept": "application/json",
        "Referer": os.getenv("API_DOMAIN") + "/specify/view/collectionobject/0001000000/",
        "Origin": os.getenv("API_DOMAIN"),
        "X-CSRFToken": session.cookies.get("csrftoken"),
    }
    
    response = session.post(url_attachment, json=params, headers=headers)
    json_response = response.json()[0]
    attachmentLocation = json_response["attachmentLocation"]
    token = json_response["token"]

    return attachmentLocation, token


# Get upload settings
# Returns json with settings - write, read, delete urls, collection, etc.
def api_get_upload_settings(session):
    log.info("Getting upload settings...")
    att_set_endpoint = "/attachment_gw/get_settings/"
    att_set_url = os.getenv("API_DOMAIN") + att_set_endpoint
    response = session.get(att_set_url)
    if response.status_code != 200:
        log.error(f"Failed to get upload settings with status code {response.status_code}.")
        return None
    else:
        log.info("Successfully got upload settings.")
        return response.json()


# Upload file to asset server
###def upload_to_asset_server
def asset_server_upload_attachment(wr, file_path, attachmentLocation, token, collection_asset):
    log.info(f"Uploading {file_path} to asset server...")
    files = {"file": open(file_path, "rb")}
    data = {
        "token": token,
        "store": attachmentLocation,
        "type": "O",
        "coll": collection_asset,
    }

    response = requests.post(wr, files=files, data=data)
    if response.status_code != 200:
        log.error(f"Failed to upload to asset server with status code {response.status_code}.")
    else:
        log.info("Successfully uploaded to asset server.")


# Create and returns attachment resource dict
def create_attachment_resource(attachmentlocation, filename):
    log.info(f"Creating attachment resource for {filename}...")
    mimeType = mimetypes.guess_type(filename)[0]
    if mimeType is None:
        log.warning(f"Could not determine MIME type for {filename}. Using 'application/octet-stream' as default.")
        mimeType = "application/octet-stream"
    attachmentResource0 = {
        "ordinal": 0,
        "attachment": {
            "attachmentlocation": attachmentlocation,
            "mimetype": mimeType,                      # e.g. "image/jpeg"
            "origfilename": filename,                  # original file name
            "title": filename,                         # title (often same as filename)
            "ispublic": True,
            "tableid": 1,
        }
    }
    return attachmentResource0


# Get collection object parameters by catalog number and collection id
# Returns collection object id and version
##def get_coll_obj_params
def api_get_coll_obj_params(session, cat_num, collectionid):
    log.info(f"Getting collection object parameters for catalog number {cat_num} in collection {collectionid}...")
    params = {"catalognumber": cat_num, "collection": collectionid}
    endp = f"/api/specify/collectionobject/"
    url_colobj = os.getenv("API_DOMAIN") + endp
    response = session.get(url_colobj, params=params)
    log.debug(f"Response status code: {response.status_code}")
    if response.status_code != 200:
        log.error(f"Failed to get collection object with status code {response.status_code}.")
        return None, None

    col_obj_id = response.json()["objects"][0]["id"]
    log.info("Collection Object ID:", col_obj_id)
    col_obj_version = response.json()["objects"][0]["version"]
    log.info("Collection Object Version:", col_obj_version)

    return col_obj_id, col_obj_version



# Upload attachment to an existing Collection Object
def api_col_obj_attach(session, attach_resources, col_obj_id, col_obj_version):
    log.info(f"Attaching resources to Collection Object ID {col_obj_id}...")
    ### optional - to add verification of the catalog number ###
    url_coll_obj_att = f"{os.getenv("API_DOMAIN")}/api/specify/collectionobject/{col_obj_id}/"
    headers = {
        "X-CSRFToken": session.cookies.get("csrftoken"),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    json = {
        "collectionobjectattachments": attach_resources,
        "version": col_obj_version,
    }

    response = session.put(url_coll_obj_att, json=json, headers=headers)
    if response.status_code != 200:
        log.error(f"Failed to attach to Collection Object with status code {response.status_code}.")
        return False
    else:
        log.info("Successfully attached to Collection Object.")
        return True

def api_col_obj_delete_attach(session, attach_resource_id, col_obj_id, col_obj_version):
    #working on it on another file
    pass

def check_filename_attached(session, cat_num, filename):
    log.info(f"Checking existing attachments for Collection Object {cat_num}...")
    endp = f"/api/specify/collectionobject/"
    url_colobj = os.getenv("API_DOMAIN") + endp
    params = { "catalognumber": cat_num}
    response = session.get(url_colobj, params=params)

    response_json = response.json()
    attachments =  response_json["objects"][0]["collectionobjectattachments"]
    if len(attachments) < 1:
        log.info(f"No existing attachments found for Collection Object {cat_num}.")
        return False
    log.info(f"Found {len(attachments)} existing attachments.")
    for att in attachments:
        log.info(f"Attachment ID: {att['id']}, Original Filename: {att['attachment']['origfilename']}, attachmentlocation: {att['attachment']['attachmentlocation']}")
        if att['attachment']['origfilename'] == filename:
            log.info(f"File {filename} is already attached to Collection Object {cat_num}.")
            return True

def attachment_to_col_object(file_path, cat_num):
    log.info(f"Starting attachment process for file {file_path} to catalog number {cat_num}...")
    s = new_session()

    api_login(s)
    filename = file_path.name
    #print(f_n)
    #filename = os.path.basename(file_path)
    attach_token = api_attach_file_token(s, filename)#??
    attachmentLocation, token = api_get_upload_params(s, filename)
    upload_settings = api_get_upload_settings(s)
    write_to_asset_url = upload_settings["write"]
    collection_asset = upload_settings["collection"]

    asset_server_upload_attachment(write_to_asset_url, file_path, attachmentLocation, token, collection_asset)

    # currently implemented for single attachment resource
    attachment_resource = create_attachment_resource(attachmentLocation, filename)
    attachment_resources = [attachment_resource]   # attachment_resources is a list of attachment resources

    col_obj_id, col_obj_version = api_get_coll_obj_params(s, cat_num, int(os.getenv("API_COLLECTIONID")))

    is_filename_attached = check_filename_attached(s, cat_num, filename)
    if is_filename_attached:
        api_col_obj_delete_attach(s, attachment_resource['id'], col_obj_id, col_obj_version)
    attached = api_col_obj_attach(s, attachment_resources, col_obj_id, col_obj_version)


