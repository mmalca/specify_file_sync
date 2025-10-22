import requests
import mimetypes
import os
from logs.logging_setup import setup_run_logger
import logging
from pathlib import Path
from dotenv import load_dotenv

import re
import json


# Set up logging
logfile = setup_run_logger(level="DEBUG")
log = logging.getLogger(__name__)

# Load environment variables from .env file
ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


# Create a new session
def new_session():
    return requests.Session()


# Login to Specify API
def api_login():#, username, password, collection_id):
    session = new_session()

    log.info(f"Logging in to Specify API using {os.getenv("API_USER")}...")
    endpoint = "/context/login/"
    login_url = os.getenv("API_DOMAIN") + endpoint   
    
    # Get CSRF token
    get_response = session.get(login_url)
    csrf_token_login = get_response.cookies.get('csrftoken')
    login_info = {'username': os.getenv("API_USER"), 'password': os.getenv("API_PASS"), 'collection': int(os.getenv("API_COLLECTIONID"))}
    headers = {"X-CSRFToken": csrf_token_login}

    response = session.put(login_url, json=login_info, headers=headers)
    if response.status_code == 204:
        log.info("Login successful.")
        return session
    else:
        log.error(f"Login failed with status code {response.status_code}.")
        if response.text:
            log.error(f"Response text: {response.text}")
            return None
    

# Get upload token for uploading file by file name
# Returns csrf token
def api_file_token(session, filename):
    log.info(f"Getting attachment token for {filename}...")
    params = {"filename": filename}
    att_token = "/attachment_gw/get_token/"
    att_token_url = os.getenv("API_DOMAIN") + att_token
    response = session.get(att_token_url,params=params)
    if response.status_code != 200:
        log.error(f"Failed to get attachment token with status code {response.status_code}.")
    else:
        log.info("successfully got attachment token.")
        log.info(f"Response: {response.text}")
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
    log.info(f"Attachment location: {attachmentLocation}")
    with open(os.getenv("ATT_LOCATION"), "a", encoding="utf-8") as f:
        f.write(f"\n{attachmentLocation}\n")
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
        return
    else:
        log.info("---> Successfully uploaded to asset server.")
        return attachmentLocation

### CURRENTLY NOT NEEDED  ###
def asset_server_delete_attachment(delete_from_asset_url, attachmentLocation, collection_asset, delete_token):
    log.info(f"Deleting {attachmentLocation} from asset server...")
        
    data = {
        "token": delete_token,
        "type": "O",
        "coll": collection_asset,
        "filename": attachmentLocation,
    }

    response = requests.post(delete_from_asset_url, data=data)
    if response.status_code != 200:
        log.error(f"Failed to delete file from asset server with status code {response.status_code}.")
        log.error(f"Response text: {response.text}")
        return
    else:
        log.info(f"Successfully deleted file from asset server.")
        return attachmentLocation
    

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
            "mimetype": mimeType,                      
            "origfilename": filename,                  
            "title": filename,                         
            "ispublic": True,
            "tableid": 1,
        }
    }
    return attachmentResource0


def get_current_attachment_list(session, cat_num):

    pass

# Add the new attachment resource to the existing list of collectionobjectattachment
# Returns full list of attachment resources, including the new one
def create_full_attachment_resource(new_attachment_resource):
    full_attachment_resources = get_current_attachment_list

    # Get the old attachment resources from the collection object


    full_attachment_resources.append(new_attachment_resource)
    return full_attachment_resources

# Get collection object parameters by catalog number and collection id
# Returns collection object id and version
def api_get_coll_obj_params(session, cat_num, collectionid):
    log.info(f"Getting collection object parameters for catalog number {cat_num} in collection {collectionid}...")
    params = {"catalognumber": cat_num, "collection": collectionid}
    endp = f"/api/specify/collectionobject/"
    url_colobj = os.getenv("API_DOMAIN") + endp
    response = session.get(url_colobj, params=params)
    log.debug(f"Response status code: {response.status_code}")
    if response.status_code != 200:
        log.error(f" !!!! Failed to get collection object with status code {response.status_code}.")
        return None, None
    if not response.json()["objects"]:
        log.error(f" !!!! No collection object found for catalog number {cat_num}.")
        return None, None
    col_obj_id = response.json()["objects"][0]["id"]
    col_obj_version = response.json()["objects"][0]["version"]

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
        log.error(f" !!!! Failed to attach file to Collection Object with status code {response.status_code}.")
        log.error(f"Response text: {response.text}")
        return
    else:
        log.info("  ----->   Successfully attached file to Collection Object.")
        return col_obj_id


