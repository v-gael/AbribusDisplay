FROM python:3.11-slim

# fbi (paquet fbida) pour l'affichage framebuffer sur le Pi,
# fontconfig + libs pour Pillow (JPEG/PNG), inutiles mais légers en mode "file" sur Mac.
RUN apt-get update && apt-get install -y --no-install-recommends \
        fbi \
        fontconfig \
        libjpeg62-turbo \
        libopenjp2-7 \
        zlib1g \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY assets/ assets/
COPY .env .env
# .env.local n'est jamais copié dans l'image (exclu par .dockerignore) : ses
# valeurs arrivent au runtime via `env_file` (docker-compose.yml), plus le
# montage en volume de docker-compose.override.yml en dev.

RUN mkdir -p /app/output

CMD ["python", "-m", "src.main"]
