import sys
import os
import subprocess
import tempfile
import time
import random
import string
import ctypes
import ctypes.wintypes
import base64

# --- ติดตั้ง dependencies ที่จำเป็นก่อน ---
def ensure_deps():
    try:
        from PIL import Image
        import qrcode
        import requests
        import pyautogui
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'Pillow', 'qrcode[pil]', 'requests', 'pyautogui', '--quiet'], check=True)

ensure_deps()

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import qrcode
import requests
import pyautogui

# ตั้งค่าความเร็วสูงสุด
pyautogui.PAUSE = 0
pyautogui.FAILSAFE = False

def scrub_and_poison(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    temp_dir = tempfile.gettempdir()
    random_name = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    temp_path = os.path.join(temp_dir, f"donate_{random_name}{ext}")
    try:
        with Image.open(file_path) as img:
            if ext in ['.jpg', '.jpeg'] and img.mode != 'RGB':
                img = img.convert('RGB')
            if ext in ['.jpg', '.jpeg']:
                img.save(temp_path, quality=95, subsampling=0)
            else:
                img.save(temp_path)
        with open(temp_path, 'ab') as f:
            random_junk = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
            f.write(f"\n#DN_{random_junk}".encode())
        return temp_path
    except Exception:
        return file_path

def upload_litterbox_24h(file_path):
    try:
        url = 'https://litterbox.catbox.moe/resources/internals/api.php'
        with open(file_path, 'rb') as f:
            files = {'fileToUpload': f}
            data = {'reqtype': 'fileupload', 'time': '24h'}
            response = requests.post(url, data=data, files=files, timeout=60)
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
    except Exception as e:
        print(f"Upload error: {e}")
    return None

def generate_qr_image(data, size=120):
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size, size), Image.LANCZOS)
    return img

def copy_image_to_clipboard(file_path):
    try:
        abs_path = os.path.abspath(file_path).replace('/', '\\')
        ps_cmd = f"Add-Type -AssemblyName System.Windows.Forms; $img = [System.Drawing.Image]::FromFile('{abs_path}'); [System.Windows.Forms.Clipboard]::SetImage($img); $img.Dispose()"
        result = subprocess.run(
            f'cmd /c powershell -STA -ExecutionPolicy Bypass -WindowStyle Hidden -Command "{ps_cmd}"',
            shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"[Clipboard] PowerShell error: {result.stderr}")
        else:
            print(f"[Clipboard] Image copied to clipboard OK")
    except Exception as e:
        print(f"[Clipboard] Error: {e}")

def auto_paste():
    try:
        user32 = ctypes.windll.user32
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        def _get_title(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0: return ""
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value

        def _find_window_by_keywords(keywords):
            matches = []
            @EnumWindowsProc
            def _enum(hwnd, lparam):
                title = _get_title(hwnd)
                if not title: return True
                title_lower = title.lower()
                for kw in keywords:
                    if kw.lower() in title_lower:
                        matches.append((hwnd, title))
                        break
                return True
            user32.EnumWindows(_enum, 0)
            return matches

        def _force_foreground(hwnd):
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            return True

        def _parse_coords(title):
            try:
                import re
                if 'READY_TO_PASTE|' in title:
                    pattern = r'READY_TO_PASTE\|([\d\.]+)\|([\d\.]+)'
                    match = re.search(pattern, title)
                    if match:
                        return int(float(match.group(1))), int(float(match.group(2)))
                return None
            except: return None

        print("[System] Mouse control sequence ACTIVATED.")
        target_hwnd, coords = None, None
        
        for i in range(300):
            wins = _find_window_by_keywords(['READY_TO_PASTE', 'READY_TO_POST'])
            if wins:
                for h, t in wins:
                    c = _parse_coords(t)
                    if c:
                        target_hwnd, coords = h, c
                        pyautogui.moveTo(c[0], c[1], duration=0)
                        pyautogui.click()
                        break
                if target_hwnd: break
            time.sleep(0.1)

        if not target_hwnd:
            print("[Fail] Handshake Timeout.")
            return
        
        _force_foreground(target_hwnd)
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'v')
        
        for _ in range(40):
            wins = _find_window_by_keywords(['READY_TO_POST'])
            if wins:
                _force_foreground(wins[0][0])
                time.sleep(0.6)
                pyautogui.press('enter')
                break
            time.sleep(0.5)

        print("[AutoPaste] Sequence finished.")
    except Exception as e:
        print(f"[AutoPaste] Error: {e}")

def get_white_band_height(img):
    w, h = img.size
    img_rgb = img.convert('RGB')
    for y in range(h - 1, h - int(h * 0.4), -1):
        white_count = 0
        samples = 20
        for i in range(samples):
            x = int((i / samples) * (w * 0.75))
            r, g, b = img_rgb.getpixel((x, y))
            if r > 190 and g > 190 and b > 190: white_count += 1
        if white_count < samples * 0.8:
            detected = h - y
            if detected >= 20: return detected
            else: return 0
    return int(h * 0.065)

