FROM python:3.10-slim

# Pasang dependencies sistem yang diperlukan (ffmpeg dan curl)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Salin berkas server ke dalam container
COPY server.py .

# Jalankan pada port 8000
EXPOSE 8000

# Perintah menjalankan server
CMD ["python3", "server.py"]
