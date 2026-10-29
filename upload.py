import sys
import threading
import requests
import json
import os
import time
import base64
import uuid


class UploadProgressBar:
    """แสดงแถบ Loading Progress Bar ในเทอร์มินัลแบบเรียลไทม์"""
    def __init__(self, title="กำลังอัปโหลด", width=22):
        self.title = title
        self.width = width
        self.pct = 0
        self.running = False
        self.thread = None
        self.last_len = 0

    def _render(self, pct, status=""):
        pct = max(0, min(100, int(pct)))
        filled = int(self.width * pct / 100)
        bar = "█" * filled + "░" * (self.width - filled)
        line = f"\r  🚀 {self.title} [{bar}] {pct:>3}% {status}"
        pad = " " * max(0, self.last_len - len(line))
        text = line + pad
        try:
            sys.stderr.buffer.write(text.encode("utf-8"))
            sys.stderr.buffer.flush()
        except Exception:
            try:
                sys.stderr.write(text)
                sys.stderr.flush()
            except Exception:
                pass
        self.last_len = len(line)

    def start(self, max_pct=92, step=3, interval=0.06):
        self.running = True
        self._render(6)
        def run():
            p = 6
            while self.running and p < max_pct:
                time.sleep(interval)
                p += step
                self._render(p)
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()

    def finish(self, status="✅ เรียบร้อย"):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.2)
        self._render(100, status)
        try:
            sys.stderr.buffer.write(b"\n")
            sys.stderr.buffer.flush()
        except Exception:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def fail(self, status="❌ ขัดข้อง"):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=0.2)
        self._render(self.pct or 30, status)
        try:
            sys.stderr.buffer.write(b"\n")
            sys.stderr.buffer.flush()
        except Exception:
            sys.stderr.write("\n")
            sys.stderr.flush()

REGISTRY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".firebase_uploads.json")

def cleanup_firebase_files():
    """ลบไฟล์ขยะใน Firebase RTDB ที่มีอายุเกิน 1 ชั่วโมงอัตโนมัติ เพื่อป้องกันพื้นที่เต็ม"""
    if not os.path.exists(REGISTRY_FILE):
        return
    try:
        with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        now = time.time()
        updated_registry = {}
        deleted_count = 0
        
        for file_id, uploaded_at in registry.items():
            # หากไฟล์มีอายุเกิน 1 ชั่วโมง (3600 วินาที) สั่ง DELETE ออกจาก Firebase ทันที
            if now - uploaded_at > 3600:
                try:
                    del_url = f"https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/{file_id}.json"
                    requests.delete(del_url, timeout=5)
                    deleted_count += 1
                except Exception:
                    pass
            else:
                updated_registry[file_id] = uploaded_at
                
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_registry, f)
            
        if deleted_count > 0:
            print(f"🧹 ล้างไฟล์หมดอายุใน Firebase สำเร็จ {deleted_count} ไฟล์", file=sys.stderr)
    except Exception as e:
        print(f"Firebase auto-cleanup error: {e}", file=sys.stderr)

def register_firebase_file(file_id):
    """บันทึกประวัติไฟล์ Firebase เพื่อรอสั่งลบอัตโนมัติเมื่อครบ 1 ชม."""
    try:
        registry = {}
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, 'r', encoding='utf-8') as f:
                registry = json.load(f)
        registry[file_id] = time.time()
        with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
            json.dump(registry, f)
    except Exception:
        pass

