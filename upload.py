import sys
import requests
import json
import os

def upload_litterbox(file_path):
    """อัพโหลดไปยัง Litterbox (1hr expiry) - ระบบหลัก"""
    url = 'https://litterbox.catbox.moe/resources/internals/api.php'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    
    # ลองอัปโหลดสูงสุด 3 ครั้ง เพื่อรองรับกรณีเน็ตช้าหรือ SSL/Cloudflare ติดขัดชั่วคราว
    for attempt in range(1, 4):
        try:
            with open(file_path, 'rb') as f:
                files = {'fileToUpload': (filename, f)}
                data = {'reqtype': 'fileupload', 'time': '1h'}
                response = requests.post(url, data=data, files=files, headers=headers, timeout=60)
                res_text = response.text.strip()
                
                if response.status_code == 200 and res_text.startswith('http'):
                    return res_text
                else:
                    print(f"Litterbox attempt {attempt} failed ({response.status_code}): {res_text[:200]}", file=sys.stderr)
        except Exception as e:
            print(f"Litterbox attempt {attempt} error: {e}", file=sys.stderr)
        
        if attempt < 3:
            import time
            time.sleep(1)
            
    return None

def upload_tmpfiles(file_path):
    """อัพโหลดไปยัง tmpfiles.org (1hr expiry) - รองรับทุกไฟล์"""
    url = 'https://tmpfiles.org/api/v1/upload'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'expire': '3600'}  # 1 hour = 3600 seconds
            response = requests.post(url, data=data, files=files, headers=headers, timeout=45)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success' and result.get('data', {}).get('url'):
                    original_url = result['data']['url']
                    download_url = original_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    return download_url
            print(f"tmpfiles.org failed: {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"tmpfiles.org error: {e}", file=sys.stderr)
    return None

def upload_uguu(file_path):
    """อัพโหลดไปยัง Uguu.se (1hr expiry) - รองรับเฉพาะรูปภาพ"""
    url = 'https://uguu.se/upload'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    try:
        with open(file_path, 'rb') as f:
            files = {'files[]': (filename, f)}
            response = requests.post(url, files=files, headers=headers, timeout=45)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('files'):
                    return result['files'][0]['url']
            print(f"Uguu failed: {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"Uguu error: {e}", file=sys.stderr)
    return None

def upload_fileio(file_path):
    """อัพโหลดไปยัง file.io (ลบอัตโนมัติหลัง 1 ครั้ง หรือ 14 วัน) - รองรับทุกไฟล์"""
    url = 'https://file.io/'
    filename = os.path.basename(file_path)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    }
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'expires': '1d'}
            response = requests.post(url, data=data, files=files, headers=headers, timeout=45)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('link'):
                    return result['link']
            print(f"file.io failed: {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"file.io error: {e}", file=sys.stderr)
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path"}))
        sys.exit(1)

    file_path = sys.argv[1]
    result = None
    source = None
    
    # ตรวจสอบประเภทไฟล์
    extension = os.path.splitext(file_path)[1].lower()
    is_pdf = extension == '.pdf'
    is_image = extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    
    # === สำหรับไฟล์ PDF ===
    if is_pdf:
        # 1st: Litterbox (รองรับ PDF)
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # 2nd: file.io (สำหรับ PDF - ลบหลังโหลด 1 ครั้ง)
        if not result:
            print("กำลังลองระบบสำรอง: file.io (ลบหลังโหลด 1 ครั้ง)...", file=sys.stderr)
            result = upload_fileio(file_path)
            source = "file.io"
        
        # 3rd: tmpfiles.org (รองรับ PDF)
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (1hr)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
    
    # === สำหรับรูปภาพ ===
    elif is_image:
        # 1st: Litterbox (รองรับรูปภาพ)
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # 2nd: Uguu.se (รองรับเฉพาะรูปภาพ)
        if not result:
            print("กำลังลองระบบสำรอง: Uguu.se (1hr)...", file=sys.stderr)
            result = upload_uguu(file_path)
            source = "Uguu"
        
        # 3rd: file.io (สำรอง)
        if not result:
            print("กำลังลองระบบสำรอง: file.io (ลบหลังโหลด 1 ครั้ง)...", file=sys.stderr)
            result = upload_fileio(file_path)
            source = "file.io"
        
        # 4th: tmpfiles.org (สำรองสุดท้าย)
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (1hr)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
    
    # === สำหรับไฟล์ประเภทอื่นๆ ===
    else:
        # 1st: Litterbox
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # 2nd: file.io
        if not result:
            print("กำลังลองระบบสำรอง: file.io (ลบหลังโหลด 1 ครั้ง)...", file=sys.stderr)
            result = upload_fileio(file_path)
            source = "file.io"
        
        # 3rd: tmpfiles.org
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (1hr)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
    
    if result:
        print(json.dumps({"url": result, "source": source}))
    else:
        print(json.dumps({"error": "อัปโหลดล้มเหลวทั้งหมด - กรุณาลองใหม่"}))
        sys.exit(1)
