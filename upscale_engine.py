import os
import sys
import subprocess
import zipfile
import urllib.request
import re
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "assets", "tools")
REAL_ESRGAN_DIR = os.path.join(TOOLS_DIR, "realesrgan-ncnn-vulkan")
REAL_ESRGAN_EXE = os.path.join(REAL_ESRGAN_DIR, "realesrgan-ncnn-vulkan.exe")
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")

RELEASE_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip"

_progress_state = {
    "status": "idle",       # "idle", "running", "completed", "error"
    "percent": 0,
    "step_num": 0,
    "step_total": 3,
    "step_title": "พร้อมใช้งาน",
    "detail": ""
}

def get_upscale_progress():
    return _progress_state

def _set_progress(status, percent, step_num, step_title, detail=""):
    global _progress_state
    _progress_state = {
        "status": status,
        "percent": int(percent),
        "step_num": step_num,
        "step_total": 3,
        "step_title": step_title,
        "detail": detail
    }

def ensure_upscaler_installed(progress_callback=None):
    """
    ตรวจเช็คว่ามี realesrgan-ncnn-vulkan.exe หรือไม่ ถ้ายังไม่มีจะดาวน์โหลดและแตกไฟล์ให้อัตโนมัติ
    """
    if os.path.exists(REAL_ESRGAN_EXE):
        return True

    # ตรวจเช็คว่ามีติดตั้งในระบบหรือ path อื่นๆ เช่น Upscayl หรือไม่
    possible_paths = [
        REAL_ESRGAN_EXE,
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "upscayl", "resources", "bin", "upscayl-bin.exe"),
        os.path.join(os.environ.get("ProgramFiles", ""), "Upscayl", "resources", "bin", "upscayl-bin.exe"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            return True

    os.makedirs(REAL_ESRGAN_DIR, exist_ok=True)
    zip_path = os.path.join(TOOLS_DIR, "realesrgan.zip")
    
    try:
        if progress_callback:
            progress_callback("กำลังดาวน์โหลดโมเดล Real-ESRGAN AI (ประมาณ 25MB)...")
        print(f"[Upscale] Downloading Real-ESRGAN AI from {RELEASE_URL}...")
        
        headers = {'User-Agent': 'Mozilla/5.0'}
        req = urllib.request.Request(RELEASE_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp, open(zip_path, 'wb') as out_f:
            out_f.write(resp.read())
            
        print("[Upscale] Extracting files...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(REAL_ESRGAN_DIR)
            
        if os.path.exists(zip_path):
            os.remove(zip_path)
            
        print(f"[Upscale] Successfully installed to {REAL_ESRGAN_DIR}")
        return os.path.exists(REAL_ESRGAN_EXE)
    except Exception as e:
        print(f"[Upscale] Download/Install error: {e}")
        return False

def get_upscaler_executable():
    if os.path.exists(REAL_ESRGAN_EXE):
        return REAL_ESRGAN_EXE
    # Check Upscayl app paths
    upscayl_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "upscayl", "resources", "bin", "upscayl-bin.exe")
    if os.path.exists(upscayl_path):
        return upscayl_path
    return None

def upscale_image(image_path=None, scale=2, model_name="realesrgan-x4plus", tile_size=256):
    """
    ทำ AI Upscale ภาพ และเขียนทับลงที่ image_path
    พร้อมทั้งอัปเดตลายน้ำ example.png บน Desktop อัตโนมัติ
    - realesrgan-x4plus: สำหรับภาพถ่ายจริง คนจริง ทัศนียภาพ สมจริง คมชัด
    - realesr-animevideov3: สำหรับภาพการ์ตูน ภาพวาด ลายเส้น
    """
    if not image_path:
        image_path = os.path.join(DESKTOP_PATH, "complete.png")

    # 🚫 ป้องกันเด็ดขาด: ห้ามยุ่งกับไฟล์ complete_bot.png หรือระบบ Facebook_Bot
    fname_lower = os.path.basename(image_path).lower()
    if "complete_bot" in fname_lower or "bot" in fname_lower:
        print(f"[Upscale] 🚫 Blocked: {image_path} is complete_bot.png. Upscale is forbidden for Facebook_Bot.")
        _set_progress("error", 0, 1, "🚫 ไม่อนุญาตให้ Upscale ไฟล์ complete_bot.png", "Facebook_Bot ไม่ใช้ระบบ Upscale")
        return {
            "success": False,
            "error": "Forbidden: complete_bot.png is reserved for Facebook_Bot and cannot be upscaled.",
            "path": image_path
        }
    
    if not os.path.exists(image_path):
        _set_progress("error", 0, 1, "❌ ไม่พบไฟล์เป้าหมาย", str(image_path))
        raise FileNotFoundError(f"ไม่พบไฟล์: {image_path}")

    _set_progress("running", 5, 1, "ขั้นตอนที่ 1/3: กำลังเตรียมไฟล์และโหลดโมเดล Real-ESRGAN...", "ตรวจสอบ GPU และโมเดล...")

    # ตรวจสอบตัว Executable
    exe = get_upscaler_executable()
    if not exe:
        _set_progress("running", 8, 1, "ขั้นตอนที่ 1/3: กำลังดาวน์โหลดโมเดล Real-ESRGAN AI...", "ดาวน์โหลดไบนารี...")
        installed = ensure_upscaler_installed()
        if installed:
            exe = get_upscaler_executable()

    temp_out = os.path.join(os.path.dirname(image_path), f"temp_upscaled_{int(scale)}x.png")
    if os.path.exists(temp_out):
        try:
            os.remove(temp_out)
        except Exception:
            pass

    _set_progress("running", 12, 2, "ขั้นตอนที่ 2/3: กำลังประมวลผลเพิ่มความคมชัดระดับสมจริงด้วย AI (0%)...", "เริ่มต้นคำนวณพิกเซล...")
    
    # ถ้ามี binary ของ Real-ESRGAN ให้ใช้ GPU/Vulkan AI
    if exe and os.path.exists(exe):
        cmd = [
            exe,
            "-i", image_path,
            "-o", temp_out,
            "-s", str(scale),
            "-n", model_name,
            "-t", str(tile_size),
            "-g", "0",
            "-f", "png"
        ]
        exe_dir = os.path.dirname(exe)
        print(f"[Upscale] Running Realistic AI: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            cwd=exe_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        for line in iter(process.stdout.readline, ''):
            line_str = line.strip()
            if not line_str:
                continue
            if '%' in line_str:
                match = re.search(r'([\d\.]+)%', line_str)
                if match:
                    raw_pct = float(match.group(1))
                    # Map 0..100% of AI into 12..88% overall
                    overall = int(12 + (raw_pct * 0.76))
                    _set_progress(
                        "running",
                        overall,
                        2,
                        f"ขั้นตอนที่ 2/3: กำลังประมวลผล AI Real-ESRGAN ({int(raw_pct)}%)...",
                        f"ขยายความละเอียดและกู้คืนรายละเอียดสมจริง {raw_pct:.1f}%"
                    )

        process.wait()
        if process.returncode != 0:
            _set_progress("error", 0, 2, "❌ ประมวลผล AI ล้มเหลว", "เกิดข้อผิดพลาดในการรันโมเดล")
            raise RuntimeError(f"Upscale process returned code {process.returncode}")
    else:
        # Fallback กรณีไม่มี binary: ใช้ Lanczos + Sharpen คุณภาพสูง
        _set_progress("running", 50, 2, "ขั้นตอนที่ 2/3: ขยายภาพด้วย Lanczos High-Res...", "ประมวลผล...")
        with Image.open(image_path) as img:
            from PIL import ImageFilter
            orig_w, orig_h = img.size
            new_size = (int(orig_w * scale), int(orig_h * scale))
            up_img = img.resize(new_size, Image.Resampling.LANCZOS)
            up_img = up_img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=120, threshold=3))
            up_img.save(temp_out, format="PNG")

    if not os.path.exists(temp_out):
        _set_progress("error", 0, 2, "❌ ไม่พบไฟล์ผลลัพธ์", "temp output file missing")
        raise RuntimeError("Upscale output file not generated")

    _set_progress("running", 90, 3, "ขั้นตอนที่ 3/3: กำลังบันทึก complete.png และสร้างลายน้ำ example.png...", "เขียนไฟล์ทับลง Desktop...")

    # แทนที่ไฟล์เป้าหมาย (เช่น complete.png)
    if os.path.exists(image_path):
        try:
            os.remove(image_path)
        except Exception:
            pass
    import shutil
    shutil.move(temp_out, image_path)
    print(f"[Upscale] ✅ Overwritten target image: {image_path}")

    # สร้างและทับ example.png บน Desktop
    example_path = os.path.join(DESKTOP_PATH, "example.png")
    try:
        from watermark_engine import create_anti_ai_watermark
        with Image.open(image_path) as img:
            example_img = create_anti_ai_watermark(img)
            example_img.save(example_path, format="PNG")
            print(f"[Upscale] ✅ Overwritten watermarked preview: {example_path}")
    except Exception as e:
        print(f"[Upscale] Watermark generation warning: {e}")

    _set_progress("completed", 100, 3, "✨ เสร็จสิ้น! เพิ่มความคมชัดและสร้างลายน้ำสำเร็จ 100%", "บันทึกทับ Desktop/complete.png และ example.png เรียบร้อย")

    return {
        "success": True,
        "path": image_path,
        "example_path": example_path,
        "scale": scale,
        "model": model_name
    }

if __name__ == "__main__":
    print("Testing ensure_upscaler_installed...")
    ok = ensure_upscaler_installed()
    print("Installed:", ok)
