# Python 3.11 slim image kullan
FROM python:3.11-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Sistem bağımlılıklarını yükle
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıklarını kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodunu kopyala
COPY . .

# Statik dosyalar için dizinler oluştur
RUN mkdir -p /app/instance /app/app/static/uploads

# Ortam değişkeni - Docker container olduğunu belirt
ENV DOCKER_CONTAINER=1

# Port 5000'i aç
EXPOSE 5000

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000', timeout=5)" || exit 1

# Uygulamayı başlat
CMD ["python", "run.py"]
