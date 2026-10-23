# -*- coding: utf-8 -*-
"""
text_touch_engine.py
ระบบจัดการเบื้องหลังสำหรับบริการ Text-Touch (eworker/shop/services/text-touch)
- จัดการเปิดไฟล์เข้า Photoshop
- พาดลายน้ำ (Watermark) เฉพาะจุดตำแหน่งที่ลูกค้าต้องการแก้ไข
- อัปเดตสถานะและรูปตัวอย่างขึ้น Firebase Realtime Database
"""

import os
import sys
import json
import base64
import urllib.request
import subprocess
from PIL import Image, ImageDraw, ImageFont

FIREBASE_DB_URL = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app"
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
DEFAULT_TARGET_PNG = os.path.join(DESKTOP_PATH, "text_touch_complete.png")

def get_photoshop_path():
    """ค้นหาตำแหน่ง Photoshop.exe จาก Registry หรือ Path ทั่วไป"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Photoshop.exe")
        path, _ = winreg.QueryValueEx(key, "")
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    
    # Fallback paths
    candidates = [
        r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2022\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2021\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop CC 2019\Photoshop.exe"
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "photoshop"

def download_session_file(session_id, file_url):
    """ดาวน์โหลดไฟล์ต้นฉบับจาก Firebase temp_files มาไว้ที่เครื่องเพื่อเปิดใน PS"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    temp_dir = os.path.join(script_dir, "cache", "text_touch")
    os.makedirs(temp_dir, exist_ok=True)
    
    target_path = os.path.join(temp_dir, f"{session_id}_original.jpg")
    
    if file_url.startswith("fb_"):
        file_key = file_url.replace("fb_", "")
        req_url = f"{FIREBASE_DB_URL}/temp_files/{file_key}.json"
        with urllib.request.urlopen(req_url, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and "data" in data:
                raw_bytes = base64.b64decode(data["data"])
                ext = ".pdf" if data.get("type") == "pdf" or data.get("filename", "").endswith(".pdf") else ".jpg"
                target_path = os.path.join(temp_dir, f"{session_id}_original{ext}")
                with open(target_path, "wb") as f:
                    f.write(raw_bytes)
                return target_path
    elif file_url.startswith("http"):
        with urllib.request.urlopen(file_url, timeout=15) as resp:
            with open(target_path, "wb") as f:
                f.write(resp.read())
        return target_path
    
    return None

def open_in_photoshop(session_id, file_url):
    """สั่งเปิดรูปภาพเข้าโปรแกรม Photoshop"""
    local_file = download_session_file(session_id, file_url)
    if not local_file or not os.path.exists(local_file):
        print(f"[Text-Touch] ❌ ไม่สามารถดาวน์โหลดไฟล์เพื่อเปิดใน Photoshop ได้ ({file_url})")
        return False
    
    ps_exe = get_photoshop_path()
    print(f"[Text-Touch] 🎨 กำลังเปิด Photoshop: {local_file}")
    subprocess.Popen([ps_exe, local_file])
    
    # บันทึกสถานะว่ากำลังทำ session นี้อยู่
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "text_touch_active.json")
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({"active_session_id": session_id, "file_path": local_file}, f, indent=2)
        
    return True

