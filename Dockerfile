# Stage 1: Build the static Next.js frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Stage 2: NVIDIA CUDA runtime Ubuntu 22.04
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04 AS runtime

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3-pip \
    python3-dev \
    ffmpeg \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/python3.12 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.12 /usr/bin/python

WORKDIR /app

# Copiar e instalar dependências do Python a partir de requirements.txt
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir onnxruntime-gpu==1.24.4

# Copiar o restante da aplicação
COPY . /app

# Copiar os arquivos compilados do frontend gerados no Stage 1
COPY --from=frontend-builder /app/frontend/out /app/frontend/out

# Expor a porta da API
EXPOSE 8000

ENV PYTHONPATH=/app

# Ponto de entrada oficial da aplicação desacoplada
CMD ["python", "run_api.py"]
