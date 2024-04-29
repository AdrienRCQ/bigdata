import pika
import docker
import threading

DOCKER_CLIENT = docker.from_env()


def get_least_busy_container():
    global DOCKER_CLIENT
    
    client = DOCKER_CLIENT

    # Get a list of all running containers
    containers = client.containers.list(filters={'label': 'com.docker.compose.service=metadata-extractors', 'status': 'running'})

    # Find the container with the least CPU usage
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

if __name__ == '__main__':
    # Create a new process to listen to the queue
    queue_process = threading.Thread(target=listen_queue)
    queue_process.start()
    