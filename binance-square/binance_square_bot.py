import os
import sys
import re
import time
import json
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error

def get_subprocess_kwargs():
    kwargs = {}
    if sys.platform == 'win32':
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = si
        kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
    return kwargs

BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"
BASE_URL_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi"
POLL_INTERVAL_SEC = 2
MAX_POLL_RETRIES = 25
MIN_CLIP_DURATION_SEC = 15   # ความยาวคลิป Binance Square ขั้นต่ำต้องไม่น้อยกว่า 15 วินาที
MAX_CLIP_DURATION_SEC = 300  # จำกัดความยาวคลิป Binance Square สูงสุดไม่เกิน 5 นาที (300 วินาที)

# รายชื่อเหรียญคริปโตยอดนิยมบน Binance
CRYPTO_COINS = [
    'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'DOGE', 'ADA', 'AVAX', 'DOT', 'LINK',
    'SHIB', 'SUI', 'PEPE', 'NEAR', 'LTC', 'BCH', 'UNI', 'APT', 'XLM', 'ATOM',
    'FIL', 'ARB', 'OP', 'TIA', 'RENDER', 'INJ', 'FTM', 'MATIC', 'POL', 'FET',
    'ICP', 'STX', 'KAS', 'AAVE', 'WIF', 'BONK', 'FLOKI', 'TON', 'TRX', 'ALGO',
    'VET', 'HBAR', 'EOS', 'CRV', 'MKR', 'DYDX', 'LDO', 'GALA', 'SAND', 'MANA',
    'AXS', 'RUNE', 'THETA', 'EGLD', 'FTT', 'BLUR', 'SEI', 'JUP', 'STRK', 'WLD',
    'PENDLE', 'ONDO', 'PYTH', 'BEAM', 'GMX', 'FLOW', 'CHZ', 'APE', 'NEO', 'IOTA',
    'KAVA', 'QNT', 'SNX', 'MINA', 'ROSE', 'CFX', 'ZEC', 'DASH', 'XMR', 'CAKE',
    'BAKE', 'TWT', '1INCH', 'LUNC', 'LUNA', 'USTC', 'BOME', 'MEME', 'ORDI', 'SATS',
    'RATS', 'JASMY', 'MEW', 'DOGS', 'CATI', 'HMSTR', 'NEIRO', 'TAO', 'ENA', 'ETHFI',
    'REZ', 'BB', 'IO', 'ZK', 'LISTA', 'BANANA', 'RDNT', 'VOXEL', 'DAR', 'ALICE',
    'TLM', 'SLP', 'ENJ', 'HIGH', 'ILV', 'MAGIC', 'PIXEL', 'PORTAL', 'MAVIA', 'SUPER',
    'YGG', 'AEVO', 'DYM', 'ALT', 'MANTA', 'XAI', 'NFP', 'ACE', 'JTO', 'VANRY',
    'VIC', 'BEAMX', 'NTRN', 'CYBER', 'ARKM', 'ARKHAM', 'KSM', 'WAVES', 'ZIL', 'BAT',
    'COMP', 'YFI', 'SUSHI', 'BAL', 'GRT', '1000SATS', 'BTT', 'CHR', 'CKB', 'C98',
    'DGB', 'DENT', 'DUSK', 'GTC', 'HARD', 'HIVE', 'ICX', 'IOST', 'IOTX', 'JST',
    'KDA', 'KNC', 'LRC', 'LSK', 'MDX', 'NKN', 'OCEAN', 'OMG', 'ONT', 'PUNDIX',
    'QTUM', 'REEF', 'RVN', 'SC', 'SCRT', 'SKL', 'SXP', 'TFUEL', 'VTHO', 'WAXP',
    'WRX', 'XEC', 'XEM', 'XVG', 'ZRX', 'USDT', 'USDC', 'FDUSD', 'TUSD', 'BUSD', 'DAI',
    'BLUM', 'MAJOR', 'MOODENG', 'GOAT', 'PNUT', 'DRIFT', 'COW', 'CETUS',
    'SWELL', 'ACX', 'ORCA', 'VIRTUAL', 'AIXBT', 'PENGU'
]
_COINS_PATTERN = '|'.join(re.escape(c) for c in sorted(CRYPTO_COINS, key=len, reverse=True))
CRYPTO_REGEX = re.compile(rf'(?<![a-zA-Z0-9_\$])({_COINS_PATTERN})(?![a-zA-Z0-9_])', re.IGNORECASE)

