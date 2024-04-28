import os
import sys
from PIL import Image
from PIL.ExifTags import TAGS
import json

def get_exif_data(image_path):
    """
    Extrait les métadonnées EXIF d'une image.
    
    :param image_path: Chemin de l'image
    :return: Dictionnaire contenant les métadonnées
    """
    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            # Les données EXIF peuvent être None si aucune n'est trouvée
            if exif_data is not None:
                # Convertit les valeurs EXIF en un format plus lisible
                exif = {
                    Image.ExifTags.TAGS[k]: v
                    for k, v in exif_data.items()
                    if k in Image.ExifTags.TAGS and isinstance(v, (str, int, float))
                }
                # Ajoute des informations supplémentaires
                exif['File Size'] = os.path.getsize(image_path)
                exif['Image Format'] = img.format
                exif['Image Size'] = img.size
                exif['Orientation'] = exif.get('Orientation', 'Undefined')
                return exif
            else:
                return {}
    except Exception as e:
        print(f"Erreur lors de l'extraction des métadonnées : {e}")
        return {}

def save_metadata(image_path, exif_data):
    """
    Sauvegarde les métadonnées dans un fichier JSON.
    
    :param image_path: Chemin de l'image
    :param exif_data: Dictionnaire contenant les métadonnées
    """
    metadata = []
    filename = f"metadata_{os.path.basename(image_path)}.json"
    metadata.append({
        'Filename': filename,
        'Metadata': exif_data
    })
    with open(filename, 'w') as f:
        json.dump(metadata, f, indent=4)

if __name__ == "__main__":
    image_path = sys.argv[1]
    metadata = get_exif_data(image_path)
    save_metadata(image_path, metadata)
    print(f"Métadonnées extraites et sauvegardées dans {os.path.basename(image_path)}")
