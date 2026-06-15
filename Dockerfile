FROM python:3.10-slim

# Pasang dependencies sistem yang diperlukan (ffmpeg dan curl)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Unduh yt-dlp secara langsung ke /app saat membangun Docker image agar aman dan cepat
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /app/yt-dlp && \
    chmod a+rx /app/yt-dlp

# Salin berkas backend dan frontend ke dalam container
COPY server.py .
COPY index.html .
COPY cookies.tx[t] .

# Expose port yang digunakan (Hugging Face defaultnya 7860)
EXPOSE 7860

CMD ["python3", "-u", "server.py"]
