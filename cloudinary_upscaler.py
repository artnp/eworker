import os
import time
import hashlib
import json
import requests
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "cloudinary_accounts.json")
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")

# Cloudinary Accounts Pool
DEFAULT_ACCOUNTS = [
    {"cloud_name": "dbfh7dtne", "api_key": "314374931381631", "api_secret": "lOAhvI52wumhjCLmdreW5WdXgSU", "active": True},
    {"cloud_name": "m9yyilb6", "api_key": "949466962937462", "api_secret": "xJOQVc9T2oXQ2kWOd96q4YlDxtQ", "active": True},
    {"cloud_name": "fenpyqu3", "api_key": "334345428177449", "api_secret": "yO4wg5MPltuQMHgiqIyzAHD-L9E", "active": True},
    {"cloud_name": "qtwdpw8x", "api_key": "182649854232788", "api_secret": "Vg2LCCHJ-4DUivlhNVh_50tyAVU", "active": True},
    {"cloud_name": "tocchodh", "api_key": "732576314649364", "api_secret": "z-NNa8o9cZxRL97djoRRpJSf8tI", "active": True},
    {"cloud_name": "y5bb3tak", "api_key": "915546952421175", "api_secret": "1z57lAUiKLoegQFrmbol8-XyLcU", "active": True},
    {"cloud_name": "dpbt2gb1h", "api_key": "331776356594442", "api_secret": "4sQ4tZb5mAU2OARoI9OFivbajtQ", "active": False}
]

def load_accounts():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_ACCOUNTS

def save_accounts(accounts):
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[Cloudinary] Error saving accounts: {e}")

_progress_state = {
    "status": "idle",
    "percent": 0,
    "step_num": 0,
    "step_total": 3,
    "step_title": "พร้อมใช้งาน",
    "detail": ""
}

_quota_cache = {
    "timestamp": 0,
    "data": None
}

def get_upscale_progress():
    return _progress_state

def get_accounts_quota(force_refresh=False):
    global _quota_cache
    now = time.time()
    # Cache for 45 seconds to keep dashboard ultra fast
    if not force_refresh and _quota_cache["data"] and (now - _quota_cache["timestamp"] < 45):
        return _quota_cache["data"]

    accounts = load_accounts()
    account_stats = []
    current_acc_info = None

    for idx, acc in enumerate(accounts):
        cloud_name = acc.get("cloud_name", "").strip()
        api_key = acc.get("api_key", "").strip()
        api_secret = acc.get("api_secret", "").strip()

        info = {
            "index": idx + 1,
            "total": len(accounts),
            "cloud_name": cloud_name,
            "used_credits": 0.0,
            "limit_credits": 25.0,
            "remaining_percent": 100.0,
            "used_transformations": 0,
            "active": acc.get("active", True),
            "status": "ready"
        }

        if cloud_name and api_key and api_secret:
            try:
                url = f"https://api.cloudinary.com/v1_1/{cloud_name}/usage"
                resp = requests.get(url, auth=(api_key, api_secret), timeout=4)
                if resp.status_code == 200:
                    j = resp.json()
                    credits = j.get('credits', {})
                    transformations = j.get('transformations', {})
                    usage = float(credits.get('usage', 0.0))
                    limit = float(credits.get('limit', 25.0))
                    used_pct = float(credits.get('used_percent', 0.0))
                    rem_pct = max(0.0, round(100.0 - used_pct, 1))

                    info["used_credits"] = round(usage, 2)
                    info["limit_credits"] = round(limit, 1)
                    info["remaining_percent"] = rem_pct
                    info["used_transformations"] = int(transformations.get('usage', 0))
                    info["status"] = "exhausted" if rem_pct <= 1.0 else "ready"
                elif resp.status_code == 403:
                    info["status"] = "forbidden"
                    info["error"] = "Access key permission issue"
                else:
                    info["status"] = "error"
            except Exception as e:
                info["status"] = "unreachable"
                info["error"] = str(e)

        account_stats.append(info)
        if not current_acc_info and info["status"] == "ready":
            current_acc_info = info

    if not current_acc_info and account_stats:
        current_acc_info = account_stats[0]

    result = {
        "current_account": current_acc_info,
        "accounts": account_stats
    }
    _quota_cache = {
        "timestamp": now,
        "data": result
    }
    return result

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

def generate_signature(params_dict, api_secret):
    sorted_keys = sorted(params_dict.keys())
    to_sign = "&".join([f"{k}={params_dict[k]}" for k in sorted_keys])
    to_sign += api_secret
    return hashlib.sha1(to_sign.encode('utf-8')).hexdigest()