def upload_litterbox(file_path):
    """อัพโหลดไปยัง Litterbox (1hr expiry) - อันดับ 1"""
    url = 'https://litterbox.catbox.moe/resources/internals/api.php'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    
    pb = UploadProgressBar(f"อัปโหลด Litterbox ({filename[:18]})")
    pb.start(max_pct=90, step=4, interval=0.04)
    
    for attempt in range(1, 3):
        try:
            with open(file_path, 'rb') as f:
                files = {'fileToUpload': (filename, f)}
                data = {'reqtype': 'fileupload', 'time': '1h'}
                response = requests.post(url, data=data, files=files, headers=headers, timeout=8)
                res_text = response.text.strip()
                
                if response.status_code == 200 and res_text.startswith('http'):
                    pb.finish("✅ อัปโหลดสำเร็จ")
                    return res_text
                else:
                    if attempt == 2:
                        pb.fail(f"HTTP {response.status_code}")
                    print(f"Litterbox attempt {attempt} failed ({response.status_code}): {res_text[:120]}", file=sys.stderr)
        except Exception as e:
            if attempt == 2:
                pb.fail("ขัดข้อง")
            print(f"Litterbox attempt {attempt} error: {e}", file=sys.stderr)
        
        if attempt < 2:
            time.sleep(0.5)
            
    pb.fail("เปลี่ยนระบบสำรอง...")
    return None

def upload_firebase(file_path):
    """อัพโหลดไปยัง Firebase RTDB (อันดับ 2: เสถียรในไทย, รองรับ PDF และรูปภาพ, ปลอดภัยสำหรับส่งงานลับ)"""
    pb = UploadProgressBar(f"อัปโหลด Cloud ({os.path.basename(file_path)[:18]})")
    pb.start(max_pct=90, step=3, interval=0.05)
    try:
        # ล้างไฟล์ขยะที่หมดอายุเกิน 1 ชม. ก่อนเริ่มอัปโหลดไฟล์ใหม่
        cleanup_firebase_files()

        file_size = os.path.getsize(file_path)
        # Firebase RTDB เหมาะสำหรับไฟล์ขนาดไม่เกิน 15MB
        if file_size > 15 * 1024 * 1024:
            pb.fail("ไฟล์เกิน 15MB")
            print("ไฟล์ขนาดเกิน 15MB ข้ามระบบ Firebase...", file=sys.stderr)
            return None

        file_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            encoded_data = base64.b64encode(f.read()).decode('ascii')

        url = f"https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/{file_id}.json"
        payload = {
            "data": encoded_data,
            "created": int(time.time() * 1000),
            "filename": filename,
            "size": file_size
        }
        
        response = requests.put(url, json=payload, timeout=45)
        if response.status_code == 200:
            register_firebase_file(file_id)
            pb.finish("✅ อัปโหลดสำเร็จ")
            return f"fb_{file_id}"
        else:
            pb.fail(f"HTTP {response.status_code}")
            print(f"Firebase failed ({response.status_code}): {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        pb.fail("ขัดข้อง")
        print(f"Firebase error: {e}", file=sys.stderr)
    return None

def upload_catbox(file_path):
    """อัพโหลดไปยัง Catbox.moe (อันดับ 3: รองรับทุกไฟล์ PDF/รูปภาพ ไม่จำกัด)"""
    url = 'https://catbox.moe/user/api.php'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    for attempt in range(1, 3):
        try:
            with open(file_path, 'rb') as f:
                files = {'fileToUpload': (filename, f)}
                data = {'reqtype': 'fileupload'}
                response = requests.post(url, data=data, files=files, headers=headers, timeout=45)
                res_text = response.text.strip()
                if response.status_code == 200 and res_text.startswith('http'):
                    return res_text
                else:
                    print(f"Catbox attempt {attempt} failed ({response.status_code}): {res_text[:120]}", file=sys.stderr)
        except Exception as e:
            print(f"Catbox attempt {attempt} error: {e}", file=sys.stderr)
        if attempt < 2:
            time.sleep(1)
    return None

def upload_tmpfiles(file_path):
    """อัพโหลดไปยัง tmpfiles.org (อันดับ 4: 1hr expiry) - สำรองสุดท้าย"""
    url = 'https://tmpfiles.org/api/v1/upload'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'expire': '3600'}
            response = requests.post(url, data=data, files=files, headers=headers, timeout=20)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success' and result.get('data', {}).get('url'):
                    original_url = result['data']['url']
                    download_url = original_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    return download_url
            print(f"tmpfiles.org failed: {response.text[:120]}", file=sys.stderr)
    except Exception as e:
        print(f"tmpfiles.org error: {e}", file=sys.stderr)
    return None

