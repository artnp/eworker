import sys
import requests
import json
import os

def upload_litterbox(file_path):
    """อัพโหลดไปยัง Litterbox (1hr expiry) - ระบบหลัก"""
    try:
        url = 'https://litterbox.catbox.moe/resources/internals/api.php'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': (filename, f)}
            data = {'reqtype': 'fileupload', 'time': '1h'}
            response = requests.post(url, data=data, files=files, timeout=20)
            
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
            else:
                print(f"Litterbox failed ({response.status_code}): {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"Litterbox error: {e}", file=sys.stderr)
    return None

def upload_tmpfiles(file_path):
    """อัพโหลดไปยัง tmpfiles.org (1hr expiry) - รองรับทุกไฟล์"""
    try:
        url = 'https://tmpfiles.org/api/v1/upload'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'expire': '3600'}  # 1 hour = 3600 seconds
            response = requests.post(url, data=data, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success' and result.get('data', {}).get('url'):
                    # tmpfiles.org returns: https://tmpfiles.org/123456/file.pdf
                    # Need to convert to direct download: https://tmpfiles.org/dl/123456/file.pdf
                    original_url = result['data']['url']
                    # Insert /dl/ after domain
                    download_url = original_url.replace('tmpfiles.org/', 'tmpfiles.org/dl/')
                    return download_url
            print(f"tmpfiles.org failed: {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"tmpfiles.org error: {e}", file=sys.stderr)
    return None

def upload_uguu(file_path):
    """อัพโหลดไปยัง Uguu.se (1hr expiry) - รองรับเฉพาะรูปภาพ"""
    try:
        url = 'https://uguu.se/upload'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'files[]': (filename, f)}
            response = requests.post(url, files=files, timeout=30)
            
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
    try:
        url = 'https://file.io/'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            # expires=1d means 1 day (free tier max)
            data = {'expires': '1d'}
            response = requests.post(url, data=data, files=files, timeout=30)
            
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
        
        # 2nd: tmpfiles.org (รองรับ PDF)
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (1hr)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
        
        # 3rd: file.io (สำหรับ PDF - ลบหลังโหลด 1 ครั้ง)
        if not result:
            print("กำลังลองระบบสำรอง: file.io (ลบหลังโหลด 1 ครั้ง)...", file=sys.stderr)
            result = upload_fileio(file_path)
            source = "file.io"
    
    # === สำหรับรูปภาพ ===
    elif is_image:
        # 1st: Litterbox (รองรับรูปภาพ)
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # 2nd: tmpfiles.org (รองรับรูปภาพ)
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (1hr)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
        
        # 3rd: Uguu.se (รองรับเฉพาะรูปภาพ)
        if not result:
            print("กำลังลองระบบสำรอง: Uguu.se (1hr)...", file=sys.stderr)
            result = upload_uguu(file_path)
            source = "Uguu"
        
        # 4th: file.io (สำรองสุดท้าย)
        if not result:
            print("กำลังลองระบบสำรอง: file.io (ลบหลังโหลด 1 ครั้ง)...", file=sys.stderr)
            result = upload_fileio(file_path)
            source = "file.io"
    
    # === สำหรับไฟล์ประเภทอื่นๆ ===
    else:
        # 1st: Litterbox
        result = upload_litterbox(file_path)
        source = "Litterbox"
        
        # 2nd: tmpfiles.org
        if not result:
            print("กำลังลองระบบสำรอง: tmpfiles.org (1hr)...", file=sys.stderr)
            result = upload_tmpfiles(file_path)
            source = "tmpfiles.org"
        
        # 3rd: file.io
        if not result:
            print("กำลังลองระบบสำรอง: file.io (ลบหลังโหลด 1 ครั้ง)...", file=sys.stderr)
            result = upload_fileio(file_path)
            source = "file.io"
    
    if result:
        print(json.dumps({"url": result, "source": source}))
    else:
        print(json.dumps({"error": "อัปโหลดล้มเหลวทั้งหมด - กรุณาลองใหม่"}))
        sys.exit(1)
