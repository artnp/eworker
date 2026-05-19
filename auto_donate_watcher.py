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
                mode_flag = "--donate" if current_mode == 'fb' else "--clean"
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
                try:
                    if os.path.exists(event.src_path):
                        os.remove(event.src_path)
                        print(f"[Watcher] ✅ Deleted source {event.src_path} to prevent stale image reuse")
                except Exception as del_err:
                    print(f"[Watcher] Could not delete source (non-critical): {del_err}")
                    
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
                self.wfile.write(json.dumps(files[:7]).encode())
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
        if parsed_url.path == '/save-expose':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                img_data = data.get('image')
                if img_data and ',' in img_data:
                    header, encoded = img_data.split(',', 1)
                    import base64
                    binary_data = base64.b64decode(encoded)
                    target = os.path.join(DESKTOP_PATH, "complete.png")
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

# --- FIREBASE JOB WATCHER (SSE) ---
seen_job_ids = set()
def firebase_sse_worker():
    global seen_job_ids
    url = 'https://retouch-ebid-default-rtdb.asia-southeast1.firebasedatabase.app/jobs.json?orderBy="status"&equalTo="active"'
    print("[Watcher] ⚡ Started Real-time Firebase Job Watcher (SSE)")
    first_run = True
    while True:
        try:
            req = urllib.request.Request(url)
            req.add_header('Accept', 'text/event-stream')
            with urllib.request.urlopen(req) as response:
                for line in response:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        data_str = line[5:].strip()
                        if data_str and data_str != 'null':
                            payload = json.loads(data_str)
                            path = payload.get('path', '')
                            data = payload.get('data')
                            
                            if not data or not isinstance(data, dict):
                                continue
                                
                            # If initial connection, we get the whole dict
                            if path == '/':
                                for key, job in data.items():
                                    if isinstance(job, dict):
                                        uid = job.get('uniqueId')
                                        if uid and uid not in seen_job_ids:
                                            seen_job_ids.add(uid)
                                            if first_run:
                                                print(f"[Watcher] 📝 Existing job noted: {uid}")
                                            else:
                                                print(f"[Watcher] 🔔 NEW Job! Opening chat: {uid}")
                                                admin_url = f"http://127.0.0.1:{PORT}/admin-local.html?job={key}&uid={uid}"
                                                import subprocess
                                                try:
                                                    cmd_url = admin_url.replace('&', '^&')
                                                    subprocess.Popen(['cmd', '/c', 'start', 'msedge', cmd_url], shell=False)
                                                except:
                                                    import webbrowser
                                                    webbrowser.open(admin_url)
                                first_run = False
                                
                            else:
                                # New job or updated job, path is like "/-NxYz"
                                key = path.strip('/')
                                uid = data.get('uniqueId')
                                if uid and uid not in seen_job_ids:
                                    seen_job_ids.add(uid)
                                    print(f"[Watcher] 🔔 NEW Job! Opening chat: {uid}")
                                    admin_url = f"http://127.0.0.1:{PORT}/admin-local.html?job={key}&uid={uid}"
                                    import subprocess
                                    try:
                                        cmd_url = admin_url.replace('&', '^&')
                                        subprocess.Popen(['cmd', '/c', 'start', 'msedge', cmd_url], shell=False)
                                    except:
                                        import webbrowser
                                        webbrowser.open(admin_url)
        except Exception as e:
            # Reconnect silently on drop
            time.sleep(5)

def firebase_heartbeat_worker():
    url = 'https://retouch-ebid-default-rtdb.asia-southeast1.firebasedatabase.app/settings.json'
    while True:
        try:
            timestamp = int(time.time() * 1000)
            data = json.dumps({"lastActive": timestamp}).encode('utf-8')
            req = urllib.request.Request(url, data=data, method='PATCH')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=5) as response:
                pass
        except Exception as e:
            pass # Silent fail for heartbeat
        time.sleep(60)

# --- CHAT MESSAGE WATCHER ---
# Monitors active chats for new user messages that admin hasn't read
# Opens Edge automatically when there's an unread message from a customer
notified_chats = set()  # Track which chats we've already opened Edge for

