import sys
import os
import requests
from urllib.parse import urlparse, unquote
import pika
import json
from pyspark.sql import SparkSession
from pyspark.sql import Row
from SPARQLWrapper import SPARQLWrapper, JSON as SPARQL_JSON

IMAGES_DIR = '/app/data/images'
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

def get_sparql_results(endpoint_url, query):
    """
    Exécute la requête SPARQL et renvoie les résultats sous forme de liste de Rows pour la création d'un DataFrame Spark.
    
    :param endpoint_url: URL de l'endpoint SPARQL
    :param query: Requête SPARQL
    :return: Liste de Rows
    """
    user_agent = "WDQS-example Python/%s.%s" % (
        sys.version_info[0],
        sys.version_info[1]
    )
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(SPARQL_JSON)
    results = sparql.query().convert()

    rows = [Row(**{key: value['value'] for key, value in result.items()}) for result in results["results"]["bindings"]]
    return rows

def download_image(url):
    """
    Télécharge une image depuis une URL et la sauvegarde dans le dossier spécifié.
    
    :param url: URL de l'image à télécharger
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        request = requests.get(url, allow_redirects=True, headers=headers, stream=True)
        request.raise_for_status()  # Lève une exception en cas de réponse non réussie

        filename = unquote(urlparse(url).path.split('/')[-1])
        filepath = os.path.join(IMAGES_DIR, filename)
        
        if os.path.exists(filepath):
            print(f"Image déjà téléchargée : {filename}")
            send_to_queue(filename)
            return filename  # Retourne le nom du fichier
        else:
            with open(filepath, 'wb') as f:
                for chunk in request.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            with open(filepath, 'rb') as f:
                response = requests.post("http://web_container:5000/save_image", files={'image': f})
                
                if response.status_code == 200:
                    print(f"Image sauvegardée : {filename}")
                    send_to_queue(filename)
                    return filename
                else:
                    raise Exception("Error: {response.status_code}")
    except Exception as e:
        print(f"Échec du téléchargement de l'image : {url} - Erreur : {e}")
        return None

def send_to_queue(file_path):
    """
    Envoie une liste de chemins de fichiers image à RabbitMQ.
    
    :param file_paths: Liste de chemins de fichiers image
    """
    # Utilisation des paramètres par défaut pour la connexion
    parameters = pika.URLParameters("amqp://guest:guest@rabbitmq_container:5672?connection_attempts=10&retry_delay=10")

    # Utilisation de try-except pour gérer les exceptions de connexion
    try:
        # Connection au serveur RabbitMQ
        with pika.BlockingConnection(parameters) as connection:
            channel = connection.channel()
            # Déclaration de la file d'attente
            channel.queue_declare(queue='image_files')

            # Envoi des données à la file d'attente
            if file_path:  # On s'assure que le chemin n'est pas None
                channel.basic_publish(exchange='',
                                        routing_key='image_files',
                                        body=json.dumps(file_path))
                print(f"Message envoyé à la file d'attente : {file_path}")
    except Exception as e:
        print(f"Échec de la connexion à RabbitMQ : {e}")

if __name__ == "__main__":
    spark = SparkSession.builder.appName("DataCollectionApp").getOrCreate()

    endpoint_url = "https://query.wikidata.org/sparql"
    query = """
    SELECT DISTINCT ?grandeville ?grandevilleLabel ?pays ?paysLabel ?image {
        ?grandeville wdt:P31 wd:Q1549591;
        wdt:P17 ?pays;
        wdt:P18 ?image.
        SERVICE wikibase:label { bd:serviceParam wikibase:language "fr". }
    }
    LIMIT 20
    """
    sparql_results = get_sparql_results(endpoint_url, query)

    # Création d'un DataFrame Spark à partir des résultats SPARQL
    spark_df = spark.createDataFrame(sparql_results)

    # Téléchargement des images et envoi des chemins à RabbitMQ
    file_paths = spark_df.rdd.map(lambda row: download_image(row.image)).collect()
    print("File paths:", file_paths)

    spark.stop()