def api_col_obj_delete_attach(session, cat_number, filename, delete_from_asset_url):
    params = { "catalognumber": cat_number, "collection": int(os.getenv("API_COLLECTIONID")) }
    endp = f"/api/specify/collectionobject/"
    url_colobj = os.getenv("API_DOMAIN") + endp
    response = session.get(url_colobj, params=params)
    
    ### getting information about attachments for this catalog number ###
    current_col_obj_json = response.json()["objects"][0]
    attachments =  current_col_obj_json["collectionobjectattachments"]
    col_obj_id = current_col_obj_json["id"]
    log.info(f"Collection Object {cat_number} ID is: {col_obj_id}")
    attachment_location = None

    if not attachments:
        log.info(f"No attachments found for Collection Object {cat_number}.")

    else:
        for att in attachments:
            attachment_id = att['id']
            attachment_location = att['attachment']['attachmentlocation']
            orig_filename = att['attachment']['origfilename']

            # Pay attention - there is another attachment id, do not use is it: att['attachment']['id']
 
            if orig_filename == filename:
                # Delete 
                log.info(f"Found attachment {attachment_id} with filename {filename}, attachmentlocation {attachment_location} to delete.")

                col_obj_by_id_url = os.getenv("API_DOMAIN") + f"/api/specify/collectionobject/{col_obj_id}/"

                # Use the fetched Collection Object resource
                ##resource = col_obj_response.json()
                attach_count_before = len(attachments)
                ## current_attachment_to_delete = next((a for a in resource["collectionobjectattachments"] if a.get("id") == attachment_id),None)
                
                # Delete only the required attachment by id
                new_attachments = [a for a in attachments if a['id'] != attachment_id]
                attach_count_after = len(new_attachments)
                if (attach_count_after + 1) != attach_count_before:
                    log.error(f" !!!! Attachment count mismatch after deletion attempt. Aborting deletion of file {filename}.")
                    return attachment_location, attachments
                # Only send the attachments list and the current version to avoid updating other nested tables
                payload = {
                    "collectionobjectattachments": new_attachments,
                    "version": current_col_obj_json.get("version"),
                }
                headers = {
                    "X-CSRFToken": session.cookies.get("csrftoken"),
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
                deleted_col_obj_response = session.put(col_obj_by_id_url, json=payload, headers=headers)
                if deleted_col_obj_response.status_code != 200:
                    log.error(f" !!!! Failed to delete img {filename} from Collection Object with status code {deleted_col_obj_response.status_code}.")
                    log.debug(f"Response text: {deleted_col_obj_response.text}")
                    return attachment_location, attachments
                log.info(f" ---> Successfully deleted img {filename} from Collection Object.")
                
                
                ## delete_att_location = current_attachment_to_delete['attachment']['attachmentlocation']
                ## delete_token = api_file_token(session, delete_att_location)
                ## deleted_from_asset_server = asset_server_delete_attachment(delete_from_asset_url, delete_att_location, os.getenv("API_COLLECTIONASSET"), delete_token)

                # Returns the updated attachment location after uploadded
                return attachment_location, new_attachments
    return attachment_location, attachments


### CURRENTLY NOT NEEDED  ###
def check_filename_attached(session, cat_num, filename):
    log.info(f"Checking existing attachments for Collection Object {cat_num}...")
    endp = f"/api/specify/collectionobject/"
    url_colobj = os.getenv("API_DOMAIN") + endp
    params = { "catalognumber": cat_num, "collection": int(os.getenv("API_COLLECTIONID")) }
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

def attachment_to_col_object(file_path, cat_num ,session):
    log.info(f"---> Starting attachment process for file {file_path} to catalog number {cat_num}...")

    filename = file_path.name

    attachmentLocation, token = api_get_upload_params(session, filename)
    upload_settings = api_get_upload_settings(session)
    write_to_asset_url = upload_settings["write"]
    delete_from_asset_url = upload_settings["delete"]
    collection_asset = upload_settings["collection"]

    col_obj_id, col_obj_version = api_get_coll_obj_params(session, cat_num, int(os.getenv("API_COLLECTIONID")))
    if col_obj_id is None:
        log.error(f" !!!! Cannot proceed with attachment")
        return None
    asset_server_upload_attachment(write_to_asset_url, file_path, attachmentLocation, token, collection_asset)

    # Currently implemented for single attachment resource
    attachment_resource = create_attachment_resource(attachmentLocation, filename)
    attachment_resources = [attachment_resource]   # attachment_resources is a list of attachment resources

    

    # Delete the old attachment with the same filename (if exists)
    deleted_att_location, current_attachments_list = api_col_obj_delete_attach(session, cat_num, filename, delete_from_asset_url)
    
    # Start with the attachments returned from deletion step
    attachment_resources = current_attachments_list or []
    # Build the new attachment list by appending the new resource
    # but fetch the authoritative collection object resource first to get up-to-date versions
    col_obj_by_id_url = os.getenv("API_DOMAIN") + f"/api/specify/collectionobject/{col_obj_id}/"
    try:
        col_obj_response = session.get(col_obj_by_id_url, headers={"X-CSRFToken": session.cookies.get("csrftoken")})
    except Exception:
        col_obj_response = None

    if col_obj_response and col_obj_response.status_code == 200:
        resource = col_obj_response.json()
        current_list = resource.get("collectionobjectattachments", [])
        # Use server's canonical list, then append the new attachment resource
        current_list.append(attachment_resource)
        attachment_resources = current_list
        # use the authoritative version from the resource
        col_obj_version = resource.get("version", col_obj_version)
        log.info(f"Using collection object version from server: {col_obj_version}")
    else:
        # Fall back to the list we have and the previously fetched version
        attachment_resources.append(attachment_resource)
        log.warning("Could not fetch authoritative collection object before attaching; using local version/list.")

    attached = api_col_obj_attach(session, attachment_resources, col_obj_id, col_obj_version)
    if not attached:
        # log.error(f"Attachment process FAILED for file {file_path} to catalog number {cat_num}.")
        return None
    return attachmentLocation