def add_crypto_cashtags(text):
    if not text:
        return ""
    return CRYPTO_REGEX.sub(r'$\1', text)

def clean_text(raw_text):
    if not raw_text:
        return ""
    text = re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]', '', raw_text)
    text = text.replace('=>Bigdata', '').replace('=>LINE', '').strip()
    text = add_crypto_cashtags(text)
    return text

def get_video_info(video_url):
    """ดึงข้อมูลหัวข้อคลิปและชื่อช่องจาก YouTube"""
    cookies_candidate = r"D:\Github\Youtube_Playlists_DL\cookies.txt"
    cookies_arg = ["--cookies", cookies_candidate] if os.path.exists(cookies_candidate) else []
    try:
        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--dump-json",
            "--no-playlist",
            *cookies_arg,
            str(video_url).strip()
        ]
        sub_kwargs = get_subprocess_kwargs()
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL, **sub_kwargs)
        if res.returncode == 0 and res.stdout.strip():
            info = json.loads(res.stdout.splitlines()[0])
            channel = info.get('channel') or info.get('uploader') or info.get('uploader_id') or 'YouTube'
            title = info.get('title') or ''
            webpage_url = info.get('webpage_url') or video_url
            return {
                'channel': channel,
                'title': title,
                'url': webpage_url
            }
    except Exception as e:
        print(f"[BinanceSquareBot] get_video_info error: {e}")
    return {
        'channel': 'YouTube',
        'title': '',
        'url': video_url
    }