def crop_watermark(source_path):
    if not os.path.exists(source_path):
        print(f"ไม่พบไฟล์: {source_path}")
        return None
    with Image.open(source_path) as img:
        img_rgb = img.convert('RGB')
        orig_w, orig_h = img_rgb.size
        white_band_h = get_white_band_height(img_rgb)
        if white_band_h > 0:
            crop_bottom = max(160, white_band_h) + 2
        else:
            crop_bottom = max(60, int(orig_h * 0.065))
        return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))

def process_clean_only(full_path=None):
    print("[CleanOnly] เริ่มต้น...")
    source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
    target = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'complete.png')
    img = crop_watermark(source)
    if img:
        img.save(target, format='PNG')
        print(f"[Done] {target}")
    else:
        print("[Error] Failed")

def process_donate(full_path=None):
    print("[Donate] เริ่มต้น...")
    source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
    target = os.path.join(os.environ['USERPROFILE'], 'Desktop', 'complete.png')
    
    original_img = crop_watermark(source)
    if not original_img: return

    temp_path = os.path.join(tempfile.gettempdir(), 'ps_cropped_temp.png')
    original_img.save(temp_path, format='PNG')
    
    poisoned = scrub_and_poison(temp_path)
    upload_url = upload_litterbox_24h(poisoned)
    if not upload_url: return

    b64_url = base64.b64encode(upload_url.encode()).decode()
    expiry = int((time.time() + 86400) * 1000)
    donate_link = f"https://artnp.github.io/eworker/download.html?d={b64_url}&exp={expiry}&type=img&donate=1"

    preview_img = original_img.copy()
    w, h = preview_img.size
    final_img = preview_img
    final_h = h
    scale = max(0.65, min(w / 850.0, 3.0))
    qr_size = int(145 * scale)
    qr_img = generate_qr_image(donate_link, size=qr_size).convert("RGBA")

    overlay_w, overlay_h = int(540 * scale), int(175 * scale)
    margin, radius = int(22 * scale), int(24 * scale)
    shadow_pad = int(12 * scale)

    # Fonts
    font = None
    small_font = None
    for fp in ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf"]:
        if os.path.exists(fp): 
            font = ImageFont.truetype(fp, int(22 * scale))
            small_font = ImageFont.truetype(fp, int(16 * scale))
            break
    if not font: 
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # สร้าง Overlay และ Shadow
    shadow_img = Image.new('RGBA', (overlay_w + shadow_pad*2, overlay_h + shadow_pad*2), (0,0,0,0))
    shadow_draw = ImageDraw.Draw(shadow_img)
    shadow_draw.rounded_rectangle((shadow_pad, shadow_pad, overlay_w + shadow_pad, overlay_h + shadow_pad), radius=radius, fill=(0, 0, 0, 60))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(10 * scale)))

    # Supersampling เฉพาะรูปทรงกรอบ เพื่อให้ขอบและเส้นขอบเนียน (Anti-aliasing)
    aa_scale = 3
    aa_img = Image.new('RGBA', (overlay_w * aa_scale, overlay_h * aa_scale), (0,0,0,0))
    aa_draw = ImageDraw.Draw(aa_img)
    import math

    aw = (overlay_w * aa_scale) - 1
    ah = (overlay_h * aa_scale) - 1
    ar = radius * aa_scale

    # วาดพื้นสีขาวของกรอบ (ไม่มีเส้นขอบทึบ)
    aa_draw.rounded_rectangle(
        (0, 0, aw, ah), 
        radius=ar, 
        fill=(255, 255, 255, 248)
    )

    # ฟังก์ชันคำนวณตำแหน่งจุดบนขอบของ Rounded Rectangle
    def get_rrect_point(p, w, h, r):
        seg_horiz = w - 2*r
        seg_vert = h - 2*r
        arc_len = math.pi * r / 2
        
        if p <= seg_horiz: return (r + p, 0)
        p -= seg_horiz
        if p <= arc_len:
            angle = -math.pi/2 + (p / arc_len) * (math.pi/2)
            return (w - r + r * math.cos(angle), r + r * math.sin(angle))
        p -= arc_len
        if p <= seg_vert: return (w, r + p)
        p -= seg_vert
        if p <= arc_len:
            angle = (p / arc_len) * (math.pi/2)
            return (w - r + r * math.cos(angle), h - r + r * math.sin(angle))
        p -= arc_len
        if p <= seg_horiz: return (w - r - p, h)
        p -= seg_horiz
        if p <= arc_len:
            angle = math.pi/2 + (p / arc_len) * (math.pi/2)
            return (r + r * math.cos(angle), h - r + r * math.sin(angle))
        p -= arc_len
        if p <= seg_vert: return (0, h - r - p)
        p -= seg_vert
        if p <= arc_len:
            angle = math.pi + (p / arc_len) * (math.pi/2)
            return (r + r * math.cos(angle), r + r * math.sin(angle))
        return (r, 0)

    perimeter = 2 * (aw - 2 * ar) + 2 * (ah - 2 * ar) + 2 * math.pi * ar
    dash_len = 20 * aa_scale * scale  # ความยาวเส้นปะ (ขยายให้ยาวขึ้น)
    gap_len = 14 * aa_scale * scale   # ความยาวช่องว่าง (ขยายช่องว่างให้สมดุล)
    
    dash_total = dash_len + gap_len
    num_dashes = max(1, int(perimeter / dash_total))
    
    actual_dash_total = perimeter / num_dashes
    ratio = actual_dash_total / dash_total
    actual_dash = dash_len * ratio
    
    samples = int(perimeter)
    border_color = '#f97316'
    outline_w = max(2, int(3.0 * scale)) # เพิ่มความหนาของเส้นปะ
    draw_width = outline_w * aa_scale
    
    last_pt = None
    for i in range(samples + 1):
        dist = (i / samples) * perimeter
        pt = get_rrect_point(dist, aw, ah, ar)
        if (dist % actual_dash_total) <= actual_dash:
            if last_pt:
                aa_draw.line([last_pt, pt], fill=border_color, width=draw_width)
            last_pt = pt
        else:
            last_pt = None
    
    # ย่อสเกลกลับด้วย LANCZOS เพื่อความเนียนสมบูรณ์แบบ
    overlay_img = aa_img.resize((overlay_w, overlay_h), Image.Resampling.LANCZOS)
    overlay_draw = ImageDraw.Draw(overlay_img)

    # วาง QR บน overlay
    qr_x, qr_y = int(15 * scale), int(15 * scale)
    overlay_img.paste(qr_img, (qr_x, qr_y))

    # ข้อความบน overlay
    text_x = qr_x + qr_size + int(22 * scale)
    text_y = qr_y + int(4 * scale)
    
    overlay_draw.text((text_x, text_y), ":) โปรเจคการกุศลช่วยเหลือฟรี", fill='#059669', font=font)
    overlay_draw.text((text_x, text_y + int(36 * scale)), "สแกน QR code !!", fill='#0f172a', font=font)
    overlay_draw.text((text_x, text_y + int(64 * scale)), "ดาวน์โหลดภาพเต็มชัดแจ๋ว-ไฟล์ไม่แตก!", fill='#0f172a', font=font)

    # วาดเส้นปะสีส้มคั่น
    dash_length = max(1, int(6 * scale))
    dash_gap = max(1, int(4 * scale))
    line_y = text_y + int(92 * scale)
    line_start_x = text_x
    line_end_x = overlay_w - int(20 * scale)
    for cx in range(line_start_x, line_end_x, dash_length + dash_gap):
        end_x = min(cx + dash_length, line_end_x)
        overlay_draw.line([(cx, line_y), (end_x, line_y)], fill='#f97316', width=max(1, int(1.5 * scale)))

    overlay_draw.text((text_x, text_y + int(106 * scale)), "> อยากจ้างตัดต่อส่วนตัว 60฿ | ทักแชทมาได้เลย", fill='#64748b', font=small_font)

    # วาง overlay มุมซ้ายล่าง ห่างขอบ   
    pos_x = margin
    pos_y = final_h - overlay_h - margin

    # นำมาแปะรวมเข้ากับภาพหลัก
    rgba_final = final_img.convert('RGBA')
    # แปะเงาก่อน (ออฟเซตลงมาเล็กน้อย)
    rgba_final.paste(shadow_img, (pos_x - shadow_pad, pos_y - shadow_pad + int(4 * scale)), shadow_img)
    # แปะกรอบ overlay (QR + text)
    rgba_final.paste(overlay_img, (pos_x, pos_y), overlay_img)

    final_export = rgba_final.convert('RGB')
    
    # --- Export เซฟลงเป้าหมายโดยตรง (รักษาตำแหน่งไอคอน Desktop) ---
    import io
    img_byte_arr = io.BytesIO()
    final_export.save(img_byte_arr, format='PNG')
    data = img_byte_arr.getvalue()
    
    try:
        if os.path.exists(target):
            with open(target, 'r+b') as f:
                f.seek(0)
                f.write(data)
                f.truncate()
        else:
            with open(target, 'wb') as f:
                f.write(data)
    except Exception as e:
        print(f"Error saving file: {e}")
    
    copy_image_to_clipboard(target)
    
    # --- หน่วงเวลาให้ Addon เตรียมโฟกัสกล่องคอมเมนต์ให้เสร็จก่อน แล้วทำการ Paste (Ctrl+V) ---
    time.sleep(2.0)
    auto_paste()

if __name__ == "__main__":
    mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
    target_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if mode_flag == "--clean":
        process_clean_only(target_path)
    elif mode_flag == "--donate":
        process_donate(target_path)
    else:
        process_donate()