def upload_uguu(file_path):
    """อัพโหลดไปยัง Uguu.se (1hr expiry) - สำรองเสริมเฉพาะรูปภาพ"""
    url = 'https://uguu.se/upload'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    try:
        with open(file_path, 'rb') as f:
            files = {'files[]': (filename, f)}
            response = requests.post(url, files=files, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('files'):
                    return result['files'][0]['url']
            print(f"Uguu failed: {response.text[:120]}", file=sys.stderr)
    except Exception as e:
        print(f"Uguu error: {e}", file=sys.stderr)
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path"}))
        sys.exit(1)

    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)

    result = None
    source = None
    
    # ตรวจสอบประเภทไฟล์
    extension = os.path.splitext(file_path)[1].lower()
    is_pdf = extension == '.pdf'
    is_image = extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    
    # === สำหรับไฟล์ PDF ===
    if is_pdf:
        # อันดับ 1: Litterbox (1hr expiry)
        print("กำลังลองอัปโหลด: Litterbox (อันดับ 1)...", file=sys.stderr)
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # อันดับ 2: Firebase Cloud
        if not result:
            print("กำลังลองระบบสำรอง: Firebase Cloud (อันดับ 2)...", file=sys.stderr)
            result = upload_firebase(file_path)
            source = "Firebase (Private Cloud)"
            
        # อันดับ 3: Catbox.moe
        if not result:
            print("กำลังลองระบบสำรอง: Catbox.moe (อันดับ 3)...", file=sys.stderr)
            result = upload_catbox(file_path)
            source = "Catbox"
            
        # อันดับ 4: tmpfiles.org
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (อันดับ 4)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
    
    # === สำหรับรูปภาพ ===
    elif is_image:
        # อันดับ 1: Litterbox (1hr expiry)
        print("กำลังลองอัปโหลด: Litterbox (อันดับ 1)...", file=sys.stderr)
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # อันดับ 2: Firebase Cloud
        if not result:
            print("กำลังลองระบบสำรอง: Firebase Cloud (อันดับ 2)...", file=sys.stderr)
            result = upload_firebase(file_path)
            source = "Firebase (Private Cloud)"
            
        # อันดับ 3: Catbox.moe
        if not result:
            print("กำลังลองระบบสำรอง: Catbox.moe (อันดับ 3)...", file=sys.stderr)
            result = upload_catbox(file_path)
            source = "Catbox"
            
        # อันดับ 4: tmpfiles.org
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (อันดับ 4)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"

        # เสริม: Uguu.se (เฉพาะรูปภาพ)
        if not result:
            print("กำลังลองระบบสำรอง: Uguu.se...", file=sys.stderr)
            result = upload_uguu(file_path)
            source = "Uguu"
    
    # === สำหรับไฟล์ประเภทอื่นๆ ===
    else:
        # อันดับ 1: Litterbox (1hr expiry)
        print("กำลังลองอัปโหลด: Litterbox (อันดับ 1)...", file=sys.stderr)
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # อันดับ 2: Firebase Cloud
        if not result:
            print("กำลังลองระบบสำรอง: Firebase Cloud (อันดับ 2)...", file=sys.stderr)
            result = upload_firebase(file_path)
            source = "Firebase (Private Cloud)"
            
        # อันดับ 3: Catbox.moe
        if not result:
            print("กำลังลองระบบสำรอง: Catbox.moe (อันดับ 3)...", file=sys.stderr)
            result = upload_catbox(file_path)
            source = "Catbox"
            
        # อันดับ 4: tmpfiles.org
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (อันดับ 4)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
    
    if result:
        print(json.dumps({"url": result, "source": source}))
    else:
        print(json.dumps({"error": "อัปโหลดล้มเหลวทั้งหมด - กรุณาลองใหม่"}))
        sys.exit(1)
