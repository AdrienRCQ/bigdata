# Dockerfile pour l'environnement PySpark avec les dépendances de RabbitMQ
FROM jupyter/pyspark-notebook

WORKDIR /app

# Copie des scripts nécessaires dans le conteneur
COPY . /app

# Installation des dépendances Python supplémentaires
RUN pip install requests pika pandas SPARQLWrapper

CMD ["spark-submit", "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.4.2", "/app/multiproc_download.py"]