def download_and_cut_clip(video_url, start_sec, end_sec, output_file, progress_callback=None):
    """ดาวน์โหลดเฉพาะช่วงเวลาที่ต้องการ (start_sec ถึง end_sec) ด้วย yt-dlp และ ffmpeg ความละเอียด 480p"""
    if end_sec <= start_sec:
        end_sec = start_sec + 60

    if (end_sec - start_sec) < MIN_CLIP_DURATION_SEC:
        end_sec = start_sec + MIN_CLIP_DURATION_SEC

    if (end_sec - start_sec) > MAX_CLIP_DURATION_SEC:
        end_sec = start_sec + MAX_CLIP_DURATION_SEC

    sub_kwargs = get_subprocess_kwargs()

    # ⚡ Smart Cache Check: Check if full video is already cached in d:\Github\eworker\cache\videos\{video_id}.mp4
    v_id = None
    m_yt = re.search(r'(?:v=|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', video_url)
    if m_yt:
        v_id = m_yt.group(1)

    cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "videos")
    os.makedirs(cache_dir, exist_ok=True)
    cached_video_file = os.path.join(cache_dir, f"{v_id}.mp4") if v_id else None

    # If not cached, download to cache first
    has_cached = bool(cached_video_file and os.path.exists(cached_video_file) and os.path.getsize(cached_video_file) > 100000)
    if not has_cached and v_id:
        if progress_callback:
            progress_callback(20, "กำลังโหลดคลิปต้นฉบับ 480p เข้าแคช...")
        cookies_candidate = r"D:\Github\Youtube_Playlists_DL\cookies.txt"
        cookies_arg = ["--cookies", cookies_candidate] if os.path.exists(cookies_candidate) else []
        temp_cache_download = os.path.join(cache_dir, f"temp_sq_{v_id}_{int(time.time())}.mp4")

        clean_video_url = f"https://www.youtube.com/watch?v={v_id}" if v_id and len(v_id) == 11 else video_url
        ytdl_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--extractor-args", "youtube:player_client=android,ios,web",
            "-f", "b[height<=480]/bv*[height<=480]+ba/b[height<=360]/b",
            "--merge-output-format", "mp4",
            *cookies_arg,
            "-o", temp_cache_download,
            clean_video_url
        ]
        proc = subprocess.run(ytdl_cmd, capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL, **sub_kwargs)
        if os.path.exists(temp_cache_download) and os.path.getsize(temp_cache_download) > 100000:
            try:
                if cached_video_file and os.path.exists(cached_video_file):
                    os.remove(cached_video_file)
                shutil.move(temp_cache_download, cached_video_file)
                has_cached = True
                print(f"[BinanceSquareBot] ✅ Cached video successfully: {cached_video_file}")
            except Exception as me:
                print(f"[BinanceSquareBot] Cache move error: {me}")

    # If cached video is ready: slice with ffmpeg in 0.5s!
    if has_cached and cached_video_file and os.path.exists(cached_video_file):
        if progress_callback:
            progress_callback(40, "กำลังตัดต่อคลิปจากแคช (0.5s ⚡)...")
        slice_cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_sec),
            "-to", str(end_sec),
            "-i", cached_video_file,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
            "-c:a", "aac", "-b:a", "128k",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",
            output_file
        ]
        subprocess.run(slice_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60, **sub_kwargs)

        if not os.path.exists(output_file) or os.path.getsize(output_file) < 1000:
            slice_copy_cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_sec),
                "-to", str(end_sec),
                "-i", cached_video_file,
                "-c", "copy",
                "-movflags", "+faststart",
                output_file
            ]
            subprocess.run(slice_copy_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, **sub_kwargs)
    else:
        # Fallback to direct section download
        if progress_callback:
            progress_callback(25, "ดาวน์โหลดช่วงเวลาที่ระบุ (Direct Download)...")
        section_arg = f"*{start_sec}-{end_sec}"
        cookies_candidate = r"D:\Github\Youtube_Playlists_DL\cookies.txt"
        cookies_arg = ["--cookies", cookies_candidate] if os.path.exists(cookies_candidate) else []
        clean_video_url = f"https://www.youtube.com/watch?v={v_id}" if v_id and len(v_id) == 11 else video_url
        fb_cmd = [
            sys.executable, "-m", "yt_dlp",
            "--extractor-args", "youtube:player_client=android,ios,web",
            "--download-sections", section_arg,
            "-f", "b[height<=480]/bv*[height<=480]+ba/b[height<=360]/b",
            "--merge-output-format", "mp4",
            *cookies_arg,
            "-o", output_file,
            clean_video_url
        ]
        subprocess.run(fb_cmd, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL, **sub_kwargs)

    # Check output file
    actual_path = output_file
    if not os.path.exists(actual_path):
        if os.path.exists(output_file + ".mp4"):
            actual_path = output_file + ".mp4"
        else:
            base_dir = os.path.dirname(output_file)
            prefix = os.path.basename(output_file).split('.')[0]
            candidates = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if f.startswith(prefix)]
            if candidates:
                actual_path = candidates[0]
            else:
                raise Exception("Clip download/slice failed, output video file not found")

    if progress_callback:
        progress_callback(58, "ตัดต่อ & จัด Faststart...")

    # Faststart remux
    fast_path = os.path.splitext(actual_path)[0] + "_fast.mp4"
    try:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", actual_path, "-c", "copy", "-movflags", "+faststart", fast_path]
        subprocess.run(
            cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=30, **sub_kwargs
        )
        if os.path.exists(fast_path) and os.path.getsize(fast_path) > 0:
            try:
                os.remove(actual_path)
            except:
                pass
            actual_path = fast_path
    except Exception as e:
        print(f"[BinanceSquareBot] faststart remux notice: {e}")

    return actual_path

