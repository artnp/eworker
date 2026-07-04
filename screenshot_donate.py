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
            response = requests.post(url, data=data, files=files, timeout=30)
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

def crop_watermark(source_path):
    """Crop white/blank padding from the bottom of Gemini-generated images."""
    if not os.path.exists(source_path):
        print(f"\u0e44\u0e21\u0e48\u0e1e\u0e1a\u0e44\u0e1f\u0e25\u0e4c: {source_path}")
        return None
    with Image.open(source_path) as img:
        img_rgb = img.convert('RGB')
        orig_w, orig_h = img_rgb.size

        CHUNK_H    = 20    # scan in chunks of 20px
        BRIGHT_T   = 230   # pixel is "white" if r,g,b all >= this
        WHITE_RATIO = 0.78 # chunk is white if 78%+ pixels are bright
        MAX_SCAN   = 0.55  # scan only bottom 55% of image

        last_content_y = orig_h  # assume full image has content

        for chunk_y in range(orig_h - CHUNK_H, int(orig_h * (1 - MAX_SCAN)), -CHUNK_H):
            bright = 0
            total = 0
            for y in range(chunk_y, min(chunk_y + CHUNK_H, orig_h)):
                for x in range(0, orig_w, max(1, orig_w // 60)):
                    r, g, b = img_rgb.getpixel((x, y))
                    if r >= BRIGHT_T and g >= BRIGHT_T and b >= BRIGHT_T:
                        bright += 1
                    total += 1

            ratio = bright / max(1, total)
            if ratio < WHITE_RATIO:
                # Found content — stop here, mark last content position
                last_content_y = chunk_y + CHUNK_H
                break

        crop_bottom = orig_h - last_content_y
        if crop_bottom > CHUNK_H:
            crop_bottom = min(crop_bottom + 15, int(orig_h * MAX_SCAN))  # buffer + cap
            print(f"[Crop] White band detected, crop_bottom={crop_bottom}px, original_h={orig_h}px")
            return img_rgb.crop((0, 0, orig_w, orig_h - crop_bottom))

        print(f"[Crop] No white band, crop_bottom=0, original_h={orig_h}px")
        return img_rgb


def process_clean_only(full_path=None):
    is_bot = '--bot' in sys.argv
    target_name = 'complete_bot.png' if is_bot else 'complete.png'
    print(f"[CleanOnly] เริ่มต้น... (target: {target_name})")
    source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
    target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
    img = crop_watermark(source)
    if img:
        img.save(target, format='PNG')
        print(f"[Done] {target}")
    else:
        print("[Error] Failed")

def _upload_with_timeout(file_path, timeout_sec=30):
    """Upload ไปที่ Litterbox โดยมี timeout ที่แน่นอน ผ่าน threading"""
    import threading
    result = [None]
    
    def _do_upload():
        result[0] = upload_litterbox_24h(file_path)
    
    t = threading.Thread(target=_do_upload, daemon=True)
    start = time.time()
    t.start()
    t.join(timeout=timeout_sec)
    elapsed = time.time() - start
    
    if t.is_alive():
        print(f"[Donate] Upload timeout! ({elapsed:.1f}s > {timeout_sec}s) → fallback to no-upload mode")
        return None
    
    if result[0]:
        print(f"[Donate] Upload สำเร็จใน {elapsed:.1f}s")
    else:
        print(f"[Donate] Upload ล้มเหลวใน {elapsed:.1f}s → fallback to no-upload mode")
    return result[0]

def process_donate(full_path=None):
    is_bot = '--bot' in sys.argv
    target_name = 'complete_bot.png' if is_bot else 'complete.png'
    print(f"[Donate] เริ่มต้น... (target: {target_name})")
    source = full_path if full_path else os.path.join(os.environ['USERPROFILE'], 'Downloads', 'complete.png')
    target = os.path.join(os.environ['USERPROFILE'], 'Desktop', target_name)
    
    original_img = crop_watermark(source)
    if not original_img: return

    # // ส่วนนี้ถูก bypass ทั้งหมด — upload littlebox + สร้าง QR + แถบ QR
    # // คอมเมนต์ไว้เพื่อกู้คืนได้ในอนาคต ไม่ได้ลบทิ้ง

    # temp_path = os.path.join(tempfile.gettempdir(), 'ps_cropped_temp.png')
    # original_img.save(temp_path, format='PNG')
    # poisoned = scrub_and_poison(temp_path)
    # upload_url = _upload_with_timeout(poisoned, timeout_sec=30)
    upload_url = None  # bypass: ข้ามการ upload ทั้งหมด

    # if upload_url:
    #     b64_url = base64.b64encode(upload_url.encode()).decode()
    #     expiry = int((time.time() + 86400) * 1000)
    #     donate_link = f"https://artnp.github.io/eworker/download.html?d={b64_url}&exp={expiry}&type=img&donate=1"
    #     preview_img = original_img.copy()
    #     w, h = preview_img.size
    #     final_img = preview_img
    #     final_h = h
    #     scale = max(0.65, min(w / 850.0, 3.0))
    #     qr_size = int(145 * scale)
    #     qr_img = generate_qr_image(donate_link, size=qr_size).convert("RGBA")
    #     overlay_w, overlay_h = int(540 * scale), int(175 * scale)
    #     margin, radius = int(22 * scale), int(24 * scale)
    #     shadow_pad = int(12 * scale)
    #     # Fonts
    #     font = None
    #     small_font = None
    #     for fp in ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf"]:
    #         if os.path.exists(fp):
    #             font = ImageFont.truetype(fp, int(22 * scale))
    #             small_font = ImageFont.truetype(fp, int(16 * scale))
    #             break
    #     if not font:
    #         font = ImageFont.load_default()
    #         small_font = ImageFont.load_default()
    #     # สร้าง Overlay และ Shadow
    #     shadow_img = Image.new('RGBA', (overlay_w + shadow_pad*2, overlay_h + shadow_pad*2), (0,0,0,0))
    #     shadow_draw = ImageDraw.Draw(shadow_img)
    #     shadow_draw.rounded_rectangle((shadow_pad, shadow_pad, overlay_w + shadow_pad, overlay_h + shadow_pad), radius=radius, fill=(0, 0, 0, 60))
    #     shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(10 * scale)))
    #     # Supersampling
    #     aa_scale = 3
    #     aa_img = Image.new('RGBA', (overlay_w * aa_scale, overlay_h * aa_scale), (0,0,0,0))
    #     aa_draw = ImageDraw.Draw(aa_img)
    #     import math
    #     aw = (overlay_w * aa_scale) - 1
    #     ah = (overlay_h * aa_scale) - 1
    #     ar = radius * aa_scale
    #     aa_draw.rounded_rectangle((0, 0, aw, ah), radius=ar, fill=(255, 255, 255, 248))
    #     def get_rrect_point(p, w, h, r):
    #         seg_horiz = w - 2*r
    #         seg_vert = h - 2*r
    #         arc_len = math.pi * r / 2
    #         if p <= seg_horiz: return (r + p, 0)
    #         p -= seg_horiz
    #         if p <= arc_len:
    #             angle = -math.pi/2 + (p / arc_len) * (math.pi/2)
    #             return (w - r + r * math.cos(angle), r + r * math.sin(angle))
    #         p -= arc_len
    #         if p <= seg_vert: return (w, r + p)
    #         p -= seg_vert
    #         if p <= arc_len:
    #             angle = (p / arc_len) * (math.pi/2)
    #             return (w - r + r * math.cos(angle), h - r + r * math.sin(angle))
    #         p -= arc_len
    #         if p <= seg_horiz: return (w - r - p, h)
    #         p -= seg_horiz
    #         if p <= arc_len:
    #             angle = math.pi/2 + (p / arc_len) * (math.pi/2)
    #             return (r + r * math.cos(angle), h - r + r * math.sin(angle))
    #         p -= arc_len
    #         if p <= seg_vert: return (0, h - r - p)
    #         p -= seg_vert
    #         if p <= arc_len:
    #             angle = math.pi + (p / arc_len) * (math.pi/2)
    #             return (r + r * math.cos(angle), r + r * math.sin(angle))
    #         return (r, 0)
    #     perimeter = 2 * (aw - 2 * ar) + 2 * (ah - 2 * ar) + 2 * math.pi * ar
    #     dash_len = 20 * aa_scale * scale
    #     gap_len = 14 * aa_scale * scale
    #     dash_total = dash_len + gap_len
    #     num_dashes = max(1, int(perimeter / dash_total))
    #     actual_dash_total = perimeter / num_dashes
    #     ratio = actual_dash_total / dash_total
    #     actual_dash = dash_len * ratio
    #     samples = int(perimeter)
    #     border_color = '#f97316'
    #     outline_w = max(2, int(3.0 * scale))
    #     draw_width = outline_w * aa_scale
    #     last_pt = None
    #     for i in range(samples + 1):
    #         dist = (i / samples) * perimeter
    #         pt = get_rrect_point(dist, aw, ah, ar)
    #         if (dist % actual_dash_total) <= actual_dash:
    #             if last_pt:
    #                 aa_draw.line([last_pt, pt], fill=border_color, width=draw_width)
    #             last_pt = pt
    #         else:
    #             last_pt = None
    #     overlay_img = aa_img.resize((overlay_w, overlay_h), Image.Resampling.LANCZOS)
    #     overlay_draw = ImageDraw.Draw(overlay_img)
    #     qr_x, qr_y = int(15 * scale), int(15 * scale)
    #     overlay_img.paste(qr_img, (qr_x, qr_y))
    #     text_x = qr_x + qr_size + int(22 * scale)
    #     text_y = qr_y + int(4 * scale)
    #     overlay_draw.text((text_x, text_y), ":) โปรเจคการกุศลช่วยเหลือฟรี", fill='#059669', font=font)
    #     overlay_draw.text((text_x, text_y + int(36 * scale)), "สแกน QR code !!", fill='#0f172a', font=font)
    #     overlay_draw.text((text_x, text_y + int(64 * scale)), "ดาวน์โหลดภาพเต็มชัดแจ๋ว-ไฟล์ไม่แตก!", fill='#0f172a', font=font)
    #     dash_length = max(1, int(6 * scale))
    #     dash_gap = max(1, int(4 * scale))
    #     line_y = text_y + int(92 * scale)
    #     line_start_x = text_x
    #     line_end_x = overlay_w - int(20 * scale)
    #     for cx in range(line_start_x, line_end_x, dash_length + dash_gap):
    #         end_x = min(cx + dash_length, line_end_x)
    #         overlay_draw.line([(cx, line_y), (end_x, line_y)], fill='#f97316', width=max(1, int(1.5 * scale)))
    #     overlay_draw.text((text_x, text_y + int(106 * scale)), "> อยากจ้างตัดต่อส่วนตัว 60฿ | ทักแชทมาได้เลย", fill='#64748b', font=small_font)
    #     pos_x = margin
    #     pos_y = final_h - overlay_h - margin
    #     rgba_final = final_img.convert('RGBA')
    #     rgba_final.paste(shadow_img, (pos_x - shadow_pad, pos_y - shadow_pad + int(4 * scale)), shadow_img)
    #     rgba_final.paste(overlay_img, (pos_x, pos_y), overlay_img)
    #     final_export = rgba_final.convert('RGB')
    # else:
    # === โหมดไม่อัพโหลด: ลบลายน้ำ + กรอบเขียว + แบนเนอร์หัวภาพ ===
    print("[Donate] → bypass mode: ลบลายน้ำ + กรอบเขียว + แบนเนอร์หัว (ไม่ upload / ไม่ QR)")
    base_img = original_img.copy().convert('RGB')
    fw, fh = base_img.size

    # --- Scale factor ตามความกว้างภาพ ---
    scale = max(0.8, min(fw / 400.0, 3.0))

    # --- โหลด Font ---
    font_large = None
    font_small = None
    font_bold = None
    font_paths = [
        "C:/Windows/Fonts/tahoma.ttf",
        "C:/Windows/Fonts/Tahoma.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/Segoeui.ttf",
    ]
    font_bold_paths = [
        "C:/Windows/Fonts/tahomabd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/Arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
    ]
    sz_large = int(20 * scale)
    sz_small = int(13 * scale)
    sz_bold = int(22 * scale)

    for fp in font_bold_paths:
        if os.path.exists(fp):
            try:
                font_bold = ImageFont.truetype(fp, sz_bold)
                break
            except Exception:
                pass
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font_large = ImageFont.truetype(fp, sz_large)
                font_small = ImageFont.truetype(fp, sz_small)
                break
            except Exception:
                pass
    if not font_bold:
        font_bold = font_large or ImageFont.load_default()
    if not font_large:
        font_large = ImageFont.load_default()
    if not font_small:
        font_small = ImageFont.load_default()

    # --- คำนวณความสูงแบนเนอร์ ---
    pad_v = int(10 * scale)
    pad_h = int(14 * scale)
    line_gap = int(5 * scale)

    dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    txt1 = 'อยากจะแก้ไขบ้าง'
    txt2 = 'เพียง 60 ฿'
    txt3 = '/ ทำแกมให้หมด ช่วย ๆ กัน / inbox มาแน่ท่าน. /'
    h1 = dummy.textbbox((0, 0), txt1, font=font_bold)[3]
    h3 = dummy.textbbox((0, 0), txt3, font=font_small)[3]
    banner_h = pad_v + h1 + line_gap + h3 + pad_v + int(4 * scale)  # +4 เผื่อเส้นประ

    # --- สร้าง banner RGBA (รองรับ alpha สำหรับ gradient) ---
    banner = Image.new('RGBA', (fw, banner_h), (0, 0, 0, 0))

    # Gradient ฟ้าสด → น้ำเงินเข้ม (ซ้าย→ขวา) แบบของเดิม
    bd = ImageDraw.Draw(banner)
    for x in range(fw):
        t = x / max(fw - 1, 1)
        r = int(0 * (1 - t) + 0 * t)
        g = int(162 * (1 - t) + 98 * t)
        b = int(255 * (1 - t) + 230 * t)
        bd.line([(x, 0), (x, banner_h - 1)], fill=(r, g, b, 255))

    # --- วาดข้อความ row 1: 💞 อยากจะแก้ไขบ้าง  เพียง 60 ฿ ---
    y1 = pad_v
    x_text = pad_h

    # วาดหัวใจ (วงกลมสีชมพู-แดง แทน emoji ที่ font ไม่รองรับ)
    heart_r = int(10 * scale)
    heart_cx = x_text + heart_r
    heart_cy = y1 + h1 // 2
    bd.ellipse([heart_cx - heart_r, heart_cy - heart_r,
                heart_cx + heart_r, heart_cy + heart_r], fill=(255, 80, 120, 255))
    bd.ellipse([heart_cx - heart_r + int(2*scale), heart_cy - heart_r + int(2*scale),
                heart_cx + heart_r - int(2*scale), heart_cy + heart_r - int(2*scale)],
               fill=(255, 130, 160, 255))
    x_text = heart_cx + heart_r + int(6 * scale)

    # เงาข้อความ row 1 (ออฟเซ็ต 1px)
    bd.text((x_text + 1, y1 + 1), txt1, fill=(0, 0, 80, 180), font=font_bold)
    bd.text((x_text, y1), txt1, fill=(255, 255, 255, 255), font=font_bold)

    # "เพียง 60 ฿" สีเหลืองสด ต่อท้าย
    w1 = dummy.textbbox((0, 0), txt1, font=font_bold)[2]
    x_price = x_text + w1 + int(8 * scale)

    # กล่องพื้นหลังสีเหลืองใส
    price_bbox = dummy.textbbox((0, 0), txt2, font=font_large)
    pw, ph = price_bbox[2], price_bbox[3]
    px1 = x_price - int(4 * scale)
    py1 = y1 + (h1 - ph) // 2 - int(1 * scale)
    px2 = x_price + pw + int(4 * scale)
    py2 = y1 + (h1 + ph) // 2 + int(2 * scale)
    bd.rounded_rectangle([px1, py1, px2, py2], radius=int(4 * scale), fill=(255, 220, 0, 220))
    bd.text((x_price + 1, py1 + 1), txt2, fill=(0, 0, 0, 120), font=font_large)
    bd.text((x_price, py1), txt2, fill=(20, 20, 20, 255), font=font_large)

    # --- วาดข้อความ row 2 ---
    y2 = y1 + h1 + line_gap
    bd.text((pad_h + 1, y2 + 1), txt3, fill=(0, 0, 80, 150), font=font_small)
    bd.text((pad_h, y2), txt3, fill=(220, 240, 255, 255), font=font_small)

    # --- ไอคอนกรรไกร ✂ มุมขวาล่างของ banner ---
    scissor_r = int(9 * scale)
    sx = fw - scissor_r - int(8 * scale)
    sy = banner_h - scissor_r - int(6 * scale)
    # วงกลมสีแดงเป็น background
    bd.ellipse([sx - scissor_r, sy - scissor_r, sx + scissor_r, sy + scissor_r],
               fill=(220, 30, 30, 230))
    # วาด X ขาว (แทน ✂)
    cr = int(5 * scale)
    bd.line([sx - cr, sy - cr, sx + cr, sy + cr], fill=(255, 255, 255, 255), width=max(2, int(2 * scale)))
    bd.line([sx + cr, sy - cr, sx - cr, sy + cr], fill=(255, 255, 255, 255), width=max(2, int(2 * scale)))

    # --- เส้นประสีเหลืองด้านล่าง banner ---
    dash_y = banner_h - int(3 * scale)
    dash_len = int(14 * scale)
    gap_len = int(7 * scale)
    x_pos = 0
    while x_pos < fw:
        end_x = min(x_pos + dash_len, fw)
        bd.line([(x_pos, dash_y), (end_x, dash_y)],
                fill=(255, 220, 0, 255), width=max(2, int(2 * scale)))
        x_pos += dash_len + gap_len

    # --- รวม banner (RGBA) + ภาพหลัก ---
    banner_rgb = banner.convert('RGB')
    combined = Image.new('RGB', (fw, banner_h + fh), (0, 0, 0))
    combined.paste(banner_rgb, (0, 0))
    combined.paste(base_img, (0, banner_h))
    final_export = combined

    # วาดกรอบสี Lime เขียวสด หนา 4px ล้อมรอบทั้งหมด (สวยกว่า)
    border_draw = ImageDraw.Draw(final_export)
    fw, fh = final_export.size
    border_color = "#00FF00"  # Lime สดใส
    for i in range(4):
        border_draw.rectangle([i, i, fw - 1 - i, fh - 1 - i], outline=border_color, width=1)
    
    # --- Export เซฟลงเป้าหมายโดยตรง (เขียนทับไฟล์เดิม ห้ามลบ) ---
    try:
        # ใช้วิธีเขียนทับโดยไม่ลบไฟล์เดิม (เพื่อไม่ให้ไอคอนหาย)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            final_export.save(temp_file.name, format='PNG')
            temp_path = temp_file.name
        
        # อ่านข้อมูลจากไฟล์ชั่วคราว
        with open(temp_path, 'rb') as temp_f:
            data = temp_f.read()
        
        # เขียนทับไฟล์เป้าหมาย (ไม่ลบก่อน)
        with open(target, 'wb') as target_f:
            target_f.write(data)
        
        # ลบไฟล์ชั่วคราว
        os.unlink(temp_path)
        
        print(f"[Done] Overwritten: {target}")
        
    except Exception as e:
        print(f"Error overwriting file: {e}")
        # fallback ไปวิธีเดิม
        final_export.save(target, format='PNG')
    
    copy_image_to_clipboard(target)
    
    # --- ถ้าเป็น --donate-no-paste → bot.js จะจัดการ upload เองผ่าน setInputFiles, ไม่ต้อง auto_paste ---
    if '--donate-no-paste' not in sys.argv:
        time.sleep(2.0)
        auto_paste()

if __name__ == "__main__":
    mode_flag = sys.argv[1] if len(sys.argv) > 1 else ""
    target_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if mode_flag == "--clean":
        process_clean_only(target_path)
    elif mode_flag in ["--donate", "--donate-no-paste"]:
        process_donate(target_path)
    else:
        process_donate()
