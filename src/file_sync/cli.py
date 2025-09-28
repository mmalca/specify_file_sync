from api import client

def main():
    file_path = "C:\\Apps\\pic40.jpg"
    cat_num = "0001000000"
    client.attachment_to_col_object(file_path, cat_num)

if __name__ == "__main__":
    main()