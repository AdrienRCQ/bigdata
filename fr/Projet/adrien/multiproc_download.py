import time
import requests
import sys
import os
import pandas as pd
from SPARQLWrapper import SPARQLWrapper, JSON
import requests
import shutil
from urllib.parse import urlparse, unquote
import queue
import multiprocessing as mp
import pika
from flask import Flask, request, send_from_directory


app = Flask(__name__)

IMAGES_DIR = 'images'
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

# code pour la connexion à RabbitMQ et le téléchargement des images...

@app.route('/images/<path:filename>', methods=['GET'])
def get_image(filename):
    """Renvoie l'image demandée."""
    return send_from_directory(IMAGES_DIR, filename)

@app.route('/request', methods=['POST'])
def handle_request():
    """Traite la requête et renvoie les images demandées."""
    request_data = request.get_json()
    image_urls = request_data.get('image_urls')
    if image_urls:
        # Télécharge les images demandées
        downloaded_images = [download_image(url) for url in image_urls]
        # Envoie les noms des images téléchargées à RabbitMQ
        send_to_rabbitmq(downloaded_images)
        # Renvoie une réponse indiquant que la requête a été traitée avec succès
        return {'status': 'success'}
    else:
        # Renvoie une réponse indiquant que la requête est invalide
        return {'status': 'error', 'message': 'Invalid request'}
    

def get_sparql_results(endpoint_url, query):
    """
    Exécute la requête SPARQL et renvoie les résultats.
    
    :param endpoint_url: URL de l'endpoint SPARQL
    :param query: requête SPARQL
    :return: résultats de la requête
    """
    endpoint_url = "https://query.wikidata.org/sparql"

    user_agent = "WDQS-example Python/%s.%s" % (
        sys.version_info[0],
        sys.version_info[1],
    )
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()

def download_image(url):
    """
    Télécharge une image depuis une URL et la sauvegarde dans le dossier spécifié.
    
    :param url: URL de l'image à télécharger
    """

    headers = {"User-Agent": "Mozilla/5.0"}
    request = requests.get(url, allow_redirects=True, headers=headers, stream=True)
    
    filename = os.path.join(IMAGES_DIR, unquote(urlparse(url).path.split('/')[-1]))
    
    # Check if the image already exists
    if os.path.exists(filename):
        print(f"Image déjà téléchargée : {filename}")
        return filename  # Return the filename
    else:
        # Vérification du code de statut de la requête
        # Si la requête a réussi (code 200), on sauvegarde l'image
        if request.status_code == 200:
            with open(filename, "wb") as image:
                request.raw.decode_content = True
                shutil.copyfileobj(request.raw, image)
            
            print(f"Image sauvegardée : {filename}")
            return filename  # Return the filename
        else:
            print(f"Échec de la récupération de l'image : {request.status_code}")
            return None

def send_to_rabbitmq(images):
    """
    Envoie les noms des images téléchargées à RabbitMQ.
    
    :param images: liste des noms des images téléchargées
    """
    connection = pika.BlockingConnection(pika.URLParameters("amqp://rabbitmq_container:5672?connection_attempts=10&retry_delay=10"))
    channel = connection.channel()
    channel.queue_declare(queue='ma_queue')
    for image in images:
        channel.basic_publish(exchange='', routing_key='ma_queue', body=image)
    connection.close()

#-------------------------------------------------------------------------------------
def main():
    # Démarre l'application Flask
    app.run(host='0.0.0.0', port=5000)

    # Définition de la requête SPARQL (LIMIT à modfier selon le besoin)
    query = """
    SELECT DISTINCT ?grandeville ?grandevilleLabel ?pays ?paysLabel ?image {
        ?grandeville wdt:P31 wd:Q1549591;
        wdt:P17 ?pays;
        wdt:P18 ?image.
        SERVICE wikibase:label { bd:serviceParam wikibase:language "fr". }
    }
    LIMIT 10
    """
    #Définition de l'URL de l'endpoint SPARQL
    endpoint_url = "https://query.wikidata.org/sparql"

    # Récupération des résultats de la requête SPARQL
    results = get_sparql_results(endpoint_url, query)

    # Traitement des résultats et création d'un DataFrame
    array = [(result["grandevilleLabel"]["value"],
            result["paysLabel"]["value"],
            result["image"]["value"])
            for result in results["results"]["bindings"]]

    dataframe = pd.DataFrame(array, columns=["ville", "pays", "image"])
    dataframe = dataframe.astype(dtype={"ville": "<U200", "pays": "<U200", "image": "<U200"})


    # Affichage du DataFrame pour vérification
    print("Showing head")
    dataframe.head()

    pool = mp.Pool(processes=mp.cpu_count())
    downloaded_images = pool.map(download_image, dataframe["image"])
    print(downloaded_images)

    # Connection au serveur RabbitMQ
    connection = pika.BlockingConnection(pika.URLParameters("amqp://rabbitmq_container:5672?connection_attempts=10&retry_delay=10"))
    channel = connection.channel()

    # Déclaration de la file d'attente
    channel.queue_declare(queue='ma_queue')

    # Envoi des données à la file d'attente
    for downloaded_images in downloaded_images:
        channel.basic_publish(exchange='', routing_key='ma_queue', body=downloaded_images)

    
    # Boucle infinie pour empêcher le processus de se terminer
    while True:
        time.sleep(1)

    # Fermeture de la connexion
    connection.close()

