import sys
import requests
import json
import os
import time

def upload_catbox(file_path):
    """อัพโหลดไปยัง Catbox.moe (ไม่มีวันหมดอายุ แต่เสถียรกว่า Litterbox)"""
    try:
        url = 'https://catbox.moe/user/api.php'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': (filename, f)}
            data = {'reqtype': 'fileupload'}
            response = requests.post(url, data=data, files=files, timeout=30)
            
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
            else:
                print(f"Catbox failed: {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"Catbox error: {e}", file=sys.stderr)
    return None

def upload_pixeldrain(file_path):
    """อัพโหลดไปยัง Pixeldrain - ไม่รองรับ auto-delete ต้องลบเอง"""
    # Pixeldrain ไม่รองรับ 1hr auto-delete - ข้าม
    return None

def upload_gofile(file_path):
    """อัพโหลดไปยัง GoFile - ไม่รองรับ 1hr auto-delete"""
    # GoFile ต่ำสุด 10 วัน - ไม่เหมาะสำหรับไฟล์ลับ
    return None

def upload_0x0(file_path):
    """อัพโหลดไปยัง 0x0.st - รองรับ 1 day minimum"""
    # 0x0.st ต่ำสุด 1 วัน - ไม่เหมาะสำหรับไฟล์ลับ
    return None

def upload_wormhole(file_path):
    """อัพโหลดไปยัง Wormhole.app (ต้องติดตั้ง wormhole-cli ก่อน)"""
    try:
        import subprocess
        
        # Check if wormhole-cli is installed
        result = subprocess.run(
            ['wormhole-cli', '--version'],
            capture_output=True,
            timeout=5,
            shell=True
        )
        
        if result.returncode != 0:
            print("Wormhole-cli not installed. Skipping...", file=sys.stderr)
            return None
        
        # Upload file
        result = subprocess.run(
            ['wormhole-cli', '-q', file_path],
            capture_output=True,
            timeout=120,
            text=True,
            shell=True
        )
        
        if result.returncode == 0:
            url = result.stdout.strip()
            if url.startswith('https://wormhole.app/'):
                return url
        
        print(f"Wormhole upload failed: {result.stderr[:200]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("Wormhole upload timeout", file=sys.stderr)
    except FileNotFoundError:
        print("Wormhole-cli not found. Install from: https://github.com/Mimickal/wormhole-cli", file=sys.stderr)
    except Exception as e:
        print(f"Wormhole error: {e}", file=sys.stderr)
    return None

def upload_uguu(file_path):
    """อัพโหลดไปยัง Uguu.se (1-48hr, configurable to 1hr)"""
    try:
        url = 'https://uguu.se/upload'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'files[]': (filename, f)}
            # Uguu supports 1hr expiry
            response = requests.post(url, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success') and result.get('files'):
                    return result['files'][0]['url']
            print(f"Uguu failed: {response.text[:200]}", file=sys.stderr)
    except Exception as e:
        print(f"Uguu error: {e}", file=sys.stderr)
    return None

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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path"}))
        sys.exit(1)

    file_path = sys.argv[1]
    result = None
    source = None
    
    # Try Litterbox first (1hr expiry - ระบบหลัก)
    result = upload_litterbox(file_path)
    source = "Litterbox"
    
    # Fallback 1: Wormhole.app (encrypted, auto-expire - ถ้าติดตั้งแล้ว)
    if not result:
        print("กำลังลองระบบสำรอง: Wormhole.app (encrypted)...", file=sys.stderr)
        result = upload_wormhole(file_path)
        source = "Wormhole"
    
    # Fallback 2: Uguu.se (1hr expiry - เสถียร)
    if not result:
        print("กำลังลองระบบสำรอง: Uguu.se (1hr)...", file=sys.stderr)
        result = upload_uguu(file_path)
        source = "Uguu"
    
    # ไม่มีระบบสำรองอื่นที่รองรับ 1hr - ล้มเหลวหากทั้ง 2 ระบบไม่ทำงาน
    
    if result:
        print(json.dumps({"url": result, "source": source}))
    else:
        print(json.dumps({"error": "อัปโหลดล้มเหลว - ไม่มีบริการที่รองรับ 1hr expiry พร้อมใช้งาน"}))
        sys.exit(1)
    
    if result:
        print(json.dumps({"url": result, "source": source}))
    else:
        print(json.dumps({"error": "อัปโหลดล้มเหลว"}))
        sys.exit(1)
