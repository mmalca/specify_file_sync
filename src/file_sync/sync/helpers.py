from pathlib import Path
from PIL import Image
import piexif
import pandas as pd


XP_COMMENT_TAG = 0x9C9C


def set_image_id(image_path: Path, attachment_location: str) -> bool:
    """Write attachment location as Image ID in image metadata."""
    img = None  # Initialize img to None
    try:
        # Open the image
        img = Image.open(image_path)

        # Get existing EXIF data or create an empty dict if none exists
        exif_data = img.info.get('exif')
        if exif_data:
            exif_dict = piexif.load(exif_data)
        else:
            exif_dict = {}  # Start with a fresh dictionary

        # Ensure the main and Exif IFD dictionaries exist
        if 'Exif' not in exif_dict:
            exif_dict['Exif'] = {}

        # Create UserComment tag with the ID for better visibility in some viewers
        # Manually construct the UserComment tag for compatibility with older piexif versions
        if attachment_location is None:
            comment_str = ""
        else:
            comment_str = f"ImageID: {attachment_location}"
        # The UserComment tag requires a character code prefix (8 bytes)
        user_comment = b'ASCII\x00\x00\x00' + comment_str.encode('ascii')
        exif_dict['Exif'][piexif.ExifIFD.UserComment] = user_comment

        # Convert to bytes and save
        exif_bytes = piexif.dump(exif_dict)

        # Save with new metadata, preserving quality
        img.save(image_path, exif=exif_bytes, quality=100)
        #TODO: Make sure that image quality is preserved. Check if the file size might by smaller
        #print(f"Added Image ID {attachment_location} to {image_path.name}")
        img.close()
        return True

    except Exception as e:
        #log.error(f"Error setting Image ID for {image_path.name}: {str(e)}")
        if img:
            img.close()
        return False
    

    def clear_comment_field(filename) -> bool:
        """
        Remove EXIF UserComment (ExifIFD.UserComment) and XPComment (0th IFD, 0x9C9C)
        without touching other EXIF fields. Uses lossless EXIF reinsertion for JPEG/TIFF.
        """
        image_path = Path(os.getenv("SCAN_DIR") + '\\' + filename)
        suffix = image_path.suffix.lower()

        # Read bytes once for lossless update
        with image_path.open("rb") as f:
            data = f.read()

        # Load existing EXIF, or initialize a valid empty structure
        try:
            exif = piexif.load(data)
        except Exception:
            exif = {"0th":{}, "Exif":{}, "GPS":{}, "1st":{}, "Interop":{}, "thumbnail": None}

        # Ensure dicts exist
        exif.setdefault("0th", {})
        exif.setdefault("Exif", {})

        # Remove both comment locations if present
        exif["Exif"].pop(piexif.ExifIFD.UserComment, None)  # UserComment
        exif["0th"].pop(XP_COMMENT_TAG, None)               # XPComment

        exif_bytes = piexif.dump(exif)

        # Prefer lossless insert for JPEG/TIFF
        if suffix in (".jpg", ".jpeg", ".tif", ".tiff"):
            new_bytes = piexif.insert(exif_bytes, data)
            with image_path.open("wb") as f:
                f.write(new_bytes)
            return True

        # Fallback for other formats (may not carry EXIF or may ignore it)
        with Image.open(image_path) as img:
            img.save(image_path, exif=exif_bytes)
        return True
    

    def fix_delete_image_id_and_unattach():
        # Load Excel file
        df = pd.read_excel(f"Z:\\Data\\Herbarium\\VascularPlants\\image_upload_verification\\tofix.xlsx")

        # Select the column by name (change "ColumnName" to your actual name)
        for i in range(len(df)):
            attachment_location = df.iloc[i, 0]   # Column A (0 index)
            catalogue_number = df.iloc[i, 1]   # Column B (1 index)
            filename = df.iloc[i, 2]   # Column C (2 index)

            # Remove Image ID from EXIF
            if attachment_location:
                print(f"Removing Image ID from file EXIF: {attachment_location}")
                clear_comment_field(filename)

            # detach from catalogue number in specify
            s = client.api_login()
            client.api_col_obj_delete_attach(s, catalogue_number, filename, None, attachment_location)

            print (f"Unattached file {filename} from catalogue number {catalogue_number} in Specify.")
        s.close()
        print("Done.")
