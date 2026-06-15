import http.server
import socketserver
import urllib.parse
import urllib.request
import os
import subprocess
import json
import re

import tempfile

PORT = int(os.environ.get("PORT", 7860))
DOWNLOADS_DIR = os.path.join(tempfile.gettempdir(), "downloader-mp3-downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def make_safe_filename(title):
    # 1. Hapus tanda kutip ganda (") dan satu (') agar tidak jadi garis bawah
    safe = title.replace('"', '').replace("'", "")
    # 2. Ganti karakter pembatas path / dan \ menjadi spasi-minus-spasi agar tetap terbaca indah
    safe = safe.replace('/', ' - ').replace('\\', ' - ')
    # 3. Ganti titik dua : menjadi spasi-minus-spasi
    safe = safe.replace(':', ' - ')
    # 4. Hapus karakter ilegal lainnya di filesystem (Windows/Linux) yaitu: * ? < > |
    safe = re.sub(r'[*?<>|]', '', safe)
    # 5. Hilangkan spasi berlebih
    safe = re.sub(r'\s+', ' ', safe)
    return safe.strip()

class DownloaderHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        # API info endpoint (proxy metadata youtube)
        if path == "/api/info":
            query = urllib.parse.parse_qs(parsed_path.query)
            video_url = query.get("url", [None])[0]
            if not video_url:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Parameter 'url' diperlukan."}).encode())
                return
                
            try:
                req_url = f"https://noembed.com/embed?url={urllib.parse.quote(video_url)}"
                req = urllib.request.Request(req_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    data = json.loads(response.read().decode())
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "title": data.get("title", "Video YouTube"),
                        "author": data.get("author_name", "YouTube Creator")
                    }).encode())
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "title": "Video YouTube",
                    "author": "YouTube Creator",
                    "error": str(e)
                }).encode())
            return

        # API convert endpoint
        elif path == "/api/convert":
            query = urllib.parse.parse_qs(parsed_path.query)
            video_url = query.get("url", [None])[0]
            quality = query.get("quality", ["128"])[0]
            
            if not video_url:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Parameter 'url' diperlukan."}).encode())
                return
                
            try:
                # 1. Pastikan binary yt-dlp ada di direktori lokal
                yt_dlp_path = os.path.join(os.getcwd(), "yt-dlp")
                if not os.path.exists(yt_dlp_path):
                    print("yt-dlp tidak ditemukan. Mengunduh secara otomatis...")
                    url_dl = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                    
                    # Custom header untuk menghindari penolakan dari github
                    req = urllib.request.Request(url_dl, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        with open(yt_dlp_path, 'wb') as out_file:
                            out_file.write(response.read())
                            
                    os.chmod(yt_dlp_path, 0o755)
                    print("yt-dlp berhasil diunduh!")
                
                # 2. Dapatkan judul video YouTube
                cmd_title = [
                    yt_dlp_path,
                    "--get-title",
                    video_url
                ]
                title_proc = subprocess.run(cmd_title, capture_output=True, text=True, check=True)
                title = title_proc.stdout.strip()
                if not title:
                    title = "Sqezee_Noso_Audio"
                
                # Buat nama berkas yang aman dan natural
                safe_title = make_safe_filename(title)
                output_filename = f"{safe_title}.mp3"
                output_filepath = os.path.join(DOWNLOADS_DIR, output_filename)
                
                # Jika file sudah pernah diunduh sebelumnya, langsung kirim
                if os.path.exists(output_filepath):
                    print(f"Berkas sudah ada: {output_filename}. Menggunakan cache.")
                    download_url = f"/api/download?file={urllib.parse.quote(output_filename)}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "title": title,
                        "download_url": download_url
                    }).encode())
                    return
                
                # 3. Jalankan proses unduh dan konversi ke mp3 menggunakan yt-dlp & ffmpeg
                cmd_dl = [
                    yt_dlp_path,
                    "-x",
                    "--audio-format", "mp3",
                    "--audio-quality", quality,
                    "-o", os.path.join(DOWNLOADS_DIR, f"{safe_title}.%(ext)s"),
                    video_url
                ]
                print(f"Memulai konversi: {video_url} dengan bitrate {quality} kbps...")
                subprocess.run(cmd_dl, check=True, capture_output=True)
                
                # 4. Cek apakah berkas MP3 berhasil terbuat
                if os.path.exists(output_filepath):
                    download_url = f"/api/download?file={urllib.parse.quote(output_filename)}"
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "title": title,
                        "download_url": download_url
                    }).encode())
                    print("Konversi selesai!")
                else:
                    raise FileNotFoundError("Gagal memproses berkas MP3.")
                    
            except subprocess.CalledProcessError as e:
                print("Error saat konversi (SubprocessError):", e)
                print("STDOUT:", e.stdout)
                print("STDERR:", e.stderr)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"{str(e)}: {e.stderr}"}).encode())
            except Exception as e:
                print("Error saat konversi:", e)
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                
        # API download endpoint (mengirim berkas mp3 hasil konversi)
        elif path == "/api/download":
            query = urllib.parse.parse_qs(parsed_path.query)
            filename = query.get("file", [None])[0]
            if not filename:
                self.send_response(400)
                self.end_headers()
                return
                
            filepath = os.path.join(DOWNLOADS_DIR, filename)
            if not os.path.exists(filepath) or ".." in filename:
                self.send_response(404)
                self.end_headers()
                return
                
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(os.path.getsize(filepath)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            with open(filepath, 'rb') as f:
                self.wfile.write(f.read())
                
        # Menyajikan berkas index.html statis
        else:
            if path == "/" or path == "":
                filepath = os.path.join(os.getcwd(), "index.html")
            else:
                filepath = os.path.join(os.getcwd(), path.lstrip("/"))
                
            if os.path.exists(filepath) and os.path.isfile(filepath):
                self.send_response(200)
                if filepath.endswith(".html"):
                    self.send_header("Content-Type", "text/html")
                elif filepath.endswith(".css"):
                    self.send_header("Content-Type", "text/css")
                elif filepath.endswith(".js"):
                    self.send_header("Content-Type", "application/javascript")
                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()

print(f"Server berjalan di http://localhost:{PORT}")
try:
    with socketserver.TCPServer(("0.0.0.0", PORT), DownloaderHandler) as httpd:
        httpd.serve_forever()
except KeyboardInterrupt:
    print("\nServer dihentikan.")
