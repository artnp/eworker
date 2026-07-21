import http.server
import socketserver
import json
import os
import shutil
import time
import threading
import urllib.request
import urllib.error
import webbrowser
from urllib.parse import urlparse, parse_qs
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- CONFIG ---
PORT = 5000
# ค้นหาพาธโฟลเดอร์ Downloads และ Desktop
DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads")
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")

# --- MODE ---
# 'hub' = crop อย่างเดียว ส่ง Desktop (ไม่มี QR)
# 'fb'  = crop + ฝัง QR + auto paste + auto post
current_mode = 'hub'

# คอนดิชั่นสำหรับแจ้งเตือน Frontend
export_event = threading.Event()
last_exported_path = ""

# --- FILE HANDLER ---
class DownloadHandler(FileSystemEventHandler):
    _processing_lock = threading.Lock()
    _last_processed_mtime = 0  # ★ ป้องกัน process ซ้ำ

    def _handle(self, event):
        global current_mode
        if event.is_directory: return
        filename = os.path.basename(event.src_path)
        
        # เมื่อ Gemini เซฟ complete.png มา
        if filename.lower() == "complete.png":
            # ★ ป้องกัน process ซ้ำ: เช็ค mtime ว่าเป็นไฟล์ใหม่จริงๆ
            if not self._processing_lock.acquire(blocking=False):
                print("[Watcher] Already processing, skipping duplicate trigger")
                return
            try:
                time.sleep(2) # รอให้ไฟล์เขียนเสร็จสนิท
                
                if not os.path.exists(event.src_path):
                    print("[Watcher] File disappeared, skipping")
                    return
                
                file_mtime = os.path.getmtime(event.src_path)
                if abs(file_mtime - self._last_processed_mtime) < 3:
                    print(f"[Watcher] Same file (mtime diff < 3s), skipping duplicate")
                    return
                DownloadHandler._last_processed_mtime = file_mtime
                
                script_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(script_dir, "screenshot_donate.py")
                
                # เลือกโหมดตาม current_mode
                if current_mode == 'chrome_hub':
                    mode_flag = "--clean"
                    skip_delete = False
                    print(f"[Watcher] Detected Export (Chrome hub) -> Running {mode_flag}")
                else:
                    mode_flag = "--donate" if current_mode == 'fb' else "--clean"
                    skip_delete = False
                    print(f"[Watcher] Detected Export -> Running {mode_flag}")
                
                import subprocess, sys
                result = subprocess.run(
                    [sys.executable, script_path, mode_flag, event.src_path],
                    capture_output=True, text=True, timeout=60
                )
                
                # ไฟล์ผลลัพธ์อยู่ที่ Desktop เสมอ
                target_path = os.path.join(DESKTOP_PATH, "complete.png")
                global last_exported_path
                last_exported_path = target_path
                
                print(f"[Watcher] Done. Result: {target_path}")
                # แจ้งเตือน Frontend ว่างานเสร็จแล้ว
                export_event.set()
                export_event.clear()
                
                # ★ ลบ complete.png ใน Downloads หลัง process เสร็จ
                # เพื่อป้องกัน watcher หยิบภาพเก่าที่มีกรอบเขียวจาก Desktop/Downloads ย้อนกลับมาใช้
                # ★ chrome_hub mode: ไม่ลบต้นฉบับ
                if not skip_delete:
                    try:
                        if os.path.exists(event.src_path):
                            os.remove(event.src_path)
                            print(f"[Watcher] ✅ Deleted source {event.src_path} to prevent stale image reuse")
                    except Exception as del_err:
                        print(f"[Watcher] Could not delete source (non-critical): {del_err}")
                else:
                    print(f"[Watcher] (Chrome hub) Keeping original {event.src_path}")
                    
            except Exception as e:
                print(f"[Watcher] Error: {e}")
            finally:
                self._processing_lock.release()

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

class DesktopHandler(FileSystemEventHandler):
    def _handle(self, event):
        if event.is_directory: return
        filename = os.path.basename(event.src_path)
        if filename.lower() == "complete.png":
            time.sleep(1) # wait for file write
            global last_exported_path
            last_exported_path = event.src_path
            export_event.set()
            export_event.clear()

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

