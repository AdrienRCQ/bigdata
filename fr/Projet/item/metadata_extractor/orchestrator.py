import json
import subprocess
import pika
import docker

def get_least_busy_container():
    """
    Renvoie le conteneur le moins occupé en termes d'utilisation du CPU.
    
    :returns: conteneur le moins occupé
    """
    client = docker.from_env()
    containers = client.containers.list()
    return min(containers, key=lambda c: c.stats(stream=False)['cpu_stats']['cpu_usage']['total_usage'])

def on_message(channel, method, properties, body):
    """
    Fonction de rappel appelée lorsqu'un message est reçu.
    
    :param channel: canal de communication
    :param method: méthode de communication
    :param properties: propriétés du message
    :param body: corps du message
    """
    container = get_least_busy_container()
    if container:
        image_path = json.loads(body.decode())['file_path']
        print(f"Dispatching job for image: {image_path} to container: {container.name}")
        # Exécution de la commande dans le conteneur sélectionné
        container.exec_run(f"python /app/process_metadata.py {image_path}", detach=True)
    else:
        print("No containers available to process the image.")

if __name__ == "__main__":
    # Utilisation des paramètres par défaut pour la connexion
    parameters = pika.URLParameters("amqp://guest:guest@rabbitmq_container:5672?connection_attempts=10&retry_delay=10")
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    channel.queue_declare(queue='image_files')
    channel.basic_consume(queue='image_files', on_message_callback=on_message, auto_ack=True)
    print("Orchestrator started. Waiting for messages...")
    channel.start_consuming()
