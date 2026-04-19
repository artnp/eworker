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
    ล้าง Metadata ของภาพ และเติมข้อมูลสุ่มท้ายไฟล์เพื่อเปลี่ยน Hash
    """
    ext = os.path.splitext(file_path)[1].lower()
    is_image = ext in ['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']
    
    # สร้างไฟล์ชั่วคราว
    temp_dir = tempfile.gettempdir()
    random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    temp_path = os.path.join(temp_dir, f"ghost_{random_name}{ext}")

    try:
        if is_image:
            # --- 1. Clean Metadata (Scrubbing) ---
            # เปิดภาพและบันทึกใหม่โดยไม่เอา EXIF/Metadata เดิมมาด้วย
            with Image.open(file_path) as img:
                # แปลงเป็น RGB ถ้าเป็น JPEG เพื่อความแน่นอนในการล้างข้อมูล
                if ext in ['.jpg', '.jpeg'] and img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # บันทึกเป็นไฟล์ใหม่ (การ save ใหม่ใน Pillow จะไม่นำ Metadata เดิมมาหากไม่สั่ง)
                if ext in ['.jpg', '.jpeg']:
                    img.save(temp_path, quality=95, subsampling=0)
                else:
                    img.save(temp_path)
        else:
            # สำหรับไฟล์อื่นๆ (เช่น PDF) ให้ใช้วิธี Copy แทนการแปลง
            shutil.copy2(file_path, temp_path)
        
        # --- 2. Change File Hash (Poisoning) ---
        # เติมข้อมูลสุ่มเล็กน้อยท้ายไฟล์ (ไม่กระทบการเปิดดู แต่ทำให้รหัสไฟล์เปลี่ยน 100%)
        with open(temp_path, 'ab') as f:
            random_junk = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            # ใส่เป็น Comment หรือข้อมูลขยะท้ายไฟล์
            f.write(f"\n#GS_{random_junk}".encode())
            
        return temp_path
    except Exception as e:
        # หากเกิดข้อผิดพลาด ให้ใช้ไฟล์ต้นฉบับแทน (Safe Fallback)
        return file_path

def upload_litterbox(file_path):
    try:
        url = 'https://litterbox.catbox.moe/resources/internals/api.php'
        # เปิดไฟล์ในโหมด 'rb' (read binary)
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            data = {
                'reqtype': 'fileupload',
                'time': '1h'
            }
            response = requests.post(url, data=data, files=files, timeout=15)
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
    except Exception:
        pass
    return None

def upload_tempfile(file_path, expiry_hours=1):
    try:
        url = 'https://tempfile.org/api/upload/local'
        with open(file_path, 'rb') as f:
            files = {'files': f}
            data = {'expiryHours': str(expiry_hours)}
            response = requests.post(url, data=data, files=files, timeout=30)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get('success') and res_data.get('files'):
                    file_id = res_data['files'][0]['id']
                    return f"https://tempfile.org/{file_id}"
    except Exception:
        pass
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No file path provided"}))
        sys.exit(1)

    original_file = sys.argv[1]
    
    # บรรจุเข้าระบบ Digital Ghosting ก่อนส่ง
    processed_file = scrub_and_poison(original_file)
    
    try:
        # Try Litterbox (ระบบหลัก)
        result_url = upload_litterbox(processed_file)
        source = "Litterbox"
        
        # Fallback to TempFile (ระบบสำรอง)
        if not result_url:
            result_url = upload_tempfile(processed_file)
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
