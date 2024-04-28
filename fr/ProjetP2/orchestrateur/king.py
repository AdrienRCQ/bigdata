import pika
import os

# sleep for 10 seconds to wait for the RabbitMQ container to start
#os.system('sleep 10')

# Connect to RabbitMQ instance running inside the Docker container
connection = pika.BlockingConnection(pika.URLParameters("amqp://rabbitmq_container:5672?connection_attempts=10&retry_delay=10"))
channel = connection.channel()

queue_name = 'ma_queue'

def callback(ch, method, properties, body):
    print(f"Received: {body.decode()}")

# Set up the consumer to listen for new messages
channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

print("Listening for new messages...")
channel.start_consuming()
