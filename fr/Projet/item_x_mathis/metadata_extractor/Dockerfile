# Base image with Python
FROM python:3.8-slim

WORKDIR /app

# Installation des dépendances nécessaires
RUN pip install pika pillow docker

# Copie des scripts dans le conteneur
COPY orchestrator.py process_metadata.py /app/

CMD ["python", "/app/orchestrator.py"]
