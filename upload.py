import sys
import requests
import json
import os
import random
import string
import tempfile
import shutil
from PIL import Image

def scrub_and_poison(file_path):
    """
    ล้าง Metadata ของภาพ (ไม่เติม junk data ที่อาจทำให้ไฟล์เสีย)
    """
    ext = os.path.splitext(file_path)[1].lower()
    is_image = ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']
    
    # สร้างไฟล์ชั่วคราว
    temp_dir = tempfile.gettempdir()
    random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    temp_path = os.path.join(temp_dir, f"ghost_{random_name}{ext}")

    try:
        if is_image:
            # --- Clean Metadata (Scrubbing) ---
            with Image.open(file_path) as img:
                # แปลงเป็น RGB ถ้าเป็น JPEG เพื่อความแน่นอนในการล้างข้อมูล
                if ext in ['.jpg', '.jpeg'] and img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # บันทึกเป็นไฟล์ใหม่ (ล้าง Metadata)
                if ext in ['.jpg', '.jpeg']:
                    img.save(temp_path, quality=95, subsampling=0)
                elif ext == '.png':
                    img.save(temp_path, optimize=True)
                else:
                    img.save(temp_path)
            
            # ไม่เติม junk data เพราะอาจทำให้ไฟล์เสีย
            return temp_path
        else:
            # สำหรับไฟล์อื่นๆ (เช่น PDF) ให้ Copy ตรงๆ
            shutil.copy2(file_path, temp_path)
            return temp_path
            
    except Exception as e:
        # หากเกิดข้อผิดพลาด ให้ใช้ไฟล์ต้นฉบับแทน (Safe Fallback)
        import sys
        print(f"Warning: Could not process file: {e}", file=sys.stderr)
        return file_path

def upload_litterbox(file_path):
    """อัพโหลดไปยัง Litterbox (อาจถูกบล็อกบางครั้ง)"""
    try:
        url = 'https://litterbox.catbox.moe/resources/internals/api.php'
        filename = os.path.basename(file_path)
        
        # เพิ่ม headers เพื่อให้ดูเหมือน browser จริง
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://litterbox.catbox.moe',
            'Referer': 'https://litterbox.catbox.moe/'
        }
        
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': (filename, f, 'application/octet-stream')}
            data = {
                'reqtype': 'fileupload',
                'time': '1h'
            }
            response = requests.post(url, data=data, files=files, headers=headers, timeout=20)
            
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
            else:
                import sys
                print(f"Litterbox upload failed (Status {response.status_code}): {response.text[:200]}", file=sys.stderr)
                
    except Exception as e:
        import sys
        print(f"Litterbox upload error: {e}", file=sys.stderr)
    return None

def upload_tmpfiles(file_path):
    """อัพโหลดไปยัง TmpFiles.org (ระบบสำรอง)"""
    try:
        url = 'https://tmpfiles.org/api/v1/upload'
        filename = os.path.basename(file_path)
        
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f, 'application/octet-stream')}
            response = requests.post(url, files=files, timeout=30)
            
            if response.status_code == 200:
                res_data = response.json()
                # TmpFiles returns: {"status": "success", "data": {"url": "https://tmpfiles.org/dl/xxx/file.jpg"}}
                if res_data.get('status') == 'success' and res_data.get('data', {}).get('url'):
                    full_url = res_data['data']['url']
                    # URL format: https://tmpfiles.org/dl/wuwaYvwgVKsn/file.jpg
                    # Extract the file ID (between /dl/ and /filename)
                    parts = full_url.split('/')
                    if len(parts) >= 5 and parts[3] == 'dl':
                        file_id = parts[4]  # wuwaYvwgVKsn
                        # Return with tf_ prefix so PrivateSend knows it's TmpFiles
                        return f"tf_{file_id}"
    except Exception as e:
        import sys
        print(f"TmpFiles upload error: {e}", file=sys.stderr)
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path provided"}))
        sys.exit(1)

    original_file = sys.argv[1]
    
    # บรรจุเข้าระบบ Digital Ghosting ก่อนส่ง
    processed_file = scrub_and_poison(original_file)
    
    try:
        # Try Litterbox ก่อน (ระบบหลัก)
        result_url = upload_litterbox(processed_file)
        source = "Litterbox"
        
        # Fallback to TmpFiles (ระบบสำรอง)
        if not result_url:
            result_url = upload_tmpfiles(processed_file)
            source = "TempFile"
            
        if result_url:
            print(json.dumps({"url": result_url, "source": source}))
        else:
            print(json.dumps({"error": "อัปโหลดล้มเหลวทั้งสองระบบ"}))
            sys.exit(1)
            
    finally:
        # ลบไฟล์ชั่วคราวทิ้งเสมอเมื่อจบงาน
        if processed_file != original_file and os.path.exists(processed_file):
            try:
                os.remove(processed_file)
            except:
                pass
