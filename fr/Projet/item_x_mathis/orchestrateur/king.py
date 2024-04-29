import sys
import time
from SPARQLWrapper import SPARQLWrapper, JSON as SPARQL_JSON
from urllib.parse import urlparse, unquote, quote
import pandas as pd
import pika
import json
import docker
import threading

DOCKER_CLIENT = docker.from_env()


def get_least_busy_container():
    global DOCKER_CLIENT
    
    client = DOCKER_CLIENT

    # Get a list of all running containers
    containers = client.containers.list(filters={'label': 'com.docker.compose.service=metadata-extractors', 'status': 'running'})

    # Get the CPU and memory usage for each container
    usage = {
        container.id: (container.stats()['cpu_stats']['cpu_usage']['total'], container.stats()['memory_stats']['usage'])
        for container in containers
    }

    # Calculate the total CPU and memory usage for all containers
    total_cpu_usage = sum(usage[container][0] for container in usage)
    total_memory_usage = sum(usage[container][1] for container in usage)

    # Calculate the maximum allowed CPU and memory usage
    max_cpu_usage = 0.95 * len(containers) * client.info()['n_cpu'] * 10**10
    max_memory_usage = 0.95 * client.info()['mem_total']

    # If all containers are used at 95% or more of their capacity, return None
    if total_cpu_usage >= max_cpu_usage or total_memory_usage >= max_memory_usage:
        return None

    # Choose the container with the lowest CPU usage
    return min(containers, key=lambda c: c.stats(stream=False)['cpu_stats']['cpu_usage']['total_usage'])


def on_message(channel, method_frame, header_frame, body):
    # Choose a container to send the data to
    container = get_least_busy_container()
    
    if container is None:
        # If no container is available, requeue the message
        channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
        return

    # Send the data to the container
    container.exec_run(['python', 'process_metadata.py', body.decode()])

def listen_queue():
    global on_message
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.URLParameters("amqp://rabbitmq_container:5672?connection_attempts=10&retry_delay=10"))
    channel = connection.channel()
    
    # Listen for new messages on the queue
    # create queue
    channel.queue_declare(queue='image_files')
    
    channel.basic_consume('image_files', on_message, auto_ack=True)
    channel.start_consuming()
    
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
    
    return results['results']['bindings']
    
def retrieve_images():
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
    
    return results

def distribute_images_to_containers(images):
    global DOCKER_CLIENT
    
    client = DOCKER_CLIENT
    containers = client.containers.list(filters={'label': 'com.docker.compose.service=downloaders', 'status': 'running'})

    # Split the array of results into chunks, one for each container
    num_containers = len(containers)
    if num_containers > len(images):
        # If there are fewer images than containers, only send one chunk to the first container
        chunks = [images]
    else:
        chunk_size = len(images) // num_containers
        chunks = [images[i:i + chunk_size] for i in range(0, len(images), chunk_size)]

    # If the array doesn't divide evenly, add the remaining elements to the last chunk
    if len(images) % num_containers != 0:
        chunks[-1].extend(images[len(images) - (len(images) % num_containers):])

    # Send a chunk to each container
    for container, chunk in zip(containers, chunks):
        # Convert the chunk to a JSON string
        chunk_json = json.dumps(chunk)
        # Pass the JSON string as a single argument to the script
        container.exec_run(['python', 'spark_app.py', chunk_json])

if __name__ == '__main__':
    # Create a new process to listen to the queue
    queue_process = threading.Thread(target=listen_queue)
    queue_process.start()
    
    # distributing image downloads
    images = retrieve_images()
    time.sleep(5)
    distribute_images_to_containers(images)
    