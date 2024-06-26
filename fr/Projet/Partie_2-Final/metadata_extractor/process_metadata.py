import os
import sys
import requests
import urllib.parse
from PIL import Image
import json
import shutil
    
def get_exif_data(image_path):
    """
    Extrait les métadonnées EXIF d'une image.
    
    :param image_path: Chemin de l'image
    :return: Dictionnaire contenant les métadonnées
    """
    try:
        # Define the URL for the Flask service
        encoded_string = urllib.parse.quote(image_path, safe='/', encoding=None, errors=None)
        webvolume_address = os.environ.get('WEBVOLUME_ADDRESS', 'web_container')
        url = f'http://{webvolume_address}:5000/getfile/' + encoded_string

        images_folder = '/images'
        image_fullpath = os.path.join(images_folder, image_path)
        if not os.path.exists(images_folder):
            os.makedirs(images_folder)
        
        try:
            # Send a GET request to the Flask service
            response = requests.get(url, stream=True)   
        except Exception as e:
            return f"Erreur lors de la requête : {e}"
        
        # Check if the request was successful
        if response.status_code == 200:
            try:
                # Save the image
                with open(image_fullpath, 'wb') as f:
                    response.raw.decode_content = True
                    shutil.copyfileobj(response.raw, f)
            except Exception as e:
                return f"Erreur lors de la sauvegarde de l'image : {e}"

            try:
                img = Image.open(image_fullpath)
                exif_data = img.getexif()   
            except Exception as e:
                return f"Erreur lors de l'ouverture de l'image : {e}"

            # Get EXIF data
            if exif_data is not None:
                try:      
                    # Convertit les valeurs EXIF en un format plus lisible
                    exif = {
                        Image.ExifTags.TAGS[k]: v
                        for k, v in exif_data.items()
                        if k in Image.ExifTags.TAGS and isinstance(v, (str, int, float))
                    }
                    # Ajoute des informations supplémentaires
                    exif['File Size'] = os.path.getsize(image_fullpath)
                    exif['Image Format'] = img.format
                    exif['Image Size'] = img.size
                    exif['Orientation'] = exif.get('Orientation', 'Undefined')
                    return exif
                except Exception as e:
                    return f"Erreur lors de la conversion des métadonnées : {e}"
            else:
                return {}
                
        else:
            print(f'Request failed with status code {response.status_code}')
        
    except Exception as e:
        print(f"Erreur lors de l'extraction des métadonnées : {e}")
        return e.__str__()

def save_metadata(image_path, exif_data):
    """
    Sauvegarde les métadonnées dans un fichier JSON.
    
    :param image_path: Chemin de l'image
    :param exif_data: Dictionnaire contenant les métadonnées
    """
    metadata = []
    filename = f"metadata_{os.path.basename(image_path)}.json"
    filename = filename.split(".")[0] + ".json"
    
    metadata.append({
        'Filename': image_path,
        'Metadata': exif_data
    })
    with open(os.path.join("metadata", filename), 'w') as f:
        json.dump(metadata, f, indent=4)

if __name__ == "__main__":
    image_path = sys.argv[1]
    image_path = image_path.replace('"', "")
    
    metadata = get_exif_data(image_path)
    save_metadata(image_path, metadata)
    print(f"Métadonnées extraites et sauvegardées dans {os.path.basename(image_path)}")
