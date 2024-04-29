# Dockerfile pour l'environnement PySpark avec les dépendances de RabbitMQ
FROM jupyter/pyspark-notebook

WORKDIR /app

# Copie des scripts nécessaires dans le conteneur
COPY spark_app.py /app/

# Installation des dépendances Python supplémentaires
RUN pip install requests pika pandas SPARQLWrapper

CMD ["spark-submit", "/app/spark_app.py"]
