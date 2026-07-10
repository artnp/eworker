import sys
import requests
import json
import os

def upload_catbox(file_path):
    """อัพโหลดไปยัง Catbox.moe - ไม่มีวันหมดอายุ (แทน Litterbox)"""
    try:
        url = 'https://catbox.moe/user/api.php'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': (filename, f, 'application/octet-stream')}
            data = {'reqtype': 'fileupload'}
            response = requests.post(url, data=data, files=files, timeout=20)
            
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
            else:
                print(f"Catbox failed ({response.status_code}): {response.text[:150]}", file=sys.stderr)
    except Exception as e:
        print(f"Catbox error: {e}", file=sys.stderr)
    return None

def upload_litterbox(file_path):
    """อัพโหลดไปยัง Litterbox - ระบบหลัก"""
    try:
        url = 'https://litterbox.catbox.moe/resources/internals/api.php'
        filename = os.path.basename(file_path)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': (filename, f, 'application/octet-stream')}
            data = {'reqtype': 'fileupload', 'time': '1h'}
            response = requests.post(url, data=data, files=files, headers=headers, timeout=20)
            
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
            else:
                print(f"Litterbox failed ({response.status_code}): {response.text[:150]}", file=sys.stderr)
    except Exception as e:
        print(f"Litterbox error: {e}", file=sys.stderr)
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path"}))
        sys.exit(1)

    file_path = sys.argv[1]
    
    # ลอง Catbox ก่อน (permanent)
    result = upload_catbox(file_path)
    source = "Catbox"
    
    # ถ้าไม่ได้ ลอง Litterbox (1h expiry)
    if not result:
        result = upload_litterbox(file_path)
        source = "Litterbox"
    
    if result:
        print(json.dumps({"url": result, "source": source}))
    else:
        print(json.dumps({"error": "อัปโหลดล้มเหลว"}))
        sys.exit(1)
