# Base image amb Python
FROM python:3.11-slim

# Metadata
LABEL maintainer="GoGestor"
LABEL description="OCR Agent per DNI i Permís de Circulació"

# Variables d'entorn
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Instal·lar dependències del sistema per Tesseract i llibreries d'imatge
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-cat \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Directori de treball
WORKDIR /app

# Copiar requirements
COPY requirements.txt .

# Instal·lar dependències Python
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copiar codi de l'aplicació
COPY ./app ./app

# Port
EXPOSE 8000

# Executar amb uvicorn (usa $PORT de Railway, per defecte 8000)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
