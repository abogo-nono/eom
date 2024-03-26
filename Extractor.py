from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS


def convert_decimal_degrees(degree, minutes, seconds, direction):
    decimal_degrees = degree + minutes / 60 + seconds / 3600
    # A value of "S" for South or West will be multiplied by -1
    if direction == "S" or direction == "W":
        decimal_degrees *= -1
    return decimal_degrees


def create_google_maps_url(gps_coords):
    # Exif data stores coordinates in degree/minutes/seconds format. To convert to decimal degrees.
    # We extract the data from the dictionary we sent to this function for latitudinal data.
    dec_deg_lat = convert_decimal_degrees(float(gps_coords["lat"][0]), float(gps_coords["lat"][1]),
                                          float(gps_coords["lat"][2]), gps_coords["lat_ref"])
    # We extract the data from the dictionary we sent to this function for longitudinal data.
    dec_deg_lon = convert_decimal_degrees(float(gps_coords["lon"][0]), float(gps_coords["lon"][1]),
                                          float(gps_coords["lon"][2]), gps_coords["lon_ref"])
    # We return a search string which can be used in Google Maps
    return f"https://maps.google.com/?q={dec_deg_lat},{dec_deg_lon}"


def single_image_extractor(image: str):
    """
        This function is used to extract metadata in a single jpg image
        :param image: the file to process
        :return: extracted data
    """

    try:
        # Open the image file. We open the file in binary format for reading.
        image = Image.open(image)
    except IOError:
        print("File format not supported!")
        return None

    if image.format in ['JPEG', 'JPG']:

        # create a dictionary to store extracted data
        extracted_data = {}

        # gps coordonate
        gps_coords = {}

        # The ._getexif() method returns a dictionary. .items() method returns a list of all dictionary keys and values.
        gps_coords = {}

        if image._getexif() is None:
            print(f"{image} contains no exif data.")
            return None

        for tag, value in image._getexif().items():
            # If you print the tag without running it through the TAGS.get() method you'll get numerical values for
            # every tag. We want the tags in human-readable form. You can see the tags and the associated decimal
            # number in the exif standard here: https://exiv2.org/tags.html
            tag_name = TAGS.get(tag)

            if tag_name:
                # print(tag_name)
                extracted_data[tag_name] = value

            if tag_name == "GPSInfo":
                for key, val in value.items():
                    # We add Latitude data to the gps_coord dictionary which we initialized in line 110.
                    if GPSTAGS.get(key) == "GPSLatitude":
                        gps_coords["lat"] = val

                    # We add Longitude data to the gps_coord dictionary which we initialized in line 110.
                    elif GPSTAGS.get(key) == "GPSLongitude":
                        gps_coords["lon"] = val

                    # We add Latitude reference data to the gps_coord dictionary which we initialized in line 110.
                    elif GPSTAGS.get(key) == "GPSLatitudeRef":
                        gps_coords["lat_ref"] = val

                    # We add Longitude reference data to the gps_coord dictionary which we initialized in line 110.
                    elif GPSTAGS.get(key) == "GPSLongitudeRef":
                        gps_coords["lon_ref"] = val

        # We print the longitudinal and latitudinal data which has been formatted for Google Maps. We only do so if
        # the GPS Coordinates exists.
        if gps_coords:
            google_map_link = create_google_maps_url(gps_coords)
            # print(google_map_link)

            # add google map url to the extracted data
            extracted_data['GoogleMapLink'] = google_map_link

            gps_coords_string = []
            for item in gps_coords.values():
                gps_coords_string.append(item)

            extracted_data['GPSInfo'] = gps_coords_string

        return extracted_data



def multi_image_extractor(path: str, images: dict) -> dict:
    """
    This function is used to extract metadata in a list of images

    :param path   : directory of the images
    :param images : list of image to extract data
    :return       : dictionary of metadata of all image in the list
    """

    # dictionary that contain metadata of all the image in the list of images passed
    extracted_data = {}

    for key, value in images.items():
        # print(f"{key}: {value}")
        image_path = path + '/' + value
        extracted_data[key] = single_image_extractor(image_path)

    return extracted_data


def remove_image_metadata(file: str):
    try:
        image = Image.open(file)
    except IOError:
        print("File format not supported!")
        return None

    if image.format in ['JPEG', 'JPG']:
        # We get the exif data from the which we'll overwrite
        img_data = list(image.getdata())

        # We create a new Image object. We initialise it with the same mode and size as the original image.
        img_no_exif = Image.new(image.mode, image.size)

        # We copy the pixel data from img_data.
        img_no_exif.putdata(img_data)

        # We save the new image without exif data. The keyword argument exif would've been used with the exif data if you
        # wanted to save any. We overwrite the original image.
        img_no_exif.save(file)
        return True



def multi_remove_image_metadata(path, images):
    removed_list = {}
    
    for key, value in images.items():
        # print(f"{key}: {value}")
        image_path = path + '/' + value
        removed_list[key] = remove_image_metadata(image_path)

    return removed_list


# data = multi_image_extractor(
#     {1: '../images/IMG_20240309_021833_129.jpg', 2: '../images/IMG_20240309_021833_129.jpg'})
# print(f"{data}")