def upscale_with_account(account, image_path, scale=2, mode="upscale_enhancer", options=None):
    if options is None:
        options = {}
    cloud_name = account.get("cloud_name", "").strip()
    api_key = account.get("api_key", "").strip()
    api_secret = account.get("api_secret", "").strip()

    if not cloud_name or not api_key or not api_secret:
        raise ValueError("Missing credentials for account")

    upload_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"
    timestamp = str(int(time.time()))
    
    params = {"timestamp": timestamp}
    signature = generate_signature(params, api_secret)

    with open(image_path, 'rb') as img_file:
        files = {'file': img_file}
        data = {
            'api_key': api_key,
            'timestamp': timestamp,
            'signature': signature
        }
        
        response = requests.post(upload_url, files=files, data=data, timeout=40)
        
    if response.status_code == 200:
        res_json = response.json()
        public_id = res_json.get("public_id")
        version = res_json.get("version")
        format_ext = res_json.get("format", "png")
        
        if mode == "enhancer":
            # Pure AI Generative Restore (Enhancer deblur & clarity, preserving dimensions)
            transformed_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/c_limit,w_2500,h_2500/e_gen_restore/v{version}/{public_id}.{format_ext}"
        elif mode == "extender":
            # Cloudinary AI Image Extender (Generative Fill Outpainting)
            aspect_ratio = options.get("aspect_ratio")
            direction = options.get("direction")
            prompt = options.get("prompt", "").strip()
            prompt_part = f":prompt_{requests.utils.quote(prompt)}" if prompt else ""

            if aspect_ratio:
                ext_part = f"b_gen_fill{prompt_part},c_pad,ar_{aspect_ratio}"
            elif direction == "top":
                ext_part = f"b_gen_fill{prompt_part},c_pad,h_1.3,g_south"
            elif direction == "bottom":
                ext_part = f"b_gen_fill{prompt_part},c_pad,h_1.3,g_north"
            elif direction == "sides":
                ext_part = f"b_gen_fill{prompt_part},c_pad,w_1.3"
            else:
                pct = float(options.get("pad_percent", 20))
                factor = round(1.0 + (pct / 100.0), 2)
                ext_part = f"b_gen_fill{prompt_part},c_pad,w_{factor},h_{factor}"

            transformed_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/c_limit,w_2000,h_2000/{ext_part}/v{version}/{public_id}.png"
        elif mode == "remove_bg":
            # Cloudinary Remove White Background / Transparent Background
            method = options.get("method", "ai")
            if method == "white":
                # Remove white background specifically
                bg_part = "e_make_transparent:20"
            else:
                # AI Smart Background Removal (foreground isolation)
                bg_part = "e_background_removal"
            transformed_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/c_limit,w_2500,h_2500/{bg_part}/v{version}/{public_id}.png"
        elif mode in ("remove_watermark", "remove_wm"):
            # Cloudinary Generative Remove (AI Inpainting Watermark / Text removal)
            region = options.get("region")
            prompt = options.get("prompt", "watermark").strip()
            if region:
                rm_part = f"e_gen_remove:region_({region})"
            else:
                prompt_q = requests.utils.quote(prompt)
                rm_part = f"e_gen_remove:prompt_{prompt_q}"
            transformed_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/c_limit,w_2500,h_2500/{rm_part}/v{version}/{public_id}.png"
        else:
            # AI Upscale + Generative Restore (Super-Resolution upscale + deblur clarity restore)
            # Cloudinary e_upscale requires input image <= 4.2 megapixels.
            # Using c_limit,w_2000,h_2000 prevents HTTP 400 "Image is too large for e_upscale"
            # while leaving smaller images (e.g. 720x960) unscaled before super-resolution.
            transformed_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/c_limit,w_2000,h_2000/e_gen_restore/e_upscale/v{version}/{public_id}.{format_ext}"
        return transformed_url
    else:
        error_msg = response.text
        try:
            err_json = response.json()
            error_msg = err_json.get("error", {}).get("message", error_msg)
        except Exception:
            pass
        raise RuntimeError(f"Cloudinary error ({response.status_code}): {error_msg}")

def upscale_image(image_path=None, scale=2, model_name="cloudinary_upscale_enhancer", mode=None, options=None):
    """
    ทำ AI Enhancer / Upscale / Image Extender / Remove Background ผ่าน Cloudinary Multi-Account Rotation
    เขียนทับลงที่ Desktop/complete.png โดยตรง (ไม่ตัดส่วนขาวใดๆ)
    และสร้างลายน้ำ Desktop/example.png ใหม่
    - mode="extender": ขยายตำแหน่งภาพ / ขยายขอบภาพด้วย AI Generative Fill
    - mode="remove_bg": ลบฉากหลัง / ลบฉากหลังสีขาวให้เป็นภาพโปร่งใส PNG
    - mode="upscale_enhancer": ขยายภาพ x2 + ปรับความชัดสมจริง
    - mode="enhancer": ปรับความชัดสมจริง (ขนาดเดิม)
    """
    if options is None:
        options = {}

    if not image_path:
        image_path = os.path.join(DESKTOP_PATH, "complete.png")

    fname_lower = os.path.basename(image_path).lower()
    if "complete_bot" in fname_lower or "bot" in fname_lower:
        print(f"[Cloudinary] 🚫 Blocked: {image_path} is complete_bot.png.")
        _set_progress("error", 0, 1, "🚫 ไม่อนุญาตให้ประมวลผลไฟล์ complete_bot.png", "Facebook_Bot ไม่ใช้ระบบนี้")
        return {
            "success": False,
            "error": "Forbidden: complete_bot.png is reserved for Facebook_Bot.",
            "path": image_path
        }

    if not os.path.exists(image_path):
        _set_progress("error", 0, 1, "❌ ไม่พบไฟล์เป้าหมาย", str(image_path))
        raise FileNotFoundError(f"ไม่พบไฟล์: {image_path}")

    # Determine execution mode
    effective_mode = mode or ("enhancer" if model_name == "cloudinary_enhancer" else ("extender" if model_name in ("cloudinary_extender", "extender") else ("remove_bg" if model_name in ("cloudinary_remove_bg", "remove_bg") else ("remove_watermark" if model_name in ("cloudinary_remove_watermark", "remove_watermark", "remove_wm") else "upscale_enhancer"))))
    is_upscale_enhancer = (effective_mode == "upscale_enhancer")
    is_extender = (effective_mode == "extender")
    is_remove_bg = (effective_mode == "remove_bg")
    is_remove_wm = (effective_mode == "remove_watermark")

    if is_extender:
        mode_title = "AI Image Extender (เพิ่มตำแหน่งภาพ)"
    elif is_remove_bg:
        mode_title = "AI Remove Background (ลบฉากหลัง)"
    elif is_remove_wm:
        mode_title = "AI Remove Watermark (ลบลายน้ำ)"
    elif is_upscale_enhancer:
        mode_title = "AI Upscale + Enhancer"
    else:
        mode_title = "AI Enhancer"

    accounts = load_accounts()
    total_acc = len(accounts)
    
    _set_progress("running", 15, 1, f"ขั้นตอนที่ 1/3: กำลังเชื่อมต่อ Cloudinary AI Cloud...", f"เตรียมส่งภาพขึ้นคลาวด์สำหรับ {mode_title}...")

    upscaled_image_bytes = None
    success_account_idx = -1
    last_error_msg = ""

    for idx, acc in enumerate(accounts):
        cloud_name = acc.get('cloud_name', '').strip()
        api_key_short = acc.get('api_key', '')[:6] + '...'
        
        if not cloud_name or not acc.get('active', True):
            continue

        try:
            print(f"[Cloudinary] Trying Account {idx+1}/{total_acc} (Cloud: {cloud_name}, Key: {api_key_short}, Mode: {effective_mode})...")
            if is_extender:
                step2_detail = "กำลังขยายขอบภาพและสร้างเนื้อหาภาพใหม่ด้วย Generative Fill..."
            elif is_remove_bg:
                step2_detail = "กำลังตัดแยกวัตถุและลบฉากหลังให้เป็นพื้นโปร่งใส..."
            elif is_remove_wm:
                step2_detail = "กำลังตรวจจับและลบลายน้ำด้วย AI Generative Inpainting..."
            elif is_upscale_enhancer:
                step2_detail = "ขยายภาพความละเอียดสูง x2 พร้อมกู้คืนรายละเอียดและลดความเบลอ..."
            else:
                step2_detail = "กู้คืนรายละเอียดและเพิ่มความคมชัดสมจริง..."

            _set_progress(
                "running",
                int(20 + (idx / total_acc) * 35),
                2,
                f"ขั้นตอนที่ 2/3: กำลังประมวลผล {mode_title} บนคลาวด์ (บัญชี {idx+1}/{total_acc})...",
                step2_detail
            )
            
            result_url = upscale_with_account(acc, image_path, scale=scale, mode=effective_mode, options=options)
            print(f"[Cloudinary] ✅ Transformed URL generated via Account {idx+1}: {result_url}")
            
            _set_progress("running", 75, 2, f"ขั้นตอนที่ 2/3: กำลังประมวลผลและดาวน์โหลดภาพ ({idx+1}/{total_acc})...", "สตรีมภาพผลลัพธ์จากคลาวด์...")
            
            # Retry loop for AI CDN generation (handles 420/423 processing responses)
            max_retries = 25
            for attempt in range(max_retries):
                try:
                    dl_resp = requests.get(result_url, timeout=50)
                    if dl_resp.status_code == 200 and len(dl_resp.content) > 500:
                        upscaled_image_bytes = dl_resp.content
                        success_account_idx = idx
                        break
                    elif dl_resp.status_code in (420, 423, 202):
                        print(f"[Cloudinary] Waiting for AI generation (attempt {attempt+1}/{max_retries}, status {dl_resp.status_code})...")
                        time.sleep(2)
                    elif dl_resp.status_code == 400:
                        cld_err = dl_resp.headers.get("x-cld-error", dl_resp.text[:200])
                        print(f"[Cloudinary] Client error 400 ({cld_err}) on account {idx+1}")
                        raise RuntimeError(f"Cloudinary 400: {cld_err}")
                    else:
                        cld_err = dl_resp.headers.get("x-cld-error", "")
                        print(f"[Cloudinary] Download attempt {attempt+1} got status {dl_resp.status_code} {cld_err}")
                        time.sleep(1.5)
                except requests.RequestException as de:
                    print(f"[Cloudinary] Download attempt {attempt+1} exception: {de}")
                    time.sleep(1.5)

            if upscaled_image_bytes:
                break
            else:
                raise RuntimeError(f"Download failed after retries for {result_url}")
        except Exception as e:
            print(f"[Cloudinary] ⚠️ Account {idx+1} ({cloud_name}) error: {e}")
            last_error_msg = str(e)
            acc["last_error"] = str(e)
            continue

    # Fallback to AI Enhancer if Upscale + Enhancer failed on all accounts
    if not upscaled_image_bytes and is_upscale_enhancer:
        print("[Cloudinary] ⚠️ Upscale failed across accounts. Attempting fallback to AI Enhancer...")
        _set_progress("running", 60, 2, "กำลังกู้คืนรายละเอียดด้วย AI Enhancer...", "เปลี่ยนเป็นระบบ Enhancer อัตโนมัติ...")
        for idx, acc in enumerate(accounts):
            cloud_name = acc.get('cloud_name', '').strip()
            if not cloud_name or not acc.get('active', True):
                continue
            try:
                enh_url = upscale_with_account(acc, image_path, scale=1, mode="enhancer")
                for attempt in range(15):
                    dl_resp = requests.get(enh_url, timeout=40)
                    if dl_resp.status_code == 200 and len(dl_resp.content) > 500:
                        upscaled_image_bytes = dl_resp.content
                        success_account_idx = idx
                        effective_mode = "enhancer"
                        break
                    time.sleep(1.5)
                if upscaled_image_bytes:
                    break
            except Exception as fe:
                print(f"[Cloudinary] Enhancer fallback error on account {idx+1}: {fe}")
                continue

    if not upscaled_image_bytes:
        _set_progress("error", 0, 2, f"❌ ทุกบัญชีติดขัด: {last_error_msg}", "กรุณาตรวจเช็ค Cloudinary Dashboard")
        raise RuntimeError(f"ทุกบัญชี Cloudinary หมดโควต้าหรือติดขัด: {last_error_msg}")

    # 💾 บันทึกทับ Desktop/complete.png โดยตรงเสมอ (ไม่สั่งลบไฟล์)
    desktop_complete = os.path.join(DESKTOP_PATH, "complete.png")
    try:
        from auto_donate_watcher import backup_desktop_files
        if backup_desktop_files:
            backup_desktop_files(incoming_data=upscaled_image_bytes)
    except Exception:
        pass
    with open(desktop_complete, 'wb') as f:
        f.write(upscaled_image_bytes)
    print(f"[Cloudinary] ✅ Overwritten Desktop complete.png: {desktop_complete}")

    # สร้างลายน้ำทับ example.png บน Desktop
    example_path = os.path.join(DESKTOP_PATH, "example.png")
    try:
        from watermark_engine import create_anti_ai_watermark
        import io
        raw_img = Image.open(io.BytesIO(upscaled_image_bytes))
        example_img = create_anti_ai_watermark(raw_img)
        example_img.save(example_path, format="PNG")
        print(f"[Cloudinary] ✅ Overwritten watermarked preview: {example_path}")
    except Exception as e:
        print(f"[Cloudinary] Watermark generation warning: {e}")

    _set_progress(
        "completed",
        100,
        3,
        f"✨ เสร็จสิ้น! {mode_title} สำเร็จ (บัญชี {success_account_idx+1}/{total_acc}) 100%",
        "บันทึกทับ Desktop/complete.png และ example.png เรียบร้อย"
    )

    save_accounts(accounts)

    return {
        "success": True,
        "path": image_path,
        "example_path": example_path,
        "mode": effective_mode,
        "provider": f"Cloudinary ({accounts[success_account_idx].get('cloud_name')})",
        "account_index": success_account_idx + 1,
        "total_accounts": total_acc
    }
