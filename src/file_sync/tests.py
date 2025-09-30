import requests


domain = "https://hujinnhc.specifycloud.org"
session = requests.Session()


###   LOGIN   ###
endpoint = "/context/login/"
method = 'GET'
login_url = domain + endpoint
collection_id = 131073 # s.get_collection_id("Vascular")
username = "ImageAgent"
password = "HvY4hpU9Hg34"
#username = "APIReader"
#password = "QEWA6u"


#Get CSRF token
get_response = session.get(login_url)
csrf_token_login = get_response.cookies.get('csrftoken')

login_info = {'username': username, 'password': password, 'collection': collection_id}
headers = {"X-CSRFToken": csrf_token_login}
print("CSRF token before login:", csrf_token_login)

response = session.put(login_url, json=login_info, headers=headers)
csrf_token = response.cookies.get('csrftoken')
print("CSRF token after login:", csrf_token)

#print("Login status code:", response.status_code)
#print("Login response:", response.text)

#headers = {"X-CSRFToken": updated_csrf_token}


##### ATTACHMENTS info #####

# endp = "/api/specify/attachment/"
# url_attachment_info = domain + endp
# response = session.get(url_attachment_info)

#print("Upload status code:", response.status_code)
#print("Upload response:", response.text)


################################################################################
##### ATTACHMENTS info for specific collection object, by catalogue number #####


cat_number = "0001000000"
params = { "catalognumber": cat_number}
endp = f"/api/specify/collectionobject/"
url_colobj = domain + endp
response = session.get(url_colobj, params=params)

#print("resp data status code:", response.status_code)
#print("resp data response:", response.text)

### getting information about attachments for this catalog number ###
response_json = response.json()
attachments =  response_json["objects"][0]["collectionobjectattachments"]
#print("Attachments:", attachments)

if not attachments:
    print("No attachments found.")
else:
    print(f"Number of attachments for catalog number {cat_number} is --> {len(attachments)}")
    for att in attachments:
        
        #print(f"col obj attach: {att['attachment']['collectionobjectattachments']}")
        print(f"Attachment: {att['id']}")
        print(f"Attachment location: {att['attachment']['attachmentlocation']}")
        print(f"Orig file name: {att['attachment']['origfilename']}")
        print(f"Attachment URI: {att['attachment']['resource_uri']}")
        print(f"Attachment ID: {att['attachment']['id']}")
        #params = {"version": att['version']}
        if att['attachment']['origfilename'] == "pic40.jpg":
            #delete 
            print("Would delete attachment here")
            url=f"{domain}/api/specify/collectionobjectattachment/{att['id']}/"
            del_response = session.delete(url, headers={"X-CSRFToken": csrf_token})
            print(f"Delete response status code for attachment ID {att['attachment']['id']}:", del_response.status_code)
            print(f"Delete response text for attachment ID {att['attachment']['id']}:", del_response.text)



#TEST - getting attachments list ##############################################

'''
params = {
    "limit": 20,
    "offset": 0,
    "domainfilter": "false"
}
endp = "/api/specify/collectionobjectattachment/"
#response = session.get(domain + endp, params=params, headers=headers)
'''
###############################################################################
'''


#### UPLOAD ATTACHMENT ####

file = "C:\\Apps\\pic40.jpg"
att_set_endpoint = "/attachment_gw/get_settings/"
#att_endpoint = "/attachment_gw/get_upload_params/"
att_set_url = domain + att_set_endpoint


#Get CSRF token for upload
#response = session.get(att_url)
#csrf_token_upload = get_response.cookies.get('csrftoken')
#print("CSRF token for upload:", csrf_token_upload)
#################
#att_response = session.get(att_url)
#print("Attachment get params status code:", att_response.status_code)
#print("Attachment get params response:", att_response.text)
#csrf_token_up = att_response.cookies.get('csrftoken')
#print("CSRF token for upload:", csrf_token_up)

#get_response = session.get(login_url)
#csrf_token = get_response.cookies.get('csrftoken')

headers = {"accept": "application/json",
           "X-CSRFToken": csrf_token}

headers = {"X-CSRFToken": csrf_token}


params = {"filename": file}

data = {'csrfmiddlewaretoken': csrf_token}

response = session.get(att_set_url)#, data=data, headers=headers, params=params)
#print the csrf:
csrf_token_up = response.cookies.get('csrftoken')
print("CSRF token for upload:", csrf_token_up)

#data = response.json()
#attachmentlocation = data.get("attachmentlocation")
#token = data.get("token")
att_read = ""
att_write = ""
att_delete = ""
att_test_key = ""

print("Attachment get settings status code:", response.status_code)
if response.status_code!=403:
    print("Attachment get settings response:", response.text)
    att_read = response.json().get("read")
    print("Read:", att_read)
    att_write = response.json().get("write")
    print("Write:", att_write)
    att_delete = response.json().get("delete")
    print("Delete:", att_delete)
    att_test_key = response.json().get("testkey")
    print("Test Key:", att_test_key)


att_token = "/attachment_gw/get_token/"
att_token_url = domain + att_token
response = session.get(att_token_url, headers=headers)#, data=data, headers=headers, params=params)

print("Attachment att_token_url:", response.status_code)
if response.status_code!=403 and response.status_code!=500: 
    print("Attachment att_token_url:", response.text)
    csrf_token_tok = response.cookies.get('csrftoken')
    print("CSRF token att_token_url:", csrf_token_tok)


file = "C:\\Apps\\pic40.jpg"
files = {
    "file": ("pic40.jpg", open(file, "rb"), "image/jpeg")
}

params = {"filename": files}

att = session.get(domain + att_endpoint, files=files, headers=headers)
print("Attachment get params status code:", att.status_code)
print("Attachment get params response:", att.text)


# params = {
#     "file": file,
#     "token": att_token,
#     "store": att_location,
#     "type": '0',
#     "coll": collection_id
# }
#resp = requests.post(att_location, data=params)
#print("Attachment upload response:", resp.text)'''

'''
att_endpoint = "/attachment_gw/get_upload_params/"
att_url = domain + att_endpoint

response = session.post(att_url,file)#, data=data, headers=headers, params=params)

print("Attachment upload params status code:", response.status_code)
if response.status_code!=403 and response.status_code!=500: 
    print("Attachment upload params response:", response.text)
    #print the request csrf token:'''




##### delete attachment #####