def get_video_duration(video_path, fallback_duration=30):
    """หาความยาววิดีโอ (วินาที) ด้วย ffprobe"""
    try:
        sub_kwargs = get_subprocess_kwargs()
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True,
            stdin=subprocess.DEVNULL, **sub_kwargs
        )
        duration = float(result.stdout.strip())
        return max(1, int(round(duration)))
    except Exception as e:
        print(f"[BinanceSquareBot] ffprobe warning: {e}")
        return max(1, int(fallback_duration))

def extract_cover_image(video_path, cover_path):
    """ดึงภาพปก (1 frame) จากวิดีโอโดยใช้ ffmpeg ตามสเปก Binance Square"""
    sub_kwargs = get_subprocess_kwargs()
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        cover_path
    ]
    subprocess.run(
        cmd, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **sub_kwargs
    )
    if not os.path.exists(cover_path) or os.path.getsize(cover_path) == 0:
        cmd_fallback = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", "00:00:00.5",
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            cover_path
        ]
        subprocess.run(
            cmd_fallback, check=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **sub_kwargs
        )

def api_call(endpoint, api_key, body, base_url=BASE_URL_V2):
    """ส่งคำขอไปยัง Binance Square OpenAPI"""
    url = f"{base_url}{endpoint}"
    headers = {
        "X-Square-OpenAPI-Key": api_key,
        "Content-Type": "application/json",
        "clienttype": "binanceSkill"
    }
    payload = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers=headers)
    
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode('utf-8')
            res = json.loads(raw)
            if res.get("code") != "000000":
                raise Exception(f"Binance API Error [{res.get('code')}]: {res.get('message')}")
            return res.get("data")
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8', errors='ignore')
        raise Exception(f"Binance HTTP {e.code}: {err_msg}")