def apply_point_watermark(image_path, marker_box, output_path=None):
    """
    พาดลายน้ำทับเฉพาะกรอบพิกัดของจุดที่แก้ไข { x, y, width, height }
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"ไม่พบไฟล์รูปภาพ: {image_path}")
        
    img = Image.open(image_path).convert("RGBA")
    W, H = img.size
    
    # คำนวณพิกัดพิกเซลจริงจาก %
    mx = int(W * (marker_box.get('x', 0) / 100.0))
    my = int(H * (marker_box.get('y', 0) / 100.0))
    mw = int(W * (marker_box.get('width', 10) / 100.0))
    mh = int(H * (marker_box.get('height', 10) / 100.0))
    
    # ปรับขอบเขต
    mx = max(0, min(W - 1, mx))
    my = max(0, min(H - 1, my))
    mw = max(10, min(W - mx, mw))
    mh = max(10, min(H - my, mh))
    
    # สร้าง Layer ลายน้ำโปร่งใส
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)
    
    # 1. วาดกรอบสีส้ม-แดงเตือนว่ารอชำระเงิน
    draw.rectangle([mx, my, mx + mw, my + mh], fill=(239, 68, 68, 80), outline=(239, 68, 68, 220), width=3)
    
    # 2. วาดเส้นทแยงมุมลายน้ำ
    step = 16
    for offset in range(-mh, mw + mh, step):
        p1 = (mx + offset, my)
        p2 = (mx + offset + mh, my + mh)
        draw.line([p1, p2], fill=(255, 255, 255, 120), width=2)
        
    # 3. ใส่ตัวหนังสือ DEMO / รอชำระเงิน
    try:
        font_size = max(12, int(min(mw, mh) * 0.35))
        font = ImageFont.truetype("C:/Windows/Fonts/tahoma.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
        
    label = "PREVIEW - รอชำระ"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    
    tx = mx + (mw - tw) // 2
    ty = my + (mh - th) // 2
    
    # ป้ายพื้นหลังตัวหนังสือ
    draw.rectangle([tx - 4, ty - 2, tx + tw + 4, ty + th + 2], fill=(15, 23, 42, 200))
    draw.text((tx, ty), label, font=font, fill=(254, 240, 138, 255))
    
    # ผสานภาพ
    final_img = Image.alpha_composite(img, overlay).convert("RGB")
    
    if not output_path:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_watermarked.jpg"
        
    final_img.save(output_path, "JPEG", quality=90)
    return output_path

def submit_active_point_from_photoshop():
    """
    ทำงานเมื่อกดปุ่ม Action ใน Photoshop (บันทึกเสร็จแล้วส่งขึ้น Cloud ทันที)
    """
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "text_touch_active.json")
    if not os.path.exists(state_file):
        print("[Text-Touch] ⚠️ ไม่พบข้อมูลเซสชันที่กำลังทำอยู่")
        return False
        
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
        
    session_id = state.get("active_session_id")
    if not session_id:
        print("[Text-Touch] ⚠️ ไม่มี session_id ที่ใช้งานอยู่")
        return False
        
    # ดึงข้อมูล Markers จาก Firebase
    req_url = f"{FIREBASE_DB_URL}/text_touch/sessions/{session_id}/markers.json"
    with urllib.request.urlopen(req_url) as resp:
        markers = json.loads(resp.read().decode('utf-8')) or {}
        
    # ค้นหาจุดที่กำลังทำอยู่ (working หรือ waiting ตัวแรก)
    target_marker = None
    for m_id, m in sorted(markers.items(), key=lambda x: x[1].get('number', 0)):
        if m.get('status') in ('working', 'waiting'):
            target_marker = m
            break
            
    if not target_marker:
        print("[Text-Touch] ⚠️ ไม่พบจุดที่รอการแก้ไขในเซสชันนี้")
        return False
        
    marker_id = target_marker.get('id')
    print(f"[Text-Touch] 🎯 กำลังประมวลผลจุดที่ {target_marker.get('number')}: {marker_id}")
    
    # ตรวจสอบไฟล์ complete.png
    input_file = DEFAULT_TARGET_PNG
    if not os.path.exists(input_file):
        # Fallback to desktop complete.png
        input_file = os.path.join(DESKTOP_PATH, "complete.png")
        
    if not os.path.exists(input_file):
        print(f"[Text-Touch] ❌ ไม่พบไฟล์ผลลัพธ์จาก Photoshop: {input_file}")
        return False
        
    # 1. พาดลายน้ำเฉพาะจุดนั้น
    watermarked_path = apply_point_watermark(input_file, target_marker)
    print(f"[Text-Touch] ✅ พาดลายน้ำสำเร็จ: {watermarked_path}")
    
    # 2. แปลงเป็น Base64 และบันทึกขึ้น Firebase
    with open(watermarked_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode('utf-8')
        
    preview_key = f"preview_{session_id}_{marker_id}"
    temp_url = f"{FIREBASE_DB_URL}/temp_files/{preview_key}.json"
    
    payload = json.dumps({
        "data": b64_data,
        "type": "image",
        "createdAt": int(os.path.getmtime(watermarked_path) * 1000)
    }).encode('utf-8')
    
    req = urllib.request.Request(temp_url, data=payload, method="PUT", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)
    
    # 3. อัปเดตสถานะของ Marker เป็น 'awaiting_payment'
    marker_update_url = f"{FIREBASE_DB_URL}/text_touch/sessions/{session_id}/markers/{marker_id}.json"
    update_data = json.dumps({
        "status": "awaiting_payment",
        "previewUrl": f"fb_{preview_key}",
        "watermarked": True
    }).encode('utf-8')
    
    req2 = urllib.request.Request(marker_update_url, data=update_data, method="PATCH", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req2)
    
    print(f"[Text-Touch] 🚀 ส่งงานจุดที่ {target_marker.get('number')} ให้ลูกค้าตรวจพร้อมขึ้นบิลชำระเงินเรียบร้อยแล้ว!")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--submit":
        submit_active_point_from_photoshop()
    elif len(sys.argv) > 2 and sys.argv[1] == "--open":
        open_in_photoshop(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
    else:
        print("Usage:")
        print("  python text_touch_engine.py --open <sessionId> <fileUrl>")
        print("  python text_touch_engine.py --submit")
