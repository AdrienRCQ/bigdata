import sys
from SPARQLWrapper import SPARQLWrapper, JSON
from urllib.parse import urlparse, unquote
import pandas as pd
import pika
import docker
import threading

DOCKER_CLIENT = docker.APIClient()


def get_least_busy_container():
    global DOCKER_CLIENT
    
    client = DOCKER_CLIENT

    # Get a list of all running containers
    containers = client.containers.list(filters={'label': 'com.docker.compose.service=data-processors', 'status': 'running'})

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

    # Choose the container with the lowest CPU and memory usage
    return client.containers.get(min(usage, key=usage.get))


def on_message(channel, method_frame, header_frame, body):
    # Choose a container to send the data to
    container = get_least_busy_container()
    
    if container is None:
        # If no container is available, requeue the message
        channel.basic_reject(delivery_tag=method_frame.delivery_tag, requeue=True)
        return

    # Send the data to the container
    container.exec_run(['python', 'process_data.py', body.decode()])

def listen_queue():
    global on_message
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(pika.URLParameters("amqp://rabbitmq_container:5672?connection_attempts=10&retry_delay=10"))
    channel = connection.channel()
    
    # Listen for new messages on the queue
    channel.basic_consume('my_queue', on_message, auto_ack=True)
    channel.start_consuming()
    
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

    # Traitement des résultats et création d'un DataFrame
    array = [(result["grandevilleLabel"]["value"],
            result["paysLabel"]["value"],
            result["image"]["value"])
            for result in results["results"]["bindings"]]

    dataframe = pd.DataFrame(array, columns=["ville", "pays", "image"])
    dataframe = dataframe.astype(dtype={"ville": "<U200", "pays": "<U200", "image": "<U200"})
    
    return dataframe["image"]

def distribute_images_to_containers(images):
    global DOCKER_CLIENT
    
    client = DOCKER_CLIENT
    containers = client.containers.list(filters={'label': 'com.docker.compose.service=data-gatherers', 'status': 'running'})

    # Split the array of images into chunks, one for each container
    num_containers = len(containers)
    chunk_size = len(images) // num_containers
    chunks = [images[i:i + chunk_size] for i in range(0, len(images), chunk_size)]

    # If the array doesn't divide evenly, add the remaining elements to the last chunk
    if len(images) % num_containers != 0:
        chunks[-1].extend(images[len(images) - (len(images) % num_containers):])

    # Send a chunk to each container
    for container, chunk in zip(containers, chunks):
        container.exec_run(['python', 'multiproc_download.py'] + chunk)

if __name__ == '__main__':
    # Create a new process to listen to the queue
    queue_process = threading.Thread(target=listen_queue)
    queue_process.start()
    
    # distributing image downloads
    images = retrieve_images()
    distribute_images_to_containers(images)
    