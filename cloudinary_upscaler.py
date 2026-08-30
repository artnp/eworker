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
    {"cloud_name": "dpbt2gb1h", "api_key": "331776356594442", "api_secret": "4sQ4tZb5mAU2OARoI9OFivbajtQ", "active": True}
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

def upscale_with_account(account, image_path, scale=2):
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
        
        # Pure AI Generative Restore (Enhancer) without extra scaling to save quota & bandwidth
        transformed_url = f"https://res.cloudinary.com/{cloud_name}/image/upload/e_gen_restore/v{version}/{public_id}.{format_ext}"
        return transformed_url
    else:
        error_msg = response.text
        try:
            err_json = response.json()
            error_msg = err_json.get("error", {}).get("message", error_msg)
        except Exception:
            pass
        raise RuntimeError(f"Cloudinary error ({response.status_code}): {error_msg}")

def upscale_image(image_path=None, scale=2, model_name="cloudinary_enhancer"):
    """
    ทำ AI Enhancer & Upscale ภาพผ่าน Cloudinary Multi-Account Rotation
    เขียนทับลงที่ image_path (complete.png) โดยตรง (ไม่ลบไฟล์)
    และสร้างลายน้ำ example.png ใหม่
    """
    if not image_path:
        image_path = os.path.join(DESKTOP_PATH, "complete.png")

    fname_lower = os.path.basename(image_path).lower()
    if "complete_bot" in fname_lower or "bot" in fname_lower:
        print(f"[Cloudinary] 🚫 Blocked: {image_path} is complete_bot.png.")
        _set_progress("error", 0, 1, "🚫 ไม่อนุญาตให้ Upscale ไฟล์ complete_bot.png", "Facebook_Bot ไม่ใช้ระบบนี้")
        return {
            "success": False,
            "error": "Forbidden: complete_bot.png is reserved for Facebook_Bot.",
            "path": image_path
        }

    if not os.path.exists(image_path):
        _set_progress("error", 0, 1, "❌ ไม่พบไฟล์เป้าหมาย", str(image_path))
        raise FileNotFoundError(f"ไม่พบไฟล์: {image_path}")

    accounts = load_accounts()
    total_acc = len(accounts)
    
    _set_progress("running", 15, 1, "ขั้นตอนที่ 1/3: กำลังเชื่อมต่อ Cloudinary AI Cloud...", "เตรียมส่งภาพขึ้นคลาวด์...")

    upscaled_image_bytes = None
    success_account_idx = -1
    last_error_msg = ""

    for idx, acc in enumerate(accounts):
        cloud_name = acc.get('cloud_name', '').strip()
        api_key_short = acc.get('api_key', '')[:6] + '...'
        
        if not cloud_name:
            continue

        try:
            print(f"[Cloudinary] Trying Account {idx+1}/{total_acc} (Cloud: {cloud_name}, Key: {api_key_short})...")
            _set_progress(
                "running",
                int(20 + (idx / total_acc) * 35),
                2,
                f"ขั้นตอนที่ 2/3: กำลังประมวลผล AI Enhancer บนคลาวด์ (บัญชี {idx+1}/{total_acc})...",
                f"กู้คืนรายละเอียดและเพิ่มความคมชัดสมจริง..."
            )
            
            result_url = upscale_with_account(acc, image_path, scale=scale)
            print(f"[Cloudinary] ✅ Transformed URL generated via Account {idx+1}: {result_url}")
            
            _set_progress("running", 75, 2, f"ขั้นตอนที่ 2/3: กำลังประมวลผลและดาวน์โหลดภาพคมชัดระดับสูง ({idx+1}/{total_acc})...", "สตรีมภาพผลลัพธ์...")
            
            dl_resp = requests.get(result_url, timeout=60)
            if dl_resp.status_code == 200 and len(dl_resp.content) > 1000:
                upscaled_image_bytes = dl_resp.content
                success_account_idx = idx
                break
            else:
                raise RuntimeError(f"Download failed with status {dl_resp.status_code}")
        except Exception as e:
            print(f"[Cloudinary] ⚠️ Account {idx+1} ({cloud_name}) error: {e}")
            last_error_msg = str(e)
            acc["last_error"] = str(e)
            continue

    if not upscaled_image_bytes:
        _set_progress("error", 0, 2, f"❌ ทุกบัญชีติดขัด: {last_error_msg}", "กรุณาตรวจเช็ค Cloudinary Dashboard")
        raise RuntimeError(f"ทุกบัญชี Cloudinary หมดโควต้าหรือติดขัด: {last_error_msg}")

    # 💾 บันทึกทับ Desktop/complete.png โดยตรงเสมอ (ไม่สั่งลบไฟล์)
    desktop_complete = os.path.join(DESKTOP_PATH, "complete.png")
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
        f"✨ เสร็จสิ้น! AI Enhancer & Restore สำเร็จ (บัญชี {success_account_idx+1}/{total_acc}) 100%",
        "บันทึกทับ Desktop/complete.png และ example.png เรียบร้อย"
    )

    save_accounts(accounts)

    return {
        "success": True,
        "path": image_path,
        "example_path": example_path,
        "provider": f"Cloudinary ({accounts[success_account_idx].get('cloud_name')})",
        "account_index": success_account_idx + 1,
        "total_accounts": total_acc
    }