def chat_message_watcher():
    """Poll active jobs and check for unread user messages in their chat rooms."""
    global notified_chats
    base_url = 'https://retouch-ebid-default-rtdb.asia-southeast1.firebasedatabase.app'
    jobs_url = f'{base_url}/jobs.json?orderBy="status"&equalTo="active"'
    print("[ChatWatcher] Started Chat Message Watcher (15s interval)")

    while True:
        try:
            # Get all active jobs
            req = urllib.request.Request(jobs_url)
            with urllib.request.urlopen(req, timeout=10) as response:
                jobs_data = json.loads(response.read().decode())

            if not jobs_data:
                time.sleep(15)
                continue

            for job_key, job in jobs_data.items():
                uid = job.get('uniqueId')
                if not uid:
                    continue

                # Skip if we already notified for this chat recently
                if uid in notified_chats:
                    continue

                try:
                    # Get the read receipt for this chat
                    receipt_url = f'{base_url}/readReceipts/{uid}.json'
                    req2 = urllib.request.Request(receipt_url)
                    with urllib.request.urlopen(req2, timeout=5) as resp2:
                        receipt_data = json.loads(resp2.read().decode())

                    admin_last_read = None
                    if receipt_data and receipt_data.get('adminLastRead'):
                        admin_last_read = receipt_data['adminLastRead']

                    # Get the latest message in the chat
                    chat_url = f'{base_url}/chats/{uid}.json?orderBy="timestamp"&limitToLast=1'
                    req3 = urllib.request.Request(chat_url)
                    with urllib.request.urlopen(req3, timeout=5) as resp3:
                        chat_data = json.loads(resp3.read().decode())

                    if not chat_data:
                        continue

                    # Check the latest message
                    for msg_key, msg in chat_data.items():
                        if msg.get('sender') != 'user':
                            continue
                        msg_time = msg.get('timestamp', '')

                        # If admin hasn't read OR admin's last read is before this message
                        should_notify = False
                        if not admin_last_read:
                            should_notify = True
                        elif msg_time > admin_last_read:
                            should_notify = True

                        if should_notify:
                            print(f"[ChatWatcher] 💬 New unread message in {uid}! Opening Edge...")
                            admin_url = f"http://127.0.0.1:{PORT}/admin-local.html?job={job_key}&uid={uid}"
                            notified_chats.add(uid)

                            import subprocess
                            try:
                                cmd_url = admin_url.replace('&', '^&')
                                subprocess.Popen(['cmd', '/c', 'start', 'msedge', cmd_url], shell=False)
                            except:
                                webbrowser.open(admin_url)

                            # Clear notification after 2 minutes (allow re-notification)
                            def clear_notif(chat_uid):
                                time.sleep(120)
                                notified_chats.discard(chat_uid)
                            threading.Thread(target=clear_notif, args=(uid,), daemon=True).start()

                except Exception as inner_e:
                    pass  # Skip individual chat errors silently

        except Exception as e:
            print(f"[ChatWatcher] Error: {e}")

        time.sleep(15)

# --- REALTIME SEND QUEUE WATCHER (SSE) ---
# Listens instantly for send.html uploads via Firebase Server-Sent Events
def send_queue_sse_watcher():
    base_url = 'https://retouch-ebid-default-rtdb.asia-southeast1.firebasedatabase.app/send_queue.json'
    print("[Watcher] ⚡ Started Real-time Send Queue Watcher (SSE)")
    
    while True:
        try:
            req = urllib.request.Request(base_url)
            req.add_header('Accept', 'text/event-stream')
            
            with urllib.request.urlopen(req) as response:
                for line in response:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data:'):
                        data_str = line[5:].strip()
                        if data_str and data_str != 'null':
                            payload = json.loads(data_str)
                            path = payload.get('path', '')
                            data = payload.get('data')
                            
                            if data and isinstance(data, dict):
                                if path == '/':
                                    items = data
                                else:
                                    # Example path: "/-Nyxyz123"
                                    items = {path.strip('/'): data}
                                    
                                for key, item in items.items():
                                    if isinstance(item, dict):
                                        link_url = item.get('url')
                                        if link_url:
                                            print(f"[Watcher] ⚡ Real-time Alert! Customer uploaded a file! Opening Edge: {link_url}")
                                            import subprocess
                                            try:
                                                cmd_url = link_url.replace('&', '^&')
                                                subprocess.Popen(['cmd', '/c', 'start', 'msedge', cmd_url], shell=False)
                                            except:
                                                import webbrowser
                                                webbrowser.open(link_url)
                                                
                                            # Immediately delete the item so it doesn't trigger again on reconnect
                                            try:
                                                del_url = f"https://retouch-ebid-default-rtdb.asia-southeast1.firebasedatabase.app/send_queue/{key}.json"
                                                del_req = urllib.request.Request(del_url, method='DELETE')
                                                urllib.request.urlopen(del_req, timeout=5)
                                            except:
                                                pass
        except Exception as e:
            # If network drops, reconnect silently after 5 seconds
            time.sleep(5)



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

    # Start Firebase Job Watcher Thread
    poller_thread = threading.Thread(target=firebase_sse_worker, daemon=True)
    poller_thread.start()

    # Start Firebase Heartbeat Thread
    heartbeat_thread = threading.Thread(target=firebase_heartbeat_worker, daemon=True)
    heartbeat_thread.start()
    print("[Server] Heartbeat started (60s interval)")

    # Start Chat Message Watcher Thread
    chat_watcher_thread = threading.Thread(target=chat_message_watcher, daemon=True)
    chat_watcher_thread.start()
    print("[Server] Chat Message Watcher started (15s interval)")

    # Start Realtime SSE Send Queue Watcher
    send_queue_sse_thread = threading.Thread(target=send_queue_sse_watcher, daemon=True)
    send_queue_sse_thread.start()


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
