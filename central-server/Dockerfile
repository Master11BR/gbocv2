FROM python:3.10-slim-bullseye

WORKDIR /app

# Configurar localização para evitar warnings
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Instalar BuildKit para melhor performance
ENV DOCKER_BUILDKIT=1

# Copiar dependências e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar aplicação
COPY app/ app/

# Criar diretório para dados e definir permissões
RUN mkdir -p /app/data && \
    chown -R nobody:nogroup /app/data && \
    chmod -R 755 /app/data

USER nobody

EXPOSE 8000 9200

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]