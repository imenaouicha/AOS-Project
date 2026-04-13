FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    gcc \
    libc6-dev \
    libpq-dev \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier les fichiers de dépendances d'abord (optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier tout le code (y compris entrypoint.sh)
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p receipts logs staticfiles media

# Donner les permissions (après avoir copié le fichier)
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]