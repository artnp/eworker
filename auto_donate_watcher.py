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
ps_trigger_event = threading.Event()
ps_trigger_data = {}

# --- FILE HANDLER ---
class DownloadHandler(FileSystemEventHandler):
    _processing_lock = threading.Lock()
    _last_processed_mtime = 0  # ★ ป้องกัน process ซ้ำ

    def _handle(self, event):
        global current_mode
        if event.is_directory: return
        target_file = getattr(event, 'dest_path', event.src_path)
        filename = os.path.basename(target_file)
        
        # เมื่อ Gemini/Copilot/Fast Download เซฟ complete.* หรือ complete_bot.* มา
        fname_lower = filename.lower()
        is_complete_file = (fname_lower.startswith("complete") and fname_lower.endswith((".png", ".jpg", ".jpeg", ".webp"))) or fname_lower in ["complete.png", "complete_bot.png", "complete.jpg", "complete.jpeg", "complete.webp"]
        if is_complete_file:
            # ★ ป้องกัน process ซ้ำ: เช็ค mtime ว่าเป็นไฟล์ใหม่จริงๆ
            if not self._processing_lock.acquire(blocking=False):
                print("[Watcher] Already processing, skipping duplicate trigger")
                return
            try:
                time.sleep(1.5) # รอให้ไฟล์เขียนเสร็จสนิท
                
                if not os.path.exists(target_file):
                    print("[Watcher] File disappeared, skipping")
                    return
                
                file_mtime = os.path.getmtime(target_file)
                if abs(file_mtime - self._last_processed_mtime) < 1.0:
                    print(f"[Watcher] Same file (mtime diff < 1s), skipping duplicate")
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
                    [sys.executable, script_path, mode_flag, target_file],
                    capture_output=True, text=True, timeout=60
                )
                if result.stdout:
                    print(f"[Watcher] Output:\n{result.stdout.strip()}")
                if result.returncode != 0:
                    print(f"[Watcher] ❌ Error in screenshot_donate.py (code {result.returncode}):\n{result.stderr.strip()}")
                
                # ไฟล์ผลลัพธ์อยู่ที่ Desktop เสมอ
                output_name = "complete_bot.png" if "complete_bot" in filename.lower() else "complete.png"
                target_path = os.path.join(DESKTOP_PATH, output_name)
                global last_exported_path
                last_exported_path = target_path
                
                print(f"[Watcher] Done. Result: {target_path}")
                # แจ้งเตือน Frontend ว่างานเสร็จแล้ว
                export_event.set()
                
                # ★ ลบ complete.* ใน Downloads หลัง process เสร็จ
                # เพื่อป้องกัน watcher หยิบภาพเก่าที่มีกรอบเขียวจาก Desktop/Downloads ย้อนกลับมาใช้
                # ★ chrome_hub mode: ไม่ลบต้นฉบับ
                if not skip_delete:
                    try:
                        if os.path.exists(target_file):
                            os.remove(target_file)
                            print(f"[Watcher] ✅ Deleted source {target_file} to prevent stale image reuse")
                    except Exception as del_err:
                        print(f"[Watcher] Could not delete source (non-critical): {del_err}")
                else:
                    print(f"[Watcher] (Chrome hub) Keeping original {target_file}")
                    
            except Exception as e:
                print(f"[Watcher] Error: {e}")
            finally:
                self._processing_lock.release()

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def on_moved(self, event):
        self._handle(event)

class DesktopHandler(FileSystemEventHandler):
    def _handle(self, event):
        if event.is_directory: return
        filename = os.path.basename(event.src_path)
        fname_lower = filename.lower()
        if (fname_lower.startswith("complete") and fname_lower.endswith((".png", ".jpg", ".jpeg", ".webp"))) or fname_lower in ["complete.png", "complete_bot.png", "complete.jpg", "complete.jpeg", "complete.webp"]:
            time.sleep(1) # wait for file write
            global last_exported_path
            last_exported_path = event.src_path
            export_event.set()

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
                export_event.clear()
                self.wfile.write(json.dumps({"status": "updated", "path": last_exported_path}).encode())
            else:
                self.wfile.write(json.dumps({"status": "timeout", "path": last_exported_path}).encode())
            return

        if parsed_url.path == '/wait-for-ps-trigger':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            was_set = ps_trigger_event.wait(timeout=60)
            if was_set:
                ps_trigger_event.clear()
                resp = {"status": "triggered"}
                resp.update(ps_trigger_data)
                self.wfile.write(json.dumps(resp).encode())
            else:
                self.wfile.write(json.dumps({"status": "timeout"}).encode())
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
                # Also include Desktop complete image if exists (.png, .jpg, .jpeg, .webp)
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    desktop_complete = os.path.join(DESKTOP_PATH, f"complete{ext}")
                    if os.path.exists(desktop_complete):
                        already = any(f['filename'] == desktop_complete for f in files)
                        if not already:
                            files.append({
                                "filename": desktop_complete,
                                "shortname": f"📍 complete{ext} (Desktop)",
                                "mtime": os.path.getmtime(desktop_complete)
                            })
                self.wfile.write(json.dumps(files[:12]).encode())
            except:
                self.wfile.write(json.dumps([]).encode())
            return

        if parsed_url.path == '/get-img':
            query = parse_qs(parsed_url.query)
            file_path = query.get('path', [None])[0]
            if file_path:
                file_path = file_path.replace('/', os.sep).replace('\\', os.sep)
                if not os.path.exists(file_path):
                    base = os.path.basename(file_path)
                    candidates = [
                        os.path.join(DOWNLOADS_PATH, base),
                        os.path.join(DESKTOP_PATH, base),
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), base)
                    ]
                    for c in candidates:
                        if os.path.exists(c):
                            file_path = c
                            break
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
                self.send_header('Access-Control-Allow-Origin', '*')
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

        if parsed_url.path == '/upscale-progress':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                import cloudinary_upscaler
                self.wfile.write(json.dumps(cloudinary_upscaler.get_upscale_progress()).encode())
            except Exception:
                import upscale_engine
                self.wfile.write(json.dumps(upscale_engine.get_upscale_progress()).encode())
            return

        if parsed_url.path == '/upscale-quota':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                import cloudinary_upscaler
                query_params = parse_qs(parsed_url.query)
                force_refresh = 'refresh' in query_params
                self.wfile.write(json.dumps(cloudinary_upscaler.get_accounts_quota(force_refresh=force_refresh)).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        return super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == '/trigger-ps':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                global ps_trigger_data
                ps_trigger_data = data
                ps_trigger_event.set()
                print(f"[Watcher] 📥 Received Photoshop Trigger: {data.get('prompt', '')[:40]}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

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

                    if data.get('openPhotoshop'):
                        import subprocess
                        ps_path = r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe"
                        if os.path.exists(ps_path):
                            subprocess.Popen([ps_path, target])
                        else:
                            try:
                                os.startfile(target)
                            except:
                                pass

                    # ถ้าบันทึก complete.png (ไม่ใช่ complete_bot.png) ให้สร้าง example.png บน Desktop ด้วย
                    is_complete_png = (os.path.basename(target).lower() == 'complete.png') and ('bot' not in target.lower())
                    if is_complete_png:
                        try:
                            from watermark_engine import create_anti_ai_watermark
                            from PIL import Image
                            import io
                            raw_img = Image.open(io.BytesIO(binary_data))
                            example_img = create_anti_ai_watermark(raw_img)
                            example_path = os.path.join(DESKTOP_PATH, 'example.png')
                            example_img.save(example_path, format='PNG')
                            print(f"[Watcher] Auto-generated example.png on Desktop")
                        except Exception as we:
                            print(f"[Watcher] Watermark generation error: {we}")

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

        if parsed_url.path == '/upscale':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                target_path = data.get('path')

                # 🚫 ป้องกันเด็ดขาด: ห้ามยุ่งกับไฟล์ complete_bot.png หรือระบบ Facebook_Bot
                if target_path and ('complete_bot' in os.path.basename(target_path).lower() or 'bot' in os.path.basename(target_path).lower()):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "ไม่อนุญาตให้ Upscale ไฟล์ complete_bot.png (Facebook_Bot ไม่ใช้ระบบ Upscale)"
                    }).encode())
                    return

                if not target_path or not os.path.exists(target_path) or 'complete_bot' in os.path.basename(target_path).lower():
                    target_path = os.path.join(DESKTOP_PATH, 'complete.png')

                scale = int(data.get('scale', 2))
                model_name = data.get('model', 'cloudinary_enhancer')
                
                print(f"[Watcher] 🔍 AI Upscale / Enhancer request received for {target_path} (scale={scale}x)")
                import cloudinary_upscaler
                result = cloudinary_upscaler.upscale_image(image_path=target_path, scale=scale, model_name=model_name)
                
                # Signal frontend that export updated
                global last_exported_path
                last_exported_path = target_path
                export_event.set()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                print(f"[Watcher] ❌ Upscale error: {e}")
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