def upload_to_s3(presigned_url, file_path, content_type):
    """อัปโหลดไฟล์ไปยัง S3 Presigned URL"""
    with open(file_path, 'rb') as f:
        data = f.read()

    req = urllib.request.Request(
        presigned_url,
        data=data,
        headers={"Content-Type": content_type},
        method="PUT"
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status not in (200, 204):
            raise Exception(f"S3 Upload failed status: {resp.status}")

def poll_ticket_status(api_key, file_ticket):
    """ตรวจสอบสถานะการประมวลผลไฟล์บน Binance Square"""
    for i in range(MAX_POLL_RETRIES):
        data = api_call("/image/imageStatus", api_key, {"fileTicket": file_ticket})
        status = data.get("status")
        if status == 1:
            return data
        elif status == 2:
            raise Exception(f"File processing failed: {data.get('failedReason')}")
        time.sleep(POLL_INTERVAL_SEC)
    raise Exception(f"Poll timed out after {MAX_POLL_RETRIES} attempts")

def upload_image(api_key, img_path, progress_callback=None):
    """อัปโหลดภาพปกไปยัง Binance Square"""
    if progress_callback:
        progress_callback(88, "อัปโหลดภาพปก...")
    img_name = os.path.basename(img_path)
    res = api_call("/image/presignedUrl", api_key, {"imageName": img_name})
    presigned_url = res.get("presignedUrl")
    file_ticket = res.get("fileTicket")

    upload_to_s3(presigned_url, img_path, "image/png")
    status_data = poll_ticket_status(api_key, file_ticket)
    return status_data.get("imageUrl")

def upload_video(api_key, video_path, progress_callback=None):
    """อัปโหลดคลิปวิดีโอไปยัง Binance Square"""
    file_name = os.path.basename(video_path)
    file_size = os.path.getsize(video_path)
    if progress_callback:
        progress_callback(68, "ขอ URL อัปโหลดวิดีโอ...")
    res = api_call("/video/preSign", api_key, {"fileName": file_name, "size": file_size})
    presigned_url = res.get("presignedUrl")
    file_ticket = res.get("fileTicket")

    if progress_callback:
        progress_callback(72, "กำลังส่งไฟล์วิดีโอขึ้น Cloud...")
    upload_to_s3(presigned_url, video_path, "video/mp4")

    if progress_callback:
        progress_callback(82, "ตรวจสอบสถานะไฟล์วิดีโอ...")
    poll_ticket_status(api_key, file_ticket)
    return file_ticket

def publish_post(api_key, file_ticket, cover_url, duration, post_text, progress_callback=None):
    """โพสต์วิดีโอลง Binance Square ผ่าน API"""
    if progress_callback:
        progress_callback(94, "กำลังเผยแพร่ลง Binance Square...")
    # ตรวจสอบให้แน่ใจว่า duration ขั้นต่ำ 15 วินาที และไม่เกิน 300 วินาที (5 นาที)
    duration_sec = max(MIN_CLIP_DURATION_SEC, min(int(duration), MAX_CLIP_DURATION_SEC))
    body = {
        "contentType": 3,
        "fileTicket": file_ticket,
        "cover": cover_url,
        "videoTimeSeconds": duration_sec,
        "isPublish": True,
        "bodyTextOnly": post_text
    }
    return api_call("/content/add", api_key, body, base_url=BASE_URL_V1)

def process_clip_and_post(data, progress_callback=None):
    """
    ประมวลผลขั้นตอนทั้งหมด:
    1. รับพารามิเตอร์ videoUrl, startSeconds, endSeconds, rawText, apiKey
    2. จัดรูปแบบข้อความพร้อมให้เครดิตช่อง
    3. ตัดต่อคลิป YouTube 480p (ขั้นต่ำ 15 วินาที, จำกัดไม่เกิน 5 นาที)
    4. ดึงภาพปก
    5. อัปโหลดและโพสต์ขึ้น Binance Square
    6. ลบไฟล์ชั่วคราวทิ้งอัตโนมัติ
    """
    if progress_callback:
        progress_callback(5, "เริ่มเตรียมข้อมูล...")

    video_url = data.get("videoUrl", "").strip()
    if not video_url:
        raise Exception("Missing videoUrl")
        
    api_key = data.get("apiKey", "").strip()
    if not api_key:
        api_key = "31c6e24cebae4e6d8fffec97e9306df2"

    start_sec = int(data.get("startSeconds", 0))
    end_sec = int(data.get("endSeconds", start_sec + 60))
    if end_sec <= start_sec:
        end_sec = start_sec + 60
    # ปรับความยาวคลิปขั้นต่ำให้ไม่น้อยกว่า 15 วินาที
    if (end_sec - start_sec) < MIN_CLIP_DURATION_SEC:
        print(f"[BinanceSquareBot] ⚠️ ความยาวคลิป ({end_sec - start_sec}s) สั้นกว่าขั้นต่ำ {MIN_CLIP_DURATION_SEC} วินาที! ปรับเพิ่มเป็น {MIN_CLIP_DURATION_SEC} วินาที")
        end_sec = start_sec + MIN_CLIP_DURATION_SEC
    # ป้องกันไม่ให้คลิปยาวเกิน 5 นาที (300 วินาที)
    if (end_sec - start_sec) > MAX_CLIP_DURATION_SEC:
        print(f"[BinanceSquareBot] ⚠️ ความยาวคลิป ({end_sec - start_sec}s) เกิน 5 นาที! จำกัดไว้ที่ {MAX_CLIP_DURATION_SEC} วินาที")
        end_sec = start_sec + MAX_CLIP_DURATION_SEC
    raw_text = data.get("rawText", "")

    # 1. ทำความสะอาดข้อความ และดึงเครดิตช่อง
    clean_content = clean_text(raw_text)
    if progress_callback:
        progress_callback(10, "ดึงข้อมูลชื่อช่อง YouTube...")
    video_info = get_video_info(video_url)
    channel_name = video_info.get("channel") or "YouTube"
    
    # จัดรูปแบบโพสต์ตามที่ต้องการ (ไม่ใส่ลิงก์คลิป ใส่เฉพาะชื่อช่อง)
    post_text = f"{clean_content}\n\n-----\nsource: {channel_name}"

    temp_dir = tempfile.mkdtemp(prefix="sq_clip_")
    video_clip_path = None
    cover_image_path = os.path.join(temp_dir, "cover.png")

    try:
        # 2. ดาวน์โหลดและตัดคลิป 480p
        if progress_callback:
            progress_callback(18, "เตรียมโหลดคลิป 480p...")
        output_template = os.path.join(temp_dir, "clip.mp4")
        video_clip_path = download_and_cut_clip(video_url, start_sec, end_sec, output_template, progress_callback=progress_callback)
        
        # 3. ตรวจสอบความยาว
        if progress_callback:
            progress_callback(62, "ตรวจสอบความยาวคลิป...")
        duration = get_video_duration(video_clip_path, fallback_duration=min(MAX_CLIP_DURATION_SEC, max(MIN_CLIP_DURATION_SEC, end_sec - start_sec)))
        if duration > MAX_CLIP_DURATION_SEC:
            print(f"[BinanceSquareBot] ⚠️ ความยาววิดีโอ ({duration}s) เกิน 5 นาที! จำกัดค่าส่ง Binance API เป็น {MAX_CLIP_DURATION_SEC}s")
            duration = MAX_CLIP_DURATION_SEC
        elif duration < MIN_CLIP_DURATION_SEC:
            print(f"[BinanceSquareBot] ⚠️ ความยาววิดีโอ ({duration}s) ต่ำกว่าขั้นต่ำ {MIN_CLIP_DURATION_SEC}s! ปรับค่าส่ง Binance API เป็น {MIN_CLIP_DURATION_SEC}s")
            duration = MIN_CLIP_DURATION_SEC

        # 4. ดึงภาพปก
        if progress_callback:
            progress_callback(65, "สร้างภาพปกวิดีโอ...")
        extract_cover_image(video_clip_path, cover_image_path)

        # 5. อัปโหลดวิดีโอและภาพปก
        print("[BinanceSquareBot] 📤 Uploading video to Binance Square...")
        video_ticket = upload_video(api_key, video_clip_path, progress_callback=progress_callback)

        print("[BinanceSquareBot] 🖼️ Uploading cover image...")
        cover_url = upload_image(api_key, cover_image_path, progress_callback=progress_callback)

        # 6. เผยแพร่โพสต์
        print("[BinanceSquareBot] 🚀 Publishing post...")
        result = publish_post(api_key, video_ticket, cover_url, duration, post_text, progress_callback=progress_callback)
        
        post_id = result.get("id") if result else None
        share_link = result.get("shareLink") if result else None
        print(f"[BinanceSquareBot] ✅ Published successfully! ID: {post_id}, Link: {share_link}")

        if progress_callback:
            progress_callback(100, "โพสต์สำเร็จเรียบร้อย!")

        return {
            "success": True,
            "id": post_id,
            "shareLink": share_link,
            "videoTitle": video_info.get("title") or "",
            "channel": channel_name,
            "message": "โพสต์ลง Binance Square สำเร็จเรียบร้อยแล้ว!"
        }

    finally:
        # 7. ลบไฟล์วิดีโอและโฟลเดอร์ชั่วคราวทิ้งทันที เพื่อไม่ให้หนักเครื่อง
        try:
            if video_clip_path and os.path.exists(video_clip_path):
                os.remove(video_clip_path)
            if os.path.exists(cover_image_path):
                os.remove(cover_image_path)
            if os.path.exists(temp_dir):
                for f in os.listdir(temp_dir):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                    except:
                        pass
                os.rmdir(temp_dir)
            print("[BinanceSquareBot] 🧹 Cleaned up temporary video files successfully.")
        except Exception as cleanup_err:
            print(f"[BinanceSquareBot] Warning during cleanup: {cleanup_err}")
