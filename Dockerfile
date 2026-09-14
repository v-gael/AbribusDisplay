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
# .env.local est copié seulement s'il existe (voir .dockerignore) — sinon il est monté en volume

RUN mkdir -p /app/output

CMD ["python", "-m", "src.main"]