# --- SERVER LOGIC ---
class HubHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        if self.path == '/favicon.ico':
            self.send_response(404)
            self.end_headers()
            return

        if parsed_url.path == '/wait-for-export':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # จอดรอตรงนี้จนกว่าจะมีสัญญาณ (Timeout 60s เพื่อความปลอดภัย)
            was_set = export_event.wait(timeout=60)
            if was_set:
                self.wfile.write(json.dumps({"status": "updated", "path": last_exported_path}).encode())
            else:
                self.wfile.write(json.dumps({"status": "timeout", "path": last_exported_path}).encode())
            return

        if parsed_url.path == '/list-downloads':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            files = []
            try:
                all_files = os.listdir(DOWNLOADS_PATH)
                all_files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOADS_PATH, x)), reverse=True)
                for f in all_files:
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        full_path = os.path.join(DOWNLOADS_PATH, f)
                        files.append({
                            "filename": full_path,
                            "shortname": f,
                            "mtime": os.path.getmtime(full_path)
                        })
                # Also include Desktop\complete.png if exists
                desktop_complete = os.path.join(DESKTOP_PATH, "complete.png")
                if os.path.exists(desktop_complete):
                    # Check if already in list (avoid duplicate)
                    already = any(f['filename'] == desktop_complete for f in files)
                    if not already:
                        files.append({
                            "filename": desktop_complete,
                            "shortname": "📍 complete.png (Desktop)",
                            "mtime": os.path.getmtime(desktop_complete)
                        })
                self.wfile.write(json.dumps(files[:12]).encode())
            except:
                self.wfile.write(json.dumps([]).encode())
            return

        if parsed_url.path == '/get-img':
            query = parse_qs(parsed_url.query)
            file_path = query.get('path', [None])[0]
            if file_path and os.path.exists(file_path):
                self.send_response(200)
                ext = file_path.lower().split('.')[-1]
                content_type = 'image/webp' if ext == 'webp' else ('image/png' if ext == 'png' else 'image/jpeg')
                self.send_header('Content-type', content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
            return

        if parsed_url.path == '/delete-file':
            query = parse_qs(parsed_url.query)
            file_path = query.get('path', [None])[0]
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                except:
                    self.send_response(500)
                    self.end_headers()
            return

        if parsed_url.path == '/set-mode':
            global current_mode
            query = parse_qs(parsed_url.query)
            mode = query.get('mode', ['hub'])[0]
            current_mode = mode
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"mode": current_mode}).encode())
            return

        if parsed_url.path == '/heartbeat':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "alive"}).encode())
            return

        return super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == '/save-image':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                img_data = data.get('dataUrl')
                target = data.get('path')
                if img_data and ',' in img_data and target:
                    header, encoded = img_data.split(',', 1)
                    import base64
                    binary_data = base64.b64decode(encoded)
                    with open(target, 'wb') as f:
                        f.write(binary_data)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "path": target}).encode())
                else:
                    self.send_response(400)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
            return

        if parsed_url.path == '/mark-points':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                img_url = data.get('url')
                img_data = data.get('dataUrl')
                
                script_dir = os.path.dirname(os.path.abspath(__file__))
                temp_filename = "temp_mark.jpg"
                temp_path = os.path.join(script_dir, temp_filename)
                
                # Remove old file if exists
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                download_success = False
                if img_url:
                    try:
                        req = urllib.request.Request(
                            img_url, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        )
                        with urllib.request.urlopen(req, timeout=15) as response:
                            with open(temp_path, 'wb') as f:
                                f.write(response.read())
                        download_success = True
                    except Exception as download_err:
                        print(f"[Watcher] Error downloading image URL: {download_err}")
                
                if not download_success and img_data and ',' in img_data:
                    try:
                        header, encoded = img_data.split(',', 1)
                        import base64
                        binary_data = base64.b64decode(encoded)
                        with open(temp_path, 'wb') as f:
                            f.write(binary_data)
                        download_success = True
                    except Exception as base64_err:
                        print(f"[Watcher] Error parsing base64 image data: {base64_err}")
                
                if download_success and os.path.exists(temp_path):
                    import subprocess
                    ps_script = os.path.join(script_dir, "MarkPoints.ps1")
                    # Run MarkPoints.ps1 asynchronously
                    cmd = f'powershell -ExecutionPolicy Bypass -File "{ps_script}" "{temp_path}"'
                    subprocess.Popen(cmd, shell=True)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "message": "MarkPoints triggered successfully."}).encode())
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": "Failed to obtain image."}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass

# --- MAIN ---
class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True





if __name__ == "__main__":
    event_handler = DownloadHandler()
    observer = Observer()
    observer.schedule(event_handler, DOWNLOADS_PATH, recursive=False)
    observer.start()

    desktop_handler = DesktopHandler()
    desktop_observer = Observer()
    desktop_observer.schedule(desktop_handler, DESKTOP_PATH, recursive=False)
    desktop_observer.start()

    from PIL import Image, ImageDraw
    import pystray

    httpd = ThreadingHTTPServer(("", PORT), HubHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    print(f"[Server] Serving in Threaded mode at port {PORT}")

    def create_image():
        image = Image.new('RGB', (64, 64), color=(66, 133, 244))
        draw = ImageDraw.Draw(image)
        draw.text((10, 20), "AI", fill=(255, 255, 255))
        return image

    def on_quit(icon, item):
        observer.stop()
        desktop_observer.stop()
        httpd.shutdown()
        httpd.server_close()
        icon.stop()

    icon = pystray.Icon("AI_Hub_Watcher", create_image(), f"AI Hub Central (Port {PORT})", menu=pystray.Menu(
        pystray.MenuItem("Quit", on_quit)
    ))
    
    try:
        icon.run()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        desktop_observer.stop()
        desktop_observer.join()
        httpd.shutdown()
        httpd.server_close()
