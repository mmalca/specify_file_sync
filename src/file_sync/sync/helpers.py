from pathlib import Path
from PIL import Image
import piexif


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