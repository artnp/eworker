import http.server
import socketserver
import json
import os
import shutil
import time
import threading
import queue
import urllib.request
import urllib.error
import webbrowser
from urllib.parse import urlparse, parse_qs
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import asyncio
import base64
import re
import sys
import tempfile
import requests

# --- CONFIG ---
PORT = 5000
# ค้นหาพาธโฟลเดอร์ Downloads และ Desktop
DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads")
DESKTOP_PATH = os.path.join(os.path.expanduser("~"), "Desktop")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "สำรองงาน_example-complete")

def _get_file_hash(target):
    import hashlib
    if isinstance(target, bytes):
        return hashlib.md5(target).hexdigest()
    if isinstance(target, str) and os.path.exists(target):
        h = hashlib.md5()
        with open(target, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
        return h.hexdigest()
    return None

def deduplicate_backup_folder():
    """
    จัดระเบียบและกำจัดไฟล์ซ้ำระหว่างชุดใน 'สำรองงาน_example-complete':
    - ถ้า bak2 ซ้ำกับ bak1: ลบ bak2 แล้วดึง bak3 ขึ้นมา
    - ถ้า bak3 ซ้ำกับ bak2: ลบ bak3
    """
    try:
        bak1_c = os.path.join(BACKUP_DIR, "complete_bak1.png")
        bak2_c = os.path.join(BACKUP_DIR, "complete_bak2.png")
        bak3_c = os.path.join(BACKUP_DIR, "complete_bak3.png")

        bak1_hash = _get_file_hash(bak1_c)
        bak2_hash = _get_file_hash(bak2_c)
        bak3_hash = _get_file_hash(bak3_c)

        # 1. ถ้า bak2 ซ้ำกับ bak1
        if bak1_hash and bak2_hash and bak1_hash == bak2_hash:
            print("[Watcher Backup] 🧹 bak2 is duplicate of bak1. Removing bak2...")
            for prefix in ("example", "complete"):
                f2 = os.path.join(BACKUP_DIR, f"{prefix}_bak2.png")
                f3 = os.path.join(BACKUP_DIR, f"{prefix}_bak3.png")
                if os.path.exists(f2): os.remove(f2)
                if os.path.exists(f3): shutil.move(f3, f2)
            bak2_hash = _get_file_hash(bak2_c)
            bak3_hash = _get_file_hash(bak3_c)

        # 2. ถ้า bak3 ซ้ำกับ bak2
        if bak2_hash and bak3_hash and bak2_hash == bak3_hash:
            print("[Watcher Backup] 🧹 bak3 is duplicate of bak2. Removing bak3...")
            for prefix in ("example", "complete"):
                f3 = os.path.join(BACKUP_DIR, f"{prefix}_bak3.png")
                if os.path.exists(f3): os.remove(f3)
    except Exception as e:
        print(f"[Watcher Backup] Warning during deduplicate: {e}")

def backup_desktop_files(incoming_data=None, incoming_path=None):
    """
    Auto backup desktop/example.png และ desktop/complete.png ก่อนถูกบันทึก/เขียนทับด้วยภาพใหม่
    เก็บประวัติย้อนหลัง 3 ชุด ในโฟลเดอร์ 'สำรองงาน_example-complete':
      - ชุดที่ 1: example_bak1.png, complete_bak1.png (งานล่าสุดก่อนหน้า)
      - ชุดที่ 2: example_bak2.png, complete_bak2.png
      - ชุดที่ 3: example_bak3.png, complete_bak3.png
    """
    try:
        desktop_complete = os.path.join(DESKTOP_PATH, "complete.png")
        desktop_example = os.path.join(DESKTOP_PATH, "example.png")

        has_complete = os.path.exists(desktop_complete)
        has_example = os.path.exists(desktop_example)

        if not has_complete and not has_example:
            return

        os.makedirs(BACKUP_DIR, exist_ok=True)

        desktop_complete_hash = _get_file_hash(desktop_complete)

        # 1. ถ้ามี incoming file/data ส่งมา และ hash ตรงกับ Desktop/complete.png ปัจจุบัน 100%
        # แสดงว่าภาพใหม่ที่จะเขียนทับคือภาพเดิม ไม่มีการเปลี่ยนแปลง -> ข้ามการสำรอง
        if incoming_data is not None:
            incoming_hash = _get_file_hash(incoming_data)
            if incoming_hash and desktop_complete_hash and incoming_hash == desktop_complete_hash:
                print("[Watcher Backup] ℹ️ Incoming image matches current Desktop image, skipping backup.")
                return
        elif incoming_path is not None and os.path.exists(incoming_path):
            incoming_hash = _get_file_hash(incoming_path)
            if incoming_hash and desktop_complete_hash and incoming_hash == desktop_complete_hash:
                print("[Watcher Backup] ℹ️ Incoming file matches current Desktop image, skipping backup.")
                return

        bak1_complete = os.path.join(BACKUP_DIR, "complete_bak1.png")
        bak1_hash = _get_file_hash(bak1_complete)

        # 2. ป้องกันการสำรองซ้ำซ้อน: ถ้า Desktop/complete.png ตรงกับ complete_bak1.png อยู่แล้ว
        # ห้ามหมุน (rotate) เด็ดขาด เพื่อไม่ให้ bak1 กับ bak2 กลายเป็นภาพเดียวกัน
        if desktop_complete_hash and bak1_hash and desktop_complete_hash == bak1_hash:
            # Sync example.png ไป bak1_example ถ้ายังไม่มี
            bak1_example = os.path.join(BACKUP_DIR, "example_bak1.png")
            if has_example and not os.path.exists(bak1_example):
                try:
                    shutil.copy2(desktop_example, bak1_example)
                except Exception:
                    pass
            print("[Watcher Backup] ℹ️ Desktop/complete.png already backed up in bak1 (identical hash), skipping rotation.")
            return

        print("[Watcher Backup] 🔄 Auto-backing up previous Desktop files to 'สำรองงาน_example-complete'...")

        # หมุนประวัติ 3 ชุด: bak2 -> bak3, bak1 -> bak2
        for i in (2, 1):
            for prefix in ("example", "complete"):
                src_file = os.path.join(BACKUP_DIR, f"{prefix}_bak{i}.png")
                dst_file = os.path.join(BACKUP_DIR, f"{prefix}_bak{i+1}.png")
                if os.path.exists(src_file):
                    try:
                        if os.path.exists(dst_file):
                            os.remove(dst_file)
                        shutil.move(src_file, dst_file)
                    except Exception as e:
                        print(f"[Watcher Backup] Warning moving {src_file} -> {dst_file}: {e}")

        # คัดลอกไฟล์จาก Desktop มาเป็น bak1
        for prefix in ("example", "complete"):
            src_desktop = os.path.join(DESKTOP_PATH, f"{prefix}.png")
            dst_bak1 = os.path.join(BACKUP_DIR, f"{prefix}_bak1.png")
            if os.path.exists(src_desktop):
                try:
                    shutil.copy2(src_desktop, dst_bak1)
                    print(f"[Watcher Backup] 📦 Saved: {prefix}_bak1.png")
                except Exception as e:
                    print(f"[Watcher Backup] Error copying {src_desktop} -> {dst_bak1}: {e}")

        # ถ้าไม่มี example.png บน Desktop ให้สร้าง example_bak1.png จาก complete_bak1.png
        bak1_complete_path = os.path.join(BACKUP_DIR, "complete_bak1.png")
        bak1_example_path = os.path.join(BACKUP_DIR, "example_bak1.png")
        if os.path.exists(bak1_complete_path) and not os.path.exists(bak1_example_path):
            try:
                from watermark_engine import create_anti_ai_watermark
                from PIL import Image
                with Image.open(bak1_complete_path) as b_img:
                    ex_img = create_anti_ai_watermark(b_img)
                    ex_img.save(bak1_example_path, format="PNG")
                    print(f"[Watcher Backup] 📦 Generated: example_bak1.png")
            except Exception as we:
                print(f"[Watcher Backup] Error creating example_bak1: {we}")

        deduplicate_backup_folder()
        print("[Watcher Backup] ✅ Backup finished successfully (maintained 3 unique sets).")
    except Exception as err:
        print(f"[Watcher Backup] ❌ Backup error: {err}")

# --- MODE ---
# 'hub' = crop อย่างเดียว ส่ง Desktop (ไม่มี QR)
# 'fb'  = crop + ฝัง QR + auto paste + auto post
current_mode = 'hub'

# คอนดิชั่นสำหรับแจ้งเตือน Frontend
export_event = threading.Event()
last_exported_path = ""
ps_trigger_event = threading.Event()
ps_trigger_data = {}

# --- FILE HANDLER ---
class DownloadHandler(FileSystemEventHandler):
    _processing_lock = threading.Lock()
    _last_processed_mtime = 0  # ★ ป้องกัน process ซ้ำ

    def _handle(self, event):
        global current_mode
        if event.is_directory: return
        target_file = getattr(event, 'dest_path', event.src_path)
        filename = os.path.basename(target_file)
        
        # เมื่อ Gemini/Copilot/Fast Download เซฟ complete.* หรือ complete_bot.* มา
        fname_lower = filename.lower()
        is_complete_file = (fname_lower.startswith("complete") and fname_lower.endswith((".png", ".jpg", ".jpeg", ".webp"))) or fname_lower in ["complete.png", "complete_bot.png", "complete.jpg", "complete.jpeg", "complete.webp"]
        if is_complete_file:
            # ★ ป้องกัน process ซ้ำ: เช็ค mtime ว่าเป็นไฟล์ใหม่จริงๆ
            if not self._processing_lock.acquire(blocking=False):
                print("[Watcher] Already processing, skipping duplicate trigger")
                return
            try:
                time.sleep(1.5) # รอให้ไฟล์เขียนเสร็จสนิท
                
                if not os.path.exists(target_file):
                    print("[Watcher] File disappeared, skipping")
                    return
                
                file_mtime = os.path.getmtime(target_file)
                if abs(file_mtime - self._last_processed_mtime) < 1.0:
                    print(f"[Watcher] Same file (mtime diff < 1s), skipping duplicate")
                    return
                DownloadHandler._last_processed_mtime = file_mtime
                
                script_dir = os.path.dirname(os.path.abspath(__file__))
                script_path = os.path.join(script_dir, "screenshot_donate.py")
                
                # ★ Auto backup complete.png & example.png ก่อนถูกบันทึก/เขียนทับ
                if "complete_bot" not in filename.lower():
                    backup_desktop_files(incoming_path=target_file)
                
                # เลือกโหมดตาม current_mode
                if current_mode == 'chrome_hub':
                    mode_flag = "--clean"
                    skip_delete = False
                    print(f"[Watcher] Detected Export (Chrome hub) -> Running {mode_flag}")
                else:
                    mode_flag = "--donate" if current_mode == 'fb' else "--clean"
                    skip_delete = False
                    print(f"[Watcher] Detected Export -> Running {mode_flag}")
                
                import subprocess, sys
                result = subprocess.run(
                    [sys.executable, script_path, mode_flag, target_file],
                    capture_output=True, text=True, timeout=60
                )
                if result.stdout:
                    print(f"[Watcher] Output:\n{result.stdout.strip()}")
                if result.returncode != 0:
                    print(f"[Watcher] ❌ Error in screenshot_donate.py (code {result.returncode}):\n{result.stderr.strip()}")
                
                # ไฟล์ผลลัพธ์อยู่ที่ Desktop เสมอ
                output_name = "complete_bot.png" if "complete_bot" in filename.lower() else "complete.png"
                target_path = os.path.join(DESKTOP_PATH, output_name)
                global last_exported_path
                last_exported_path = target_path
                
                print(f"[Watcher] Done. Result: {target_path}")
                # แจ้งเตือน Frontend ว่างานเสร็จแล้ว
                export_event.set()
                
                # ★ ลบ complete.* ใน Downloads หลัง process เสร็จ
                # เพื่อป้องกัน watcher หยิบภาพเก่าที่มีกรอบเขียวจาก Desktop/Downloads ย้อนกลับมาใช้
                # ★ chrome_hub mode: ไม่ลบต้นฉบับ
                if not skip_delete:
                    try:
                        if os.path.exists(target_file):
                            os.remove(target_file)
                            print(f"[Watcher] ✅ Deleted source {target_file} to prevent stale image reuse")
                    except Exception as del_err:
                        print(f"[Watcher] Could not delete source (non-critical): {del_err}")
                else:
                    print(f"[Watcher] (Chrome hub) Keeping original {target_file}")
                    
            except Exception as e:
                print(f"[Watcher] Error: {e}")
            finally:
                self._processing_lock.release()

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def on_moved(self, event):
        self._handle(event)

class DesktopHandler(FileSystemEventHandler):
    _last_mtime = 0

    def _handle(self, event):
        if event.is_directory: return
        filename = os.path.basename(event.src_path)
        fname_lower = filename.lower()
        if (fname_lower.startswith("complete") and fname_lower.endswith((".png", ".jpg", ".jpeg", ".webp"))) or fname_lower in ["complete.png", "complete_bot.png", "complete.jpg", "complete.jpeg", "complete.webp"]:
            time.sleep(1) # wait for file write
            try:
                if not os.path.exists(event.src_path): return
                mtime = os.path.getmtime(event.src_path)
                if abs(mtime - self._last_mtime) < 1.5: return
                self._last_mtime = mtime

                # Auto sync/generate Desktop/example.png if modified externally (e.g. from Photoshop)
                if fname_lower == "complete.png":
                    example_path = os.path.join(DESKTOP_PATH, "example.png")
                    need_generate_example = True
                    if os.path.exists(example_path):
                        ex_mtime = os.path.getmtime(example_path)
                        if abs(ex_mtime - mtime) < 2.0:
                            need_generate_example = False
                    
                    if need_generate_example:
                        try:
                            from watermark_engine import create_anti_ai_watermark
                            from PIL import Image
                            with Image.open(event.src_path) as c_img:
                                ex_img = create_anti_ai_watermark(c_img)
                                ex_img.save(example_path, format='PNG')
                                print(f"[Watcher Desktop] Auto-synced Desktop/example.png")
                        except Exception as we:
                            print(f"[Watcher Desktop] Error auto-generating example.png: {we}")

                global last_exported_path
                last_exported_path = event.src_path
                export_event.set()
            except Exception as e:
                print(f"[Watcher Desktop] Error: {e}")

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

# --- BIGDATA VIDEO PROCESSING, TRAY & CACHE ---
tray_icon_instance = None
VIDEO_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "videos")
os.makedirs(VIDEO_CACHE_DIR, exist_ok=True)

# Tracking cached videos and cleanup requests
cached_video_ref_counts = {}  # video_id -> count of active/pending tasks
pending_cleanup_videos = set() # video_ids requested to clean up when Gemini tab closes
video_lock = threading.Lock()
cached_github_config = {}

def extract_video_id(url):
    if not url:
        return None
    m = re.search(r'(?:v=|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})', str(url))
    return m.group(1) if m else None

def make_tray_icon(percent=None, q_len=0, phase='idle'):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGBA', (64, 64), (15, 23, 42, 255))
    draw = ImageDraw.Draw(img)

    if percent is None or (phase in ('idle', 'done') and q_len == 0 and (percent == 0 or percent == 100)):
        # Default AI Hub icon (Blue rounded rectangle with bold AI)
        draw.rounded_rectangle([2, 2, 61, 61], radius=14, fill=(37, 99, 235), outline=(96, 165, 250), width=2)
        try:
            font = ImageFont.truetype('arialbd.ttf', 28)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), "AI", font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((64 - tw) // 2, (64 - th) // 2 - 2), "AI", fill=(255, 255, 255), font=font)
        return img

    pct = max(0, min(100, int(percent or 0)))
    # Active Progress Icon
    draw.rounded_rectangle([2, 2, 61, 61], radius=12, fill=(15, 23, 42), outline=(56, 189, 248), width=2)

    # Progress bar at bottom
    bar_w = int((pct / 100.0) * 52)
    draw.rectangle([6, 50, 58, 56], fill=(30, 41, 59))
    if bar_w > 0:
        bar_color = (34, 197, 94) if pct >= 90 else (6, 182, 212)
        draw.rectangle([6, 50, 6 + bar_w, 56], fill=bar_color)

    # Draw percentage text in center
    try:
        font = ImageFont.truetype('arialbd.ttf', 22 if pct < 100 else 18)
    except Exception:
        font = ImageFont.load_default()
    txt = f"{pct}%"
    bbox = draw.textbbox((0, 0), txt, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((64 - tw) // 2, 13), txt, fill=(255, 255, 255), font=font)

    # Queue badge indicator at top right if queue > 0
    if q_len > 0:
        badge_txt = f"+{q_len}" if q_len < 10 else "9+"
        try:
            badge_font = ImageFont.truetype('arialbd.ttf', 11)
        except Exception:
            badge_font = ImageFont.load_default()
        draw.rounded_rectangle([38, 2, 62, 16], radius=4, fill=(234, 88, 12))
        draw.text((42, 2), badge_txt, fill=(255, 255, 255), font=badge_font)

    return img

def show_tray_notification(title, message):
    # ปิดการแจ้งเตือน Windows Notification Popup ตามที่ผู้ใช้ต้องการเพื่อไม่ให้เด้งรบกวนหน้าจอ
    print(f"[Tray Banner - Silenced] 🔔 {title}: {message}")
    return

last_notified_phase = None

def update_tray_status(percent=None, phase=None, message=None, force_notify=False):
    global tray_icon_instance, bigdata_task_queue, last_notified_phase
    if not tray_icon_instance:
        return
    try:
        q_size = bigdata_task_queue.qsize()
        if (percent is None or phase in ('idle',)) and q_size == 0:
            tray_icon_instance.title = f"AI Hub Central (Port {PORT}) - พร้อมทำงาน"[:120]
            tray_icon_instance.icon = make_tray_icon(percent=None, q_len=0, phase='idle')
            last_notified_phase = None
        elif phase == 'done' and q_size == 0:
            tray_icon_instance.title = f"[100%] สำเร็จ | บันทึก bigdata เรียบร้อย"[:120]
            tray_icon_instance.icon = make_tray_icon(percent=100, q_len=0, phase='done')
            show_tray_notification("✅ AI Hub Bigdata สำเร็จ 100%", message or "บันทึกลง bigdata.json เรียบร้อย!")
            last_notified_phase = 'done'
        else:
            pct = int(max(0, min(100, percent if percent is not None else 0)))
            phase_map = {
                'queued': 'เข้าคิว',
                'starting': 'เริ่ม',
                'tts': 'TTS',
                'downloading': 'โหลดคลิป',
                'subtitles': 'ซับไตเติล',
                'rendering': 'ตัดต่อ/FX',
                'desktop': 'บันทึกPC',
                'uploading': 'อัปโหลด',
                'github': 'GitHub',
                'done': 'เสร็จ',
                'error': 'ข้อผิดพลาด'
            }
            phase_th = phase_map.get(phase, phase or '')
            title = f"[{pct}%] {phase_th} (คิวรอ: {q_size}) | AI Hub (Port {PORT})"
            tray_icon_instance.title = title[:120]
            tray_icon_instance.icon = make_tray_icon(percent=pct, q_len=q_size, phase=phase)

            # Trigger Windows Notification Banner on key milestones
            milestones = ('queued', 'tts', 'downloading', 'rendering', 'uploading', 'error')
            if force_notify or (phase in milestones and phase != last_notified_phase):
                last_notified_phase = phase
                banner_title = f"[{pct}%] AI Hub Bigdata ({phase_th})"
                banner_msg = f"{message or phase_th} (คิวรอ: {q_size})"
                show_tray_notification(banner_title, banner_msg)
    except Exception as e:
        print(f"[Tray Status Error]: {e}")

def cleanup_video_cache(video_id=None, clean_all=False):
    global cached_video_ref_counts, pending_cleanup_videos
    with video_lock:
        if not os.path.exists(VIDEO_CACHE_DIR):
            return

        # Current video IDs being processed by active/running tasks
        active_ids = {vid for vid, count in cached_video_ref_counts.items() if count > 0}

        if clean_all or video_id == "all":
            # Safely sweep all files in VIDEO_CACHE_DIR that are NOT in active use
            deleted_count = 0
            try:
                for f in os.listdir(VIDEO_CACHE_DIR):
                    f_path = os.path.join(VIDEO_CACHE_DIR, f)
                    if not os.path.isfile(f_path):
                        continue
                    # Protect files that belong to currently active video tasks
                    is_active = any(act in f for act in active_ids)
                    if not is_active:
                        try:
                            os.remove(f_path)
                            deleted_count += 1
                        except Exception as e:
                            print(f"[Bigdata Cache] ⚠️ Could not remove {f}: {e}")
            except Exception as le:
                print(f"[Bigdata Cache] Sweep error: {le}")

            if not active_ids:
                pending_cleanup_videos.clear()
            if deleted_count > 0:
                print(f"[Bigdata Cache] 🧹 Swept & deleted {deleted_count} file(s) from cache\\videos")
            return

        if video_id:
            if cached_video_ref_counts.get(video_id, 0) <= 0:
                cached_video_file = os.path.join(VIDEO_CACHE_DIR, f"{video_id}.mp4")
                if os.path.exists(cached_video_file):
                    try:
                        os.remove(cached_video_file)
                        print(f"[Bigdata Cache] 🧹 Cleaned up cached video {video_id} immediately (Gemini tab closed)")
                    except Exception as ce:
                        print(f"[Bigdata Cache] ⚠️ Could not remove {cached_video_file}: {ce}")

                # Clean any lingering temporary yt-dlp files for this video
                try:
                    for f in os.listdir(VIDEO_CACHE_DIR):
                        if video_id in f and (f.startswith("temp_") or f.endswith(".part") or f.endswith(".ytdl")):
                            try:
                                os.remove(os.path.join(VIDEO_CACHE_DIR, f))
                            except Exception:
                                pass
                except Exception:
                    pass

                pending_cleanup_videos.discard(video_id)
            else:
                pending_cleanup_videos.add(video_id)
                print(f"[Bigdata Cache] ⏳ Marked {video_id} for cleanup after {cached_video_ref_counts[video_id]} pending task(s) finish")

def mark_video_for_cleanup(video_id):
    cleanup_video_cache(video_id=video_id, clean_all=False)

bigdata_job_progress = {
    "percent": 0,
    "phase": "idle",
    "message": "พร้อมทำงาน",
    "result": None
}
last_bigdata_result = None
bigdata_task_queue = queue.Queue()
video_pipeline_lock = threading.Lock()
binance_count_lock = threading.Lock()
binance_queue_count = 0

STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "status.json")

def write_status_file(percent, phase, message, task_type="bigdata", queue_size=0, detail=""):
    try:
        data = {
            "percent": int(percent) if percent is not None else 0,
            "phase": phase,
            "status": message,
            "detail": detail or f"[{task_type.capitalize()}] {message}",
            "taskType": task_type,
            "queueSize": queue_size,
            "timestamp": int(time.time() * 1000)
        }
        tmp_path = STATUS_FILE + ".tmp"
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp_path, STATUS_FILE)
        if phase != "idle" and task_type in ("bigdata", "binance"):
            ensure_watcher_gui_running()
    except Exception:
        pass

def ensure_watcher_gui_running():
    try:
        import psutil
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmd = ' '.join(proc.info.get('cmdline') or [])
                if 'watcher_gui.ps1' in cmd:
                    return
            except Exception:
                pass
        gui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watcher_gui.ps1")
        if os.path.exists(gui_path):
            subprocess.Popen([
                "powershell.exe", "-WindowStyle", "Hidden", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", gui_path, str(os.getpid())
            ])
            print("[Watcher] 🚀 Launched floating Status & Process Bar Widget (watcher_gui.ps1)")
    except Exception as e:
        print(f"[Watcher] Error launching watcher_gui.ps1: {e}")

def set_bigdata_progress(percent, phase, message, result=None):
    global bigdata_job_progress, last_bigdata_result
    if result is not None:
        last_bigdata_result = result
    pct = int(percent)
    q_len = bigdata_task_queue.qsize()
    bigdata_job_progress = {
        "percent": pct,
        "phase": phase,
        "message": message,
        "result": last_bigdata_result,
        "queue_size": q_len
    }
    print(f"[Bigdata Progress] {pct}% ({phase}) [Queue: {q_len}]: {message}")
    update_tray_status(pct, phase, message)
    write_status_file(pct, phase, message, task_type="bigdata", queue_size=q_len)

def load_github_token_from_ps1():
    try:
        ps1_path = r"D:\Github\token.ps1"
        if os.path.exists(ps1_path):
            with open(ps1_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            m = re.search(r"\$token\s*=\s*'([^']+)'", content)
            if m:
                return m.group(1).strip()
    except Exception as e:
        print(f"[Watcher] Token load error from ps1: {e}")
    return ''

def update_github_reel(clean_text, catbox_url, github_config):
    """
    Appends a new video clip entry to the active bigdata*.json file on GitHub.
    Handles file discovery, 2000-item rollover, UTF-8 base64 encoding, and retry on conflict.
    """
    global cached_github_config
    cfg = dict(cached_github_config or {})
    if github_config and isinstance(github_config, dict):
        cfg.update({k: v for k, v in github_config.items() if v})

    username = cfg.get('username') or 'artnp'
    repository = cfg.get('repository') or 'bigdata'
    branch = cfg.get('branch', 'main') or 'main'
    token = cfg.get('token') or load_github_token_from_ps1()

    if not (username and repository and token):
        print(f"[Bigdata GitHub] Skipping GitHub update: missing credentials in github_config (username={username}, repo={repository}, token={'yes' if token else 'no'})")
        return None

    clean_url = re.sub(r'^https?://', '', catbox_url).strip()
    headers = {
        'Authorization': f'token {token}',
        'User-Agent': 'JavaScript',
        'Cache-Control': 'no-cache'
    }

    api_contents = f"https://api.github.com/repos/{username}/{repository}/contents"
    highest_index = 1
    active_filename = "bigdata1.json"

    try:
        list_resp = requests.get(f"{api_contents}?ref={branch}", headers=headers, timeout=20)
        if list_resp.status_code == 200:
            files = list_resp.json()
            bigdata_files = []
            if isinstance(files, list):
                for f in files:
                    m = re.match(r'^bigdata(\d+)\.json$', f.get('name', ''))
                    if m:
                        bigdata_files.append((int(m.group(1)), f.get('name')))
                if bigdata_files:
                    bigdata_files.sort(key=lambda x: x[0])
                    highest_index, active_filename = bigdata_files[-1]
    except Exception as e:
        print(f"[Bigdata GitHub] Error discovering active bigdata file: {e}")

    for attempt in range(1, 4):
        try:
            file_url = f"{api_contents}/{active_filename}?ref={branch}"
            get_resp = requests.get(file_url, headers=headers, timeout=20)

            existing_arr = []
            current_sha = None

            if get_resp.status_code == 200:
                file_data = get_resp.json()
                current_sha = file_data.get('sha')
                content_b64 = file_data.get('content', '')
                if content_b64:
                    try:
                        content_str = base64.b64decode(content_b64).decode('utf-8').strip()
                        existing_arr = json.loads(content_str)
                    except Exception:
                        repaired = re.sub(r'^\ufeff', '', content_str)
                        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)
                        existing_arr = json.loads(repaired)

                if not isinstance(existing_arr, list):
                    raise RuntimeError(f"{active_filename} is not a JSON array")

                if len(existing_arr) >= 2000:
                    highest_index += 1
                    active_filename = f"bigdata{highest_index}.json"
                    print(f"[Bigdata GitHub] Reached 2000 items limit, rolling over to {active_filename}")
                    existing_arr = []
                    current_sha = None
            elif get_resp.status_code == 404:
                existing_arr = []
                current_sha = None
            else:
                raise RuntimeError(f"GET {active_filename} failed: {get_resp.status_code} - {get_resp.text[:200]}")

            new_entry = {
                "data": clean_text,
                "url": clean_url
            }
            existing_arr.append(new_entry)

            formatted_lines = ["  " + json.dumps(item, ensure_ascii=False) for item in existing_arr]
            new_json_str = "[\n" + ",\n".join(formatted_lines) + "\n]"
            b64_content = base64.b64encode(new_json_str.encode('utf-8')).decode('utf-8')

            put_body = {
                "message": f"Append video summary to {active_filename} via Watcher",
                "content": b64_content,
                "branch": branch
            }
            if current_sha:
                put_body["sha"] = current_sha

            put_resp = requests.put(
                f"{api_contents}/{active_filename}",
                headers={'Authorization': f'token {token}', 'User-Agent': 'JavaScript', 'Content-Type': 'application/json'},
                json=put_body,
                timeout=30
            )

            if put_resp.status_code in (200, 201):
                print(f"[Bigdata GitHub] ✅ Successfully appended item to {active_filename} (Total items: {len(existing_arr)})")
                return {
                    "success": True,
                    "fileName": active_filename,
                    "lineCount": len(existing_arr)
                }
            else:
                print(f"[Bigdata GitHub] PUT attempt {attempt} failed ({put_resp.status_code}): {put_resp.text[:200]}")
                time.sleep(0.5)
        except Exception as ex:
            print(f"[Bigdata GitHub] Attempt {attempt} error: {ex}")
            if attempt == 3:
                raise
            time.sleep(0.5)

    return {"success": False, "error": "All 3 attempts failed"}

def bigdata_queue_worker():
    while True:
        task = bigdata_task_queue.get()
        if task is None:
            break
        if len(task) == 7:
            video_url, start_sec, end_sec, text, copy_to_desktop, github_config, final_id_string = task
        else:
            video_url, start_sec, end_sec, text, copy_to_desktop, github_config = task
            final_id_string = ""
        try:
            with video_pipeline_lock:
                try:
                    process_bigdata_video_task(
                        video_url=video_url,
                        start_sec=start_sec,
                        end_sec=end_sec,
                        text=text,
                        copy_to_desktop=copy_to_desktop,
                        github_config=github_config,
                        final_id_string=final_id_string
                    )
                except Exception as err:
                    print(f"[Bigdata Queue Worker] Error in task: {err}")
                    set_bigdata_progress(0, "error", f"เกิดข้อผิดพลาด: {err}")
        finally:
            bigdata_task_queue.task_done()
            if bigdata_task_queue.qsize() == 0 and binance_queue_count == 0:
                def reset_idle_later():
                    time.sleep(6)
                    if bigdata_task_queue.qsize() == 0 and binance_queue_count == 0:
                        update_tray_status(None, 'idle', 'พร้อมทำงาน')
                        write_status_file(0, 'idle', 'พร้อมทำงาน', task_type="idle")
                        # Sweep any leftover cache files when system is completely idle
                        cleanup_video_cache(clean_all=True)
                threading.Thread(target=reset_idle_later, daemon=True).start()

# Start background queue worker daemon
threading.Thread(target=bigdata_queue_worker, daemon=True).start()

def generate_pill_vector(cx, cy, width, height, radius):
    r = min(radius, height // 2, width // 2)
    x1 = int(cx - width / 2)
    x2 = int(cx + width / 2)
    y1 = int(cy - height / 2)
    y2 = int(cy + height / 2)
    return (
        f"m {x1 + r} {y1} l {x2 - r} {y1} b {x2} {y1} {x2} {y1 + r} {x2} {y1 + r} "
        f"l {x2} {y2 - r} b {x2} {y2} {x2 - r} {y2} {x2 - r} {y2} "
        f"l {x1 + r} {y2} b {x1} {y2} {x1} {y2 - r} {x1} {y2 - r} "
        f"l {x1} {y1 + r} b {x1} {y1} {x1 + r} {y1} {x1 + r} {y1}"
    )

def detect_audio_speech_bounds(audio_file):
    startupinfo = None
    creationflags = 0
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

    dur = 5.0
    try:
        probe = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', audio_file
        ], capture_output=True, text=True, timeout=10, startupinfo=startupinfo, creationflags=creationflags)
        dur = float(probe.stdout.strip())
    except Exception:
        pass

    try:
        cmd = ['ffmpeg', '-i', audio_file, '-af', 'silencedetect=noise=-30dB:d=0.08', '-f', 'null', '-']
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, startupinfo=startupinfo, creationflags=creationflags)
        starts = [float(m.group(1)) for m in re.finditer(r'silence_start:\s*([\d\.]+)', res.stderr)]
        ends = [float(m.group(1)) for m in re.finditer(r'silence_end:\s*([\d\.]+)', res.stderr)]

        speech_start = ends[0] if ends else 0.22
        speech_end = starts[-1] if (starts and starts[-1] > speech_start) else (dur - 0.25)
        speech_start = max(0.05, min(speech_start, 0.45))
        speech_dur = max(0.8, speech_end - speech_start)
        return speech_start, speech_dur, dur
    except Exception as e:
        print(f"[Bigdata Video] Speech bounds detection fallback: {e}")
        return 0.22, max(1.0, dur - 0.75), dur

def calculate_visual_text_width(text, font_size=34):
    if not text:
        return 0
    thai_marks = re.sub(r'[\u0E31\u0E34-\u0E3A\u0E47-\u0E4E]', '', text)
    visual_units = 0.0
    for ch in thai_marks:
        if ch == ' ':
            visual_units += 0.28
        elif re.match(r'[a-zA-Z0-9]', ch):
            visual_units += 0.55
        elif '\u0E01' <= ch <= '\u0E2E':
            visual_units += 0.58
        elif '\u0E40' <= ch <= '\u0E44':
            visual_units += 0.48
        else:
            visual_units += 0.52
    return visual_units * font_size

def format_ass_time(sec):
    if sec is None or sec < 0:
        sec = 0.0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def build_caption_chunks(words, is_vertical=False):
    if not words:
        return []
    chunks = []
    i = 0
    max_chunk_chars = 14 if is_vertical else 20
    max_chunk_words = 3 if is_vertical else 5
    min_chunk_words = 2 if is_vertical else 3

    while i < len(words):
        remaining = len(words) - i
        chunk_size = min_chunk_words
        if remaining <= max_chunk_words:
            total_chars = sum(len(words[i + k].get('word', '')) for k in range(remaining))
            if total_chars <= max_chunk_chars or remaining <= min_chunk_words:
                chunk_size = remaining
            else:
                chunk_size = max(1, (remaining + 1) // 2)
        else:
            char_len = 0
            count = 0
            for k in range(min(max_chunk_words, remaining)):
                char_len += len(words[i + k].get('word', ''))
                count = k + 1
                if char_len >= (max_chunk_chars - 2) and count >= min_chunk_words:
                    break
            chunk_size = max(min_chunk_words, min(max_chunk_words, count))

        chunk_words = words[i:i + chunk_size]
        chunks.append({
            'words': chunk_words,
            'startSec': chunk_words[0]['startSec'],
            'endSec': chunk_words[-1]['endSec']
        })
        i += chunk_size
    return chunks

def build_ass_center_live_tts(clean_text, start_offset=0.22, speech_duration=8.0, target_w=640, target_h=360, is_vertical=False):
    try:
        from pythainlp import word_tokenize
        raw_tokens = word_tokenize(clean_text)
    except Exception:
        raw_tokens = re.findall(r'\S+', clean_text)

    # Filter out empty tokens and standalone punctuation
    raw_words = [w.strip() for w in raw_tokens if w.strip() and not re.match(r'^[\s\.,;:\-–—\(\)\[\]"\'«»]+$', w)]
    if not raw_words:
        return ''

    def word_phonetic_weight(w):
        # Tone marks and floating vowels don't add full syllable length
        base_chars = re.sub(r'[\u0E31\u0E34-\u0E3A\u0E47-\u0E4E]', '', w)
        return max(2, len(base_chars))

    total_weight = sum(word_phonetic_weight(w) for w in raw_words)
    accum = 0.0
    words = []
    dur = max(0.8, float(speech_duration))
    offset = max(0.0, float(start_offset))

    for idx, w in enumerate(raw_words):
        wt = word_phonetic_weight(w)
        s_sec = offset + (accum / total_weight) * dur
        accum += wt
        e_sec = offset + (accum / total_weight) * dur
        words.append({'word': w, 'startSec': s_sec, 'endSec': e_sec})

    chunks = build_caption_chunks(words, is_vertical=is_vertical)
    if not chunks:
        return ''

    cx = target_w / 2
    cy = int(target_h * 0.55) if is_vertical else (target_h / 2)
    base_font_size = 32 if is_vertical else 34
    orange_ass = r"{\c&H003C92FB&\b1}"
    white_ass = r"{\c&H00FFFFFF&\b1}"

    events = []
    for c_idx, chunk in enumerate(chunks):
        next_chunk = chunks[c_idx + 1] if c_idx + 1 < len(chunks) else None
        # Switch seamlessly to next chunk, or close 0.35s after the last spoken word
        chunk_limit_end = next_chunk['startSec'] if next_chunk else (chunk['endSec'] + 0.35)

        chunk_full_text = ''.join(w['word'] for w in chunk['words'])
        chunk_font_size = base_font_size
        max_chars = 14 if is_vertical else 20
        if len(chunk_full_text) > max_chars:
            chunk_font_size = max(24, int(base_font_size - (len(chunk_full_text) - max_chars) * 0.8))

        text_width = calculate_visual_text_width(chunk_full_text, chunk_font_size)
        pill_width = max(110, min(target_w - 24, int(text_width + 56)))
        pill_height = int(chunk_font_size * 1.8)
        pill_radius = int(pill_height / 2)
        pill_vector = generate_pill_vector(cx, cy, pill_width, pill_height, pill_radius)

        # Layer 0: Frosted cyan-bordered pill badge (vdoAI signature design)
        events.append(f"Dialogue: 0,{format_ass_time(chunk['startSec'])},{format_ass_time(chunk_limit_end)},PillBox,,0,0,0,,{{\\an7\\pos(0,0)\\p1}}{pill_vector}{{\\p0}}")

        # Layer 1: Word-by-word karaoke text with orange active highlight matching spoken speech
        for w_idx, current_word in enumerate(chunk['words']):
            next_word = chunk['words'][w_idx + 1] if w_idx + 1 < len(chunk['words']) else None
            w_start = current_word['startSec']
            w_end = next_word['startSec'] if next_word else current_word['endSec']
            if w_end <= w_start:
                continue

            rendered_words_list = []
            for idx, item in enumerate(chunk['words']):
                word = item['word']
                prefix_space = ''
                if idx > 0:
                    prev = chunk['words'][idx - 1]['word']
                    if re.search(r'[a-zA-Z0-9]$', prev) or re.search(r'^[a-zA-Z0-9]', word):
                        prefix_space = ' '
                if idx == w_idx:
                    rendered_words_list.append(f"{prefix_space}{orange_ass}{word}{white_ass}")
                else:
                    rendered_words_list.append(f"{prefix_space}{word}")
            rendered_words = ''.join(rendered_words_list)
            events.append(f"Dialogue: 1,{format_ass_time(w_start)},{format_ass_time(w_end)},LiveTts,,0,0,0,,{{\\an5\\pos({cx},{cy})}}{{\\fs{chunk_font_size}}}{{\\c&H00FFFFFF&\\b1}}{rendered_words}")

        # If there's a hold after the last word until chunk_limit_end, show full white text without lingering orange
        last_word_end = chunk['words'][-1]['endSec']
        if chunk_limit_end > last_word_end + 0.04:
            all_white_text = ''.join(
                (' ' if idx > 0 and (re.search(r'[a-zA-Z0-9]$', chunk['words'][idx - 1]['word']) or re.search(r'^[a-zA-Z0-9]', item['word'])) else '') + item['word']
                for idx, item in enumerate(chunk['words'])
            )
            events.append(f"Dialogue: 1,{format_ass_time(last_word_end)},{format_ass_time(chunk_limit_end)},LiveTts,,0,0,0,,{{\\an5\\pos({cx},{cy})}}{{\\fs{chunk_font_size}}}{{\\c&H00FFFFFF&\\b1}}{all_white_text}")

    events_str = '\n'.join(events)
    ass_template = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {target_w}
PlayResY: {target_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: PillBox,Prompt,10,&H75181008,&H75181008,&H30E8B208,&H80000000,0,0,0,0,100,100,0,0,1,2,0,7,0,0,0,222
Style: LiveTts,Prompt,{base_font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,1,0,0,0,100,100,0,0,1,1.4,0,5,0,0,0,222

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{events_str}
"""
    return ass_template

def process_bigdata_video_task(video_url, start_sec, end_sec, text, copy_to_desktop, github_config=None, final_id_string=""):
    import math
    temp_dir = tempfile.mkdtemp(prefix="bigdata_clip_")
    raw_video = os.path.join(temp_dir, "raw_clip.mp4")
    tts_audio = os.path.join(temp_dir, "tts.mp3")
    final_video = os.path.join(temp_dir, "final_clip.mp4")
    ass_file = os.path.join(temp_dir, "subtitles.ass")

    hide_startupinfo = None
    creation_flags = 0
    if sys.platform == 'win32':
        hide_startupinfo = subprocess.STARTUPINFO()
        hide_startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        hide_startupinfo.wShowWindow = subprocess.SW_HIDE
        creation_flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)

    orig_video_input = video_url
    if video_url and not video_url.startswith("http://") and not video_url.startswith("https://"):
        video_url = f"https://www.youtube.com/watch?v={video_url}"

    try:
        set_bigdata_progress(5, "starting", "เตรียมความพร้อม...")
        start_val = int(start_sec) if start_sec is not None else 0
        end_val = int(end_sec) if end_sec is not None and int(end_sec) > start_val else (start_val + 60)

        # Build fallback YouTube URL format (ระบบสอง)
        v_id_fallback = extract_video_id(video_url)
        youtube_clean_url = final_id_string.strip() if final_id_string and final_id_string.strip() else (
            f"{v_id_fallback}?start={start_val}&end={end_val}" if v_id_fallback else re.sub(r'^https?://', '', orig_video_input).strip()
        )
        youtube_clean_url = re.sub(r'^https?://', '', youtube_clean_url).strip()

        # 1. Clean Text: separate text for GitHub saving vs TTS speaking
        save_text = re.sub(r'\[\s*\d+(?::\d{2}){1,2}\s*\]|\b\d{1,2}:\d{2}(?::\d{2})?\b', '', text).strip()
        save_text = re.sub(r'[\u200b\ufeff\u00ad]', '', save_text)
        save_text = re.sub(r'\s+', ' ', save_text).strip()

        speech_text = re.sub(r'\[[^\]]*\]|\([^)]*\)|（[^）]*）', '', save_text)
        speech_text = re.sub(r'[\U00010000-\U0010ffff]', '', speech_text)
        speech_text = re.sub(r'\s+', ' ', speech_text).strip()
        if not speech_text:
            speech_text = save_text

        # 2. Generate Thai TTS (vdoAI voiceover process: edge_tts th-TH-PremwadeeNeural with sentence boundaries)
        has_tts = False
        tts_start_offset = 0.1
        tts_speech_duration = 0.0
        total_audio_duration = 0.0

        if speech_text:
            set_bigdata_progress(15, "tts", "สร้างเสียงพากย์ TTS ภาษาไทย (vdoAI)...")
            print(f"[Bigdata Video] 🎙️ Generating TTS for: {speech_text[:50]}...")

            def _synthesize_edge_tts(target_text, out_mp3):
                import edge_tts
                target_text = re.sub(r'ยักษ์', 'ยัก', str(target_text or ''))
                async def _synth():
                    for voice in ('th-TH-PremwadeeNeural', 'th-TH-NiwatNeural'):
                        try:
                            comm = edge_tts.Communicate(target_text, voice)
                            audio_bytes = bytearray()
                            boundaries = []
                            async for ch in comm.stream():
                                if ch['type'] == 'audio':
                                    audio_bytes.extend(ch['data'])
                                elif ch['type'] == 'SentenceBoundary':
                                    boundaries.append(ch)

                            if audio_bytes:
                                with open(out_mp3, 'wb') as f:
                                    f.write(audio_bytes)
                                print(f"[Bigdata Video] 🎙️ TTS generated via voice {voice} ({len(audio_bytes)} bytes, {len(boundaries)} boundaries)")
                                return True, boundaries
                        except Exception as e:
                            print(f"[Bigdata Video] TTS {voice} attempt failed: {e}")
                    return False, []

                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    res, bounds = loop.run_until_complete(_synth())
                    loop.close()
                    return res, bounds
                except Exception as loop_err:
                    print(f"[Bigdata Video] TTS loop execution failed: {loop_err}")
                    return False, []

            has_tts, _ = _synthesize_edge_tts(speech_text, tts_audio)

        # Detect exact speech bounds (onset, real speech duration without trailing silence, total audio)
        if has_tts and os.path.exists(tts_audio):
            tts_start_offset, tts_speech_duration, total_audio_duration = detect_audio_speech_bounds(tts_audio)
        else:
            total_audio_duration = 6.0
            tts_start_offset = 0.20
            tts_speech_duration = 5.0

        print(f"[Bigdata Video] ⏱️ Accurate Timing: start_offset={tts_start_offset:.2f}s, speech_duration={tts_speech_duration:.2f}s, total_audio={total_audio_duration:.2f}s")

        # Ensure video duration covers both clip cut AND TTS audio
        req_span = end_val - start_val
        actual_span = max(15, req_span, int(math.ceil(total_audio_duration)) + 2)
        actual_end_val = start_val + actual_span
        section_arg = f"*{start_val}-{actual_end_val}"

        # 3. Use Cached Video or Download YouTube Video to cache
        v_id = extract_video_id(video_url) or f"clip_{int(time.time())}"
        clean_video_url = f"https://www.youtube.com/watch?v={v_id}" if (v_id and len(v_id) == 11) else video_url
        cached_video_file = os.path.join(VIDEO_CACHE_DIR, f"{v_id}.mp4")

        cookies_arg = []
        cookies_candidate = r"D:\Github\Youtube_Playlists_DL\cookies.txt"
        if os.path.exists(cookies_candidate):
            cookies_arg = ["--cookies", cookies_candidate]

        # Check if full video is already cached and valid (>100KB)
        has_cached_video = os.path.exists(cached_video_file) and os.path.getsize(cached_video_file) > 102400

        if not has_cached_video:
            set_bigdata_progress(25, "downloading", f"กำลังดาวน์โหลดวิดีโอจาก YouTube (เก็บแคชไว้ตัดต่อ <li> อื่นๆ)...")
            print(f"[Bigdata Video] 🎬 Downloading YouTube video to cache: {cached_video_file}")

            temp_cache_download = os.path.join(VIDEO_CACHE_DIR, f"temp_{v_id}_{int(time.time())}.mp4")
            ytdl_cmd = [
                sys.executable, "-m", "yt_dlp",
                "--extractor-args", "youtube:player_client=android,ios,web",
                "-f", "b[height<=480]/bv*[height<=480]+ba/b[height<=360]/b",
                "--merge-output-format", "mp4",
                *cookies_arg,
                "-o", temp_cache_download,
                clean_video_url
            ]
            proc = subprocess.run(ytdl_cmd, capture_output=True, text=True, timeout=180, startupinfo=hide_startupinfo, creationflags=creation_flags)
            if os.path.exists(temp_cache_download) and os.path.getsize(temp_cache_download) > 102400:
                try:
                    if os.path.exists(cached_video_file):
                        os.remove(cached_video_file)
                    shutil.move(temp_cache_download, cached_video_file)
                    has_cached_video = True
                    print(f"[Bigdata Video] ✅ Video cached successfully: {cached_video_file}")
                except Exception as me:
                    print(f"[Bigdata Video] Cache move error: {me}")
            else:
                # If full download timed out or failed, fallback to section download directly to raw_video
                print(f"[Bigdata Video] Fallback to section download for {section_arg}")
                fallback_cmd = [
                    sys.executable, "-m", "yt_dlp",
                    "--extractor-args", "youtube:player_client=android,ios,web",
                    "--download-sections", section_arg,
                    "-f", "b[height<=480]/bv*[height<=480]+ba/b[height<=360]/b",
                    "--merge-output-format", "mp4",
                    *cookies_arg,
                    "-o", raw_video,
                    clean_video_url
                ]
                proc_fallback = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=120, startupinfo=hide_startupinfo, creationflags=creation_flags)

        if has_cached_video:
            set_bigdata_progress(35, "downloading", f"ดึงวิดีโอจากแคชช่วง [{start_val}s-{actual_end_val}s] (ไม่ต้องโหลดใหม่ ⚡)...")
            print(f"[Bigdata Video] ⚡ Slicing directly from cached video ({start_val}s to {actual_end_val}s)...")
            slice_cmd = [
                "ffmpeg", "-y",
                "-ss", str(start_val),
                "-to", str(actual_end_val),
                "-i", cached_video_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24",
                "-c:a", "aac", "-b:a", "128k",
                "-avoid_negative_ts", "make_zero",
                raw_video
            ]
            proc_slice = subprocess.run(slice_cmd, capture_output=True, text=True, timeout=60, startupinfo=hide_startupinfo, creationflags=creation_flags)
            if not os.path.exists(raw_video) or os.path.getsize(raw_video) < 1000:
                print(f"[Bigdata Video] Slicing fallback to copy")
                slice_copy_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start_val),
                    "-to", str(actual_end_val),
                    "-i", cached_video_file,
                    "-c", "copy",
                    raw_video
                ]
                subprocess.run(slice_copy_cmd, capture_output=True, text=True, timeout=30, startupinfo=hide_startupinfo, creationflags=creation_flags)

        if not os.path.exists(raw_video):
            candidates = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.mp4')]
            if candidates:
                raw_video = candidates[0]
            else:
                raise RuntimeError(f"Could not produce raw clip from video ({video_url})")

        # 4. Detect Video Orientation & Dimensions (16:9 Landscape vs 9:16 Vertical Shorts)
        orig_w, orig_h = 640, 360
        try:
            probe_cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0",
                raw_video
            ]
            p_dim = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=10, startupinfo=hide_startupinfo, creationflags=creation_flags)
            out_dim = p_dim.stdout.strip()
            if 'x' in out_dim:
                pw, ph = out_dim.split('x')[:2]
                orig_w, orig_h = int(pw), int(ph)
        except Exception as e_dim:
            print(f"[Bigdata Video] Dimension probe failed: {e_dim}")

        is_vertical = orig_h > orig_w
        if is_vertical:
            target_w, target_h = 360, 640
        else:
            target_w, target_h = 640, 360

        print(f"[Bigdata Video] 📐 Detected format: {'Vertical (Shorts 9:16)' if is_vertical else 'Horizontal (16:9)'} ({orig_w}x{orig_h} -> {target_w}x{target_h})")

        # Generate Subtitles (vdoAI center pill badge style, synchronized to exact speech duration)
        set_bigdata_progress(60, "subtitles", "คำนวณซับไตเติลคาราโอเกะ (vdoAI Pill)...")
        ass_content = build_ass_center_live_tts(
            speech_text,
            start_offset=tts_start_offset,
            speech_duration=tts_speech_duration,
            target_w=target_w,
            target_h=target_h,
            is_vertical=is_vertical
        )
        with open(ass_file, 'w', encoding='utf-8') as f:
            f.write(ass_content)

        # 5. FFmpeg Cutting, Subtitle Burning, and Audio Ducking
        set_bigdata_progress(75, "rendering", "ตัดต่อ & ฝังซับไตเติลและผสมเสียง...")
        esc_colon = r"\:"
        escaped_ass = os.path.abspath(ass_file).replace('\\', '/').replace(':', esc_colon)
        vdoai_fonts = r"D:\Github\vdoAI\fonts".replace('\\', '/').replace(':', esc_colon)
        fonts_dir_param = f":fontsdir='{vdoai_fonts}'" if os.path.exists(r"D:\Github\vdoAI\fonts") else ""
        subtitles_filter = f"subtitles=filename='{escaped_ass}'{fonts_dir_param}"

        scale_param = f"scale={target_w}:{target_h}"
        target_video = raw_video

        if has_tts and os.path.exists(tts_audio):
            duck_expr = f"volume='if(lt(t,{total_audio_duration + 0.3}),0.15,1.0)':eval=frame"
            filter_complex = (
                f"[0:v]{scale_param},{subtitles_filter}[vsub];"
                f"[0:a]{duck_expr},aresample=async=1000[ducked];"
                f"[1:a]volume=2.2,aresample=async=1000[tts];"
                f"[ducked][tts]amix=inputs=2:duration=first:dropout_transition=0.1:normalize=0[aout]"
            )
            merge_cmd = [
                "ffmpeg", "-y",
                "-i", raw_video,
                "-i", tts_audio,
                "-filter_complex", filter_complex,
                "-map", "[vsub]",
                "-map", "[aout]",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-crf", "26",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                final_video
            ]
            res_merge = subprocess.run(merge_cmd, capture_output=True, text=True, timeout=90, startupinfo=hide_startupinfo, creationflags=creation_flags)
            if res_merge.returncode == 0 and os.path.exists(final_video) and os.path.getsize(final_video) > 100:
                target_video = final_video
            else:
                filter_complex_no_a = f"[0:v]{scale_param},{subtitles_filter}[vsub]"
                merge_cmd2 = [
                    "ffmpeg", "-y",
                    "-i", raw_video,
                    "-i", tts_audio,
                    "-filter_complex", filter_complex_no_a,
                    "-map", "[vsub]",
                    "-map", "1:a:0",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-tune", "fastdecode",
                    "-crf", "26",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-shortest",
                    "-movflags", "+faststart",
                    final_video
                ]
                res_merge2 = subprocess.run(merge_cmd2, capture_output=True, text=True, timeout=90, startupinfo=hide_startupinfo, creationflags=creation_flags)
                if res_merge2.returncode == 0 and os.path.exists(final_video) and os.path.getsize(final_video) > 100:
                    target_video = final_video
        else:
            filter_complex_sub = f"[0:v]{scale_param},{subtitles_filter}[vsub]"
            merge_cmd3 = [
                "ffmpeg", "-y",
                "-i", raw_video,
                "-filter_complex", filter_complex_sub,
                "-map", "[vsub]",
                "-map", "0:a?",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "fastdecode",
                "-crf", "26",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                final_video
            ]
            res_merge3 = subprocess.run(merge_cmd3, capture_output=True, text=True, timeout=90, startupinfo=hide_startupinfo, creationflags=creation_flags)
            if res_merge3.returncode == 0 and os.path.exists(final_video) and os.path.getsize(final_video) > 100:
                target_video = final_video

        # 6. Copy to Desktop if requested
        desktop_dest = None
        if copy_to_desktop:
            set_bigdata_progress(88, "desktop", "บันทึกไฟล์วิดีโอลง Desktop...")
            safe_text = re.sub(r'[\\/*?:"<>|]', '', save_text[:25]).strip()
            dest_name = f"clip_{safe_text}_{int(time.time())}.mp4" if safe_text else f"clip_{start_val}_{actual_end_val}_{int(time.time())}.mp4"
            desktop_dest = os.path.join(DESKTOP_PATH, dest_name)
            shutil.copy2(target_video, desktop_dest)
            print(f"[Bigdata Video] 🖥️ Successfully saved video to Desktop: {desktop_dest}")

        # 7. Upload to Catbox with userhash API key (Primary: ระบบหนึ่ง)
        set_bigdata_progress(92, "uploading", "อัปโหลดขึ้น Catbox.moe (API key)...")
        catbox_userhash = "6d72cf40b5ef56e27239aed64"
        raw_res = ""
        catbox_url = None

        def verify_catbox_upload(test_url):
            if not test_url or "catbox.moe" not in test_url:
                return False
            try:
                # Use GET with byte-range 0-2048 to probe file headers and data.
                # Note: Catbox Nginx returns "Content-Length: 0" on HEAD requests (-sI),
                # so we must use a GET range request (-r 0-2048) to accurately verify.
                probe_cmd = ["curl.exe", "-s", "-i", "--max-time", "15", "-r", "0-2048", "-L", test_url]
                c_res = subprocess.run(probe_cmd, capture_output=True, timeout=20, startupinfo=hide_startupinfo, creationflags=creation_flags)
                raw_out = c_res.stdout
                if not raw_out:
                    print(f"[Bigdata Catbox] ⚠️ Empty response from curl probe")
                    return False

                header_sep = b"\r\n\r\n" if b"\r\n\r\n" in raw_out else (b"\n\n" if b"\n\n" in raw_out else None)
                if header_sep:
                    parts = raw_out.split(header_sep)
                    header_out = parts[-2].decode("utf-8", errors="ignore")
                    body_bytes = parts[-1]
                else:
                    header_out = raw_out.decode("utf-8", errors="ignore")
                    body_bytes = b""

                # Check HTTP status code
                status_matches = re.findall(r'HTTP/[\d\.]+\s+(\d+)', header_out)
                last_status = int(status_matches[-1]) if status_matches else 0
                if last_status not in (200, 206):
                    print(f"[Bigdata Catbox] ⚠️ HTTP status error: {last_status}")
                    return False

                # Catbox returns "Content-Range: bytes 0-2048/<total_bytes>" on 206 responses
                cr_m = re.search(r'Content-Range:\s*bytes\s+\d+-\d+/(\d+)', header_out, re.IGNORECASE)
                if cr_m:
                    total_bytes = int(cr_m.group(1))
                    if total_bytes < 1000:
                        print(f"[Bigdata Catbox] ⚠️ Catbox file suspiciously small: {total_bytes} bytes")
                        return False
                    print(f"[Bigdata Catbox] ✅ Verified Catbox video size: {total_bytes} bytes (HTTP {last_status})")
                    return True

                # If server returned 200/206 with actual payload data (> 500 bytes for video)
                if len(body_bytes) > 500:
                    print(f"[Bigdata Catbox] ✅ Verified Catbox body payload: {len(body_bytes)} bytes received (HTTP {last_status})")
                    return True

                # If Content-Length header is provided in GET response
                cl_m = re.search(r'Content-Length:\s*(\d+)', header_out, re.IGNORECASE)
                if cl_m and int(cl_m.group(1)) > 1000:
                    print(f"[Bigdata Catbox] ✅ Verified Catbox Content-Length: {cl_m.group(1)} bytes")
                    return True

                print(f"[Bigdata Catbox] ⚠️ Catbox verification failed (received only {len(body_bytes)} bytes, status {last_status})")
                return False
            except Exception as e:
                print(f"[Bigdata Catbox] Verification exception: {e}")
                return False

        for attempt in range(1, 4):
            try:
                cmd = [
                    "curl.exe", "--max-time", "90", "-s",
                    "-F", "reqtype=fileupload",
                    "-F", f"userhash={catbox_userhash}",
                    "-F", f"fileToUpload=@{target_video}",
                    "https://catbox.moe/user/api.php"
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=100, startupinfo=hide_startupinfo, creationflags=creation_flags)
                raw_res = proc.stdout.strip()
                if "catbox.moe" in raw_res:
                    if verify_catbox_upload(raw_res):
                        catbox_url = raw_res
                        print(f"[Bigdata Video] ☁️ Uploaded and verified Catbox: {catbox_url}")
                        break
                    else:
                        print(f"[Bigdata Video] Catbox gave URL {raw_res} but verification failed (corrupt/empty 0-byte file)")
                else:
                    print(f"[Bigdata Video] Catbox attempt {attempt} failed: {raw_res[:100]} | stderr: {proc.stderr[:100]}")
                time.sleep(1)
            except Exception as up_err:
                print(f"[Bigdata Video] Catbox upload error attempt {attempt}: {up_err}")
                time.sleep(1)

        target_save_url = None
        is_fallback_youtube = False

        if catbox_url:
            target_save_url = re.sub(r'^https?://', '', catbox_url).strip()
            print(f"[Bigdata Video] 🎯 Primary System: Catbox video uploaded & verified: {target_save_url}")
        else:
            is_fallback_youtube = True
            target_save_url = youtube_clean_url
            print(f"[Bigdata Video] ⚠️ Catbox ขัดข้อง/ไฟล์ว่าง 0-byte → สลับใช้ระบบสอง บันทึก YouTube URL สำรอง: {target_save_url}")
            show_tray_notification("Bigdata: ระบบสอง YouTube URL", f"Catbox ขัดข้อง → บันทึก YouTube URL สำรองลง GitHub เรียบร้อย 🐙")

        # 8. Direct GitHub update (guaranteed to complete even if Gemini tab is closed!)
        github_res = None
        set_bigdata_progress(96, "github", "กำลังบันทึกลง GitHub (bigdata)...")
        try:
            github_res = update_github_reel(save_text, target_save_url, github_config)
            print(f"[Bigdata Video] 🐙 GitHub updated successfully: {github_res}")
        except Exception as ge:
            print(f"[Bigdata Video] ⚠️ GitHub update error: {ge}")

        result_data = {
            "success": True,
            "url": target_save_url,
            "fullUrl": catbox_url if catbox_url else (f"https://www.youtube.com/watch?v={target_save_url}" if not target_save_url.startswith('http') else target_save_url),
            "desktopPath": desktop_dest,
            "hasTts": has_tts,
            "isFallback": is_fallback_youtube,
            "github": github_res
        }
        msg_done = "เสร็จสมบูรณ์! (ระบบสอง: YouTube URL)" if is_fallback_youtube else "ประมวลผลและบันทึกเสร็จสมบูรณ์ 100%!"
        set_bigdata_progress(100, "done", msg_done, result=result_data)
        print(f"[Bigdata Video] ✅ Processing success: {target_save_url}")
        return result_data

    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

        # Cleanup cached video only if Gemini tab was closed AND no more tasks are waiting
        try:
            if v_id:
                with video_lock:
                    if v_id in cached_video_ref_counts:
                        cached_video_ref_counts[v_id] -= 1
                    ref_count = cached_video_ref_counts.get(v_id, 0)
                    if v_id in pending_cleanup_videos and ref_count <= 0:
                        c_file = os.path.join(VIDEO_CACHE_DIR, f"{v_id}.mp4")
                        if os.path.exists(c_file):
                            try:
                                os.remove(c_file)
                                print(f"[Bigdata Cache] 🧹 Deleted cached video {v_id} (Gemini tab was closed and all tasks completed)")
                            except Exception as ce:
                                print(f"[Bigdata Cache] Error removing {c_file}: {ce}")
                        pending_cleanup_videos.discard(v_id)
        except Exception as cle:
            print(f"[Bigdata Cache] Refcount cleanup error: {cle}")
# --- SERVER LOGIC ---
class HubHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        
        if self.path == '/favicon.ico':
            self.send_response(404)
            self.end_headers()
            return

        if parsed_url.path == '/bigdata-progress':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(bigdata_job_progress).encode('utf-8'))
            return

        if parsed_url.path == '/wait-for-export':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            # จอดรอตรงนี้จนกว่าจะมีสัญญาณ (Timeout 60s เพื่อความปลอดภัย)
            was_set = export_event.wait(timeout=60)
            if was_set:
                export_event.clear()
                self.wfile.write(json.dumps({"status": "updated", "path": last_exported_path}).encode())
            else:
                self.wfile.write(json.dumps({"status": "timeout", "path": last_exported_path}).encode())
            return

        if parsed_url.path == '/wait-for-ps-trigger':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            was_set = ps_trigger_event.wait(timeout=60)
            if was_set:
                ps_trigger_event.clear()
                resp = {"status": "triggered"}
                resp.update(ps_trigger_data)
                self.wfile.write(json.dumps(resp).encode())
            else:
                self.wfile.write(json.dumps({"status": "timeout"}).encode())
            return

        if parsed_url.path == '/list-downloads':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            files = []
            try:
                all_files = os.listdir(DOWNLOADS_PATH)
                all_files.sort(key=lambda x: os.path.getmtime(os.path.join(DOWNLOADS_PATH, x)), reverse=True)
                for f in all_files:
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        full_path = os.path.join(DOWNLOADS_PATH, f)
                        files.append({
                            "filename": full_path,
                            "shortname": f,
                            "mtime": os.path.getmtime(full_path)
                        })
                # Also include Desktop complete image if exists (.png, .jpg, .jpeg, .webp)
                for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                    desktop_complete = os.path.join(DESKTOP_PATH, f"complete{ext}")
                    if os.path.exists(desktop_complete):
                        already = any(f['filename'] == desktop_complete for f in files)
                        if not already:
                            files.append({
                                "filename": desktop_complete,
                                "shortname": f"📍 complete{ext} (Desktop)",
                                "mtime": os.path.getmtime(desktop_complete)
                            })
                self.wfile.write(json.dumps(files[:12]).encode())
            except:
                self.wfile.write(json.dumps([]).encode())
            return

        if parsed_url.path == '/get-img':
            query = parse_qs(parsed_url.query)
            file_path = query.get('path', [None])[0]
            if file_path:
                file_path = file_path.replace('/', os.sep).replace('\\', os.sep)
                if not os.path.exists(file_path):
                    base = os.path.basename(file_path)
                    candidates = [
                        os.path.join(DOWNLOADS_PATH, base),
                        os.path.join(DESKTOP_PATH, base),
                        os.path.join(BACKUP_DIR, base),
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), base)
                    ]
                    for c in candidates:
                        if os.path.exists(c):
                            file_path = c
                            break
            if file_path and os.path.exists(file_path):
                self.send_response(200)
                ext = file_path.lower().split('.')[-1]
                content_type = 'image/webp' if ext == 'webp' else ('image/png' if ext == 'png' else 'image/jpeg')
                self.send_header('Content-type', content_type)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
            return

        if parsed_url.path == '/open-backup-folder':
            if os.path.exists(BACKUP_DIR):
                try:
                    os.startfile(BACKUP_DIR)
                except Exception as e:
                    print(f"[Watcher] Could not open backup folder: {e}")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "path": BACKUP_DIR}).encode())
            return

        if parsed_url.path == '/delete-file':
            query = parse_qs(parsed_url.query)
            file_path = query.get('path', [None])[0]
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                except:
                    self.send_response(500)
                    self.end_headers()
            return

        if parsed_url.path == '/set-mode':
            global current_mode
            query = parse_qs(parsed_url.query)
            mode = query.get('mode', ['hub'])[0]
            current_mode = mode
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"mode": current_mode}).encode())
            return

        if parsed_url.path == '/heartbeat':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "alive"}).encode())
            return

        if parsed_url.path == '/trigger-admin-payment':
            open_admin_payment_in_chrome()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            return

        if parsed_url.path == '/upscale-progress':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                import cloudinary_upscaler
                self.wfile.write(json.dumps(cloudinary_upscaler.get_upscale_progress()).encode())
            except Exception:
                import upscale_engine
                self.wfile.write(json.dumps(upscale_engine.get_upscale_progress()).encode())
            return

        if parsed_url.path == '/upscale-quota':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                import cloudinary_upscaler
                query_params = parse_qs(parsed_url.query)
                force_refresh = 'refresh' in query_params
                self.wfile.write(json.dumps(cloudinary_upscaler.get_accounts_quota(force_refresh=force_refresh)).encode())
            except Exception as e:
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return

        return super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == '/edge-tts':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(post_data.decode('utf-8'))
                text = re.sub(r'[\u200b\ufeff\u00ad]', '', str(data.get('text', '')))
                text = text.replace('ยักษ์', 'ยัก')
                text = re.sub(r'\s+', ' ', text).strip()
                if not text:
                    raise ValueError('Missing text')
                # Keep requests bounded: this endpoint is for one Gemini <li>.
                if len(text) > 5000:
                    raise ValueError('Text is too long for live TTS')

                async def synthesize(part, voice):
                    import edge_tts
                    communicate = edge_tts.Communicate(part, voice, rate='+0%')
                    audio_parts, raw_bounds = [], []
                    async for chunk in communicate.stream():
                        if chunk['type'] == 'audio':
                            audio_parts.append(chunk['data'])
                        elif chunk['type'] in ('WordBoundary', 'SentenceBoundary'):
                            start = chunk['offset'] / 10000000.0
                            dur = chunk.get('duration', 0) / 10000000.0
                            raw_bounds.append({
                                'text': chunk.get('text', ''),
                                'startSec': start,
                                'endSec': start + dur
                            })
                    return b''.join(audio_parts), raw_bounds

                voices = ('th-TH-PremwadeeNeural', 'th-TH-NiwatNeural')
                audio = b''
                raw_boundaries = []
                last_error = None
                for voice in voices:
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            audio, raw_boundaries = loop.run_until_complete(synthesize(text, voice))
                            if audio:
                                break
                        finally:
                            loop.close()
                    except Exception as voice_error:
                        last_error = voice_error
                        print(f'[Watcher] Edge TTS {voice} failed: {voice_error}')

                if not audio:
                    raise RuntimeError(f'Edge TTS returned no audio: {last_error or "unknown error"}')

                payload = {
                    'success': True,
                    'audioBase64': base64.b64encode(audio).decode('ascii'),
                    'wordBoundaries': []
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode('utf-8'))
            except Exception as e:
                print(f'[Watcher] Edge TTS error: {e}')
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            return

        if parsed_url.path == '/trigger-ps':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                global ps_trigger_data
                ps_trigger_data = data
                ps_trigger_event.set()
                print(f"[Watcher] 📥 Received Photoshop Trigger: {data.get('prompt', '')[:40]}")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": True}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        if parsed_url.path == '/trigger-admin-payment':
            open_admin_payment_in_chrome()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode())
            return

        if parsed_url.path == '/save-image':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                img_data = data.get('dataUrl')
                target = data.get('path')
                if img_data and ',' in img_data and target:
                    header, encoded = img_data.split(',', 1)
                    binary_data = base64.b64decode(encoded)

                    # ถ้าบันทึก complete.png (ไม่ใช่ complete_bot.png) ให้ backup ไฟล์เดิมก่อนเขียนทับ
                    is_complete_png = (os.path.basename(target).lower() == 'complete.png') and ('bot' not in target.lower())
                    if is_complete_png:
                        backup_desktop_files(incoming_data=binary_data)

                    with open(target, 'wb') as f:
                        f.write(binary_data)

                    if data.get('openPhotoshop'):
                        import subprocess
                        ps_path = r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe"
                        if os.path.exists(ps_path):
                            subprocess.Popen([ps_path, target])
                        else:
                            try:
                                os.startfile(target)
                            except:
                                pass

                    # ถ้าบันทึก complete.png (ไม่ใช่ complete_bot.png) ให้สร้าง example.png บน Desktop ด้วย
                    is_complete_png = (os.path.basename(target).lower() == 'complete.png') and ('bot' not in target.lower())
                    if is_complete_png:
                        try:
                            from watermark_engine import create_anti_ai_watermark
                            from PIL import Image
                            import io
                            raw_img = Image.open(io.BytesIO(binary_data))
                            example_img = create_anti_ai_watermark(raw_img)
                            example_path = os.path.join(DESKTOP_PATH, 'example.png')
                            example_img.save(example_path, format='PNG')
                            print(f"[Watcher] Auto-generated example.png on Desktop")
                        except Exception as we:
                            print(f"[Watcher] Watermark generation error: {we}")

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "path": target}).encode())
                else:
                    self.send_response(400)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
            except Exception as e:
                self.send_response(500)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
            return

        if parsed_url.path == '/process-bigdata-video':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(post_data.decode('utf-8'))
                video_url = data.get('videoUrl', '').strip()
                start_sec = data.get('start', 0)
                end_sec = data.get('end', None)
                text = data.get('text', '').strip()
                copy_to_desktop = bool(data.get('copyToDesktop', False))
                github_config = data.get('github')
                final_id_string = data.get('finalIdString', '').strip()

                if not video_url:
                    raise ValueError('Missing videoUrl')

                v_id = extract_video_id(video_url)
                if v_id:
                    with video_lock:
                        cached_video_ref_counts[v_id] = cached_video_ref_counts.get(v_id, 0) + 1
                        pending_cleanup_videos.discard(v_id)

                if github_config and isinstance(github_config, dict) and github_config.get('token'):
                    cached_github_config.update(github_config)

                # Queue task immediately for background processing
                bigdata_task_queue.put((video_url, start_sec, end_sec, text, copy_to_desktop, github_config, final_id_string))
                q_len = bigdata_task_queue.qsize()
                set_bigdata_progress(10, "queued", f"คิวงานตัดต่อวิดีโอเรียบร้อย (คิวที่ {q_len}) เริ่มทำงานพื้นหลัง...")

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'status': 'started', 'queue_size': q_len}).encode('utf-8'))
            except Exception as e:
                print(f"[Watcher] /process-bigdata-video error: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            return

        if parsed_url.path == '/cleanup-bigdata-cache':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(post_data.decode('utf-8'))
                clean_all = bool(data.get('cleanAll', False))
                video_url = data.get('videoUrl', '')
                video_id = data.get('videoId') or extract_video_id(video_url)
                if clean_all:
                    cleanup_video_cache(clean_all=True)
                elif video_id:
                    cleanup_video_cache(video_id=video_id)
                else:
                    cleanup_video_cache(clean_all=True)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            return

        if parsed_url.path == '/update-example-qr':
            content_length = int(self.headers.get('Content-Length', 0))
            try:
                data = json.loads(self.rfile.read(content_length) or b'{}')
                from watermark_engine import save_qr_amount, create_anti_ai_watermark

                amount = save_qr_amount(data.get('amount'))
                complete_path = os.path.join(DESKTOP_PATH, 'complete.png')
                example_path = os.path.join(DESKTOP_PATH, 'example.png')
                if not os.path.exists(complete_path):
                    raise FileNotFoundError('ยังไม่พบ Desktop/complete.png')

                from PIL import Image
                with Image.open(complete_path) as complete_img:
                    example_img = create_anti_ai_watermark(complete_img, qr_amount=amount)
                    example_img.save(example_path, format='PNG')

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'amount': amount, 'path': example_path}).encode())
            except Exception as e:
                print(f'[Watcher] QR amount update error: {e}')
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode())
            return

        if parsed_url.path == '/mark-points':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data)
                img_url = data.get('url')
                img_data = data.get('dataUrl')
                
                script_dir = os.path.dirname(os.path.abspath(__file__))
                temp_filename = "temp_mark.jpg"
                temp_path = os.path.join(script_dir, temp_filename)
                
                # Remove old file if exists
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                
                download_success = False
                if img_url:
                    try:
                        req = urllib.request.Request(
                            img_url, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        )
                        with urllib.request.urlopen(req, timeout=15) as response:
                            with open(temp_path, 'wb') as f:
                                f.write(response.read())
                        download_success = True
                    except Exception as download_err:
                        print(f"[Watcher] Error downloading image URL: {download_err}")
                
                if not download_success and img_data and ',' in img_data:
                    try:
                        header, encoded = img_data.split(',', 1)
                        binary_data = base64.b64decode(encoded)
                        with open(temp_path, 'wb') as f:
                            f.write(binary_data)
                        download_success = True
                    except Exception as base64_err:
                        print(f"[Watcher] Error parsing base64 image data: {base64_err}")
                
                if download_success and os.path.exists(temp_path):
                    import subprocess
                    ps_script = os.path.join(script_dir, "MarkPoints.ps1")
                    # Run MarkPoints.ps1 asynchronously
                    cmd = f'powershell -ExecutionPolicy Bypass -File "{ps_script}" "{temp_path}"'
                    subprocess.Popen(cmd, shell=True)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "message": "MarkPoints triggered successfully."}).encode())
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": "Failed to obtain image."}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
            return

        if parsed_url.path in ('/upscale', '/ai-transform'):
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            try:
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                target_path = data.get('path')

                # 🚫 ป้องกันเด็ดขาด: ห้ามยุ่งกับไฟล์ complete_bot.png หรือระบบ Facebook_Bot
                if target_path and ('complete_bot' in os.path.basename(target_path).lower() or 'bot' in os.path.basename(target_path).lower()):
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "ไม่อนุญาตให้ประมวลผลไฟล์ complete_bot.png (Facebook_Bot ไม่ใช้ระบบนี้)"
                    }).encode())
                    return

                if not target_path or not os.path.exists(target_path) or 'complete_bot' in os.path.basename(target_path).lower():
                    target_path = os.path.join(DESKTOP_PATH, 'complete.png')

                # ★ Auto backup complete.png & example.png ก่อนถูกเขียนทับ
                if 'complete_bot' not in os.path.basename(target_path).lower():
                    backup_desktop_files()

                scale = int(data.get('scale', 2))
                model_name = data.get('model', 'cloudinary_upscale_enhancer')
                mode = data.get('mode')
                options = data.get('options', {})
                
                print(f"[Watcher] 🔍 AI request received for {target_path} (model={model_name}, mode={mode}, scale={scale}x, options={options})")
                import cloudinary_upscaler
                import importlib
                importlib.reload(cloudinary_upscaler)
                result = cloudinary_upscaler.upscale_image(image_path=target_path, scale=scale, model_name=model_name, mode=mode, options=options)
                
                # Signal frontend that export updated
                global last_exported_path
                last_exported_path = target_path
                export_event.set()

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                print(f"[Watcher] ❌ Upscale error: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode())
            return

        if parsed_url.path == '/binance-square-post':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b'{}'
            v_id = None
            try:
                import sys
                import importlib
                bs_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "binance-square")
                if bs_folder not in sys.path:
                    sys.path.insert(0, bs_folder)
                import binance_square_bot
                importlib.reload(binance_square_bot)
                data = json.loads(post_data.decode('utf-8')) if post_data else {}
                video_url = data.get('videoUrl', '')
                v_id = extract_video_id(video_url)

                if v_id:
                    with video_lock:
                        cached_video_ref_counts[v_id] = cached_video_ref_counts.get(v_id, 0) + 1
                        pending_cleanup_videos.discard(v_id)

                self.send_response(200)
                self.send_header('Content-type', 'application/x-ndjson')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()

                def send_line(obj):
                    try:
                        line = json.dumps(obj) + "\n"
                        self.wfile.write(line.encode('utf-8'))
                        self.wfile.flush()
                    except Exception:
                        pass

                # Sequential FIFO Queue registration
                global binance_queue_count
                with binance_count_lock:
                    binance_queue_count += 1
                    current_q_pos = binance_queue_count

                if current_q_pos > 1:
                    wait_msg = f"รอคิวงานที่ {current_q_pos} (กำลังรอคิวก่อนหน้าเสร็จ)..."
                    send_line({"type": "progress", "percent": 5, "stage": wait_msg})
                    write_status_file(5, "queued", f"🔶 Binance Square: รอคิวที่ {current_q_pos}", task_type="binance", queue_size=binance_queue_count)
                    update_tray_status(5, "queued", f"Binance Square คิวที่ {current_q_pos}")
                    print(f"[Watcher] ⏳ Binance Square job queued at position {current_q_pos}")

                # Sequential Execution: Only ONE video processing/downloading job runs across the entire system!
                with video_pipeline_lock:
                    with binance_count_lock:
                        binance_queue_count = max(0, binance_queue_count - 1)
                        remaining_q = binance_queue_count

                    write_status_file(10, "starting", "🔶 เริ่มประมวลผลคลิป Binance Square...", task_type="binance", queue_size=remaining_q)

                    def progress_cb(pct, stage):
                        send_line({"type": "progress", "percent": pct, "stage": stage})
                        write_status_file(pct, "working", f"🔶 Binance Square: {stage}", task_type="binance", queue_size=remaining_q)
                        update_tray_status(pct, "rendering", f"Binance Square: {stage}")

                    result = binance_square_bot.process_clip_and_post(data, progress_callback=progress_cb)
                    write_status_file(100, "done", "🔶 โพสต์ Binance Square สำเร็จ 100%!", task_type="binance", queue_size=remaining_q)
                    send_line({"type": "complete", "success": True, **result})
                    # show_tray_notification("Binance Square สำเร็จ!", "โพสต์คลิปขึ้น Binance Square เรียบร้อย 🔶")
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"[Watcher] ❌ Binance Square error: {e}\n{tb}")
                try:
                    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "binance_err.log"), "w", encoding="utf-8") as ef:
                        ef.write(tb)
                except:
                    pass
                err_line = {"type": "error", "success": False, "error": str(e)}
                write_status_file(0, "error", f"❌ เกิดข้อผิดพลาด Binance Square: {str(e)[:60]}", task_type="binance")
                try:
                    self.wfile.write((json.dumps(err_line) + "\n").encode('utf-8'))
                    self.wfile.flush()
                except:
                    pass
            finally:
                if v_id:
                    with video_lock:
                        if v_id in cached_video_ref_counts:
                            cached_video_ref_counts[v_id] -= 1
                        ref_count = cached_video_ref_counts.get(v_id, 0)
                        if v_id in pending_cleanup_videos and ref_count <= 0:
                            c_file = os.path.join(VIDEO_CACHE_DIR, f"{v_id}.mp4")
                            if os.path.exists(c_file):
                                try:
                                    os.remove(c_file)
                                    print(f"[Bigdata Cache] 🧹 Deleted cached video {v_id} (Binance Square finished and Gemini closed)")
                                except Exception as ce:
                                    pass
                            pending_cleanup_videos.discard(v_id)
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        pass

# --- AUTO OPEN ADMIN PAYMENT IN CHROME ---
def open_admin_payment_in_chrome():
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    admin_html = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin-payment.html")
    for cp in chrome_paths:
        if os.path.exists(cp):
            try:
                subprocess.Popen([cp, admin_html])
                return
            except Exception:
                pass
    try:
        os.system(f'start chrome "{admin_html}"')
    except Exception:
        pass

def handle_kbank_deposit_received(amount=None):
    """
    เมื่อได้รับแจ้งเตือนเงินเข้าจาก KBank Live (LINE PC หรือ K PLUS):
    - แบบระบุยอดเงิน (amount is not None): ตรวจสอบยอดตรงกับ pending request -> อนุมัติทันที
    - แบบไม่ระบุยอดเงิน (LINE "แจ้งเตือนเงินเข้า" - Option B):
        - ถ้ามีคิวรอ (pending) แค่ 1 รายการ -> อนุมัติคิวนั้นทันที!
        - ถ้ามีคิวรอมากกว่า 1 รายการ -> ป้องกันความผิดพลาด โดยเปิด admin-payment.html ให้แอดมินตรวจและกดเอง
        - ถ้าไม่มีคิวรอเลย -> ข้าม (อาจเป็นเงินส่วนตัวโอนเข้า)
    """
    firebase_url = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/payment_requests.json"
    try:
        req = urllib.request.Request(f"{firebase_url}?t={int(time.time()*1000)}", headers={"User-Agent": "PaymentWatcher/1.0"})
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode('utf-8'))
        
        if not data or not isinstance(data, dict):
            if amount is not None:
                print(f"[KBank AutoPay] ℹ️ Received deposit of {amount:.2f} THB, but no payment requests found in Firebase.")
            else:
                print(f"[KBank AutoPay] ℹ️ Received 'แจ้งเตือนเงินเข้า', but no payment requests found in Firebase.")
            return

        # กรองรายการที่สถานะเป็น pending ทั้งหมด
        pending_items = []
        for k, v in data.items():
            if isinstance(v, dict) and v.get('status') == 'pending':
                pending_items.append((k, v))

        matched_key = None
        matched_price = 0.0

        if amount is not None and amount > 0:
            # กรณีที่ 1: รู้ยอดเงินชัดเจน (เช่น K PLUS / Phone Link) -> ค้นหาคำขอที่ยอดตรงกัน
            for k, v in pending_items:
                try:
                    req_price = float(v.get('price', 0))
                    if abs(req_price - amount) < 0.05:
                        matched_key = k
                        matched_price = req_price
                        break
                except Exception:
                    continue
        else:
            # กรณีที่ 2 (Option B): LINE ส่งมาแค่ "แจ้งเตือนเงินเข้า" ไม่มียอดเงิน
            if len(pending_items) == 1:
                # มีคิวเดียวที่กำลังรออยู่ อนุมัติให้อัตโนมัติทันที
                matched_key = pending_items[0][0]
                try:
                    matched_price = float(pending_items[0][1].get('price', 0))
                except Exception:
                    matched_price = 0.0
                print(f"[KBank AutoPay] 🎯 Single pending queue detected ({matched_key}, {matched_price:.2f} THB). Auto-approving upon LINE 'แจ้งเตือนเงินเข้า' alert!")
            elif len(pending_items) > 1:
                print(f"[KBank AutoPay] ⚠️ Alert 'แจ้งเตือนเงินเข้า' received but {len(pending_items)} orders are pending simultaneously. Opening admin dashboard for manual safety confirmation.")
                open_admin_payment_in_chrome()
                try:
                    import winsound
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                except Exception:
                    pass
                return
            else:
                print(f"[KBank AutoPay] ℹ️ Alert 'แจ้งเตือนเงินเข้า' received, but 0 pending orders found in Firebase.")
                return

        if matched_key:
            print(f"[KBank AutoPay] 🎯 MATCH FOUND! Order {matched_key} (Amount: {matched_price:.2f} THB). Approving now...")
            
            # 1. ส่ง PATCH ปรับสถานะเป็น approved ทันที
            final_paid_amount = amount if (amount is not None and amount > 0) else matched_price
            patch_url = f"https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/payment_requests/{matched_key}.json"
            patch_data = json.dumps({
                "status": "approved",
                "approvedAt": int(time.time() * 1000),
                "autoApproved": True,
                "paidAmount": final_paid_amount
            }).encode('utf-8')
            
            patch_req = urllib.request.Request(patch_url, data=patch_data, method='PATCH', headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(patch_req, timeout=5) as patch_res:
                pass
            
            print(f"[KBank AutoPay] 🚀 AUTO-APPROVED successfully for Order {matched_key}! Client download is now unlocked.")
            
            # ส่งเสียงแจ้งเตือนสั้นๆ บน Windows
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass

            # บันทึกสถานะ approved ค้างไว้ใน Firebase เพื่อให้ลูกค้าสามารถเปิดลิงก์ดาวน์โหลดได้ตลอดอายุลิงก์
        else:
            if amount is not None:
                print(f"[KBank AutoPay] ℹ️ Received deposit of {amount:.2f} THB, but no matching pending request found.")

    except Exception as e:
        print(f"[KBank AutoPay] ⚠️ Error handling deposit: {e}")

def start_kbank_notification_listener():
    """เฝ้าตรวจจับ Notification จาก KBank Live (LINE PC / K PLUS) แบบ Realtime ตลอดเวลา"""
    def listener_thread():
        ps_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kbank_listener.ps1")
        if not os.path.exists(ps_script):
            print(f"[KBank AutoPay] ⚠️ kbank_listener.ps1 not found at {ps_script}")
            return

        cmd = ["powershell", "-WindowStyle", "Hidden", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps_script]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0x08000000
        
        while True:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    encoding='utf-8',
                    bufsize=1,
                    creationflags=creationflags,
                    startupinfo=startupinfo
                )
                
                print("[KBank AutoPay] 🛡️ KBank Live Notification Listener started successfully.")
                
                for line in iter(proc.stdout.readline, ''):
                    line = line.strip()
                    if line.startswith("EVENT:"):
                        try:
                            data = json.loads(line[6:])
                            if data.get('event') == 'kbank_deposit':
                                amt_raw = data.get('amount')
                                amt = float(amt_raw) if amt_raw is not None else None
                                if amt is not None:
                                    print(f"[KBank AutoPay] 💸 Bank deposit alert detected: {amt:.2f} THB from {data.get('app', 'LINE')}")
                                else:
                                    print(f"[KBank AutoPay] 🔔 Bank deposit alert detected (No amount in notification) from {data.get('app', 'LINE')}")
                                threading.Thread(target=handle_kbank_deposit_received, args=(amt,), daemon=True).start()
                        except Exception as err:
                            print(f"[KBank AutoPay] Error parsing notification event: {err}")
                
                proc.wait()
            except Exception as e:
                print(f"[KBank AutoPay] Listener process error: {e}")
            time.sleep(3)

    t = threading.Thread(target=listener_thread, daemon=True)
    t.start()

_opened_payment_keys = set()

def start_payment_requests_watcher():
    """Monitor Firebase RTDB for pending customer payment triggers and auto-open Chrome"""
    def watcher_loop():
        global _opened_payment_keys
        firebase_url = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/payment_requests.json"
        
        while True:
            try:
                req = urllib.request.Request(f"{firebase_url}?t={int(time.time()*1000)}", headers={"User-Agent": "PaymentWatcher/1.0"})
                with urllib.request.urlopen(req, timeout=5) as res:
                    data = json.loads(res.read().decode('utf-8'))
                    if data and isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, dict) and v.get('status') == 'pending':
                                if k not in _opened_payment_keys:
                                    _opened_payment_keys.add(k)
                                    print(f"[Payment Watcher] 🔔 Customer confirmed payment: {k} (Amount: {v.get('price')} THB). Auto-opening Chrome...")
                                    open_admin_payment_in_chrome()
                            elif isinstance(v, dict) and v.get('status') != 'pending':
                                _opened_payment_keys.discard(k)
            except Exception:
                pass
            time.sleep(2)

    t = threading.Thread(target=watcher_loop, daemon=True)
    t.start()

# --- MAIN ---
class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    event_handler = DownloadHandler()
    observer = Observer()
    observer.schedule(event_handler, DOWNLOADS_PATH, recursive=False)
    observer.start()

    desktop_handler = DesktopHandler()
    desktop_observer = Observer()
    desktop_observer.schedule(desktop_handler, DESKTOP_PATH, recursive=False)
    desktop_observer.start()

    httpd = ThreadingHTTPServer(("", PORT), HubHandler)
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    print(f"[Server] Serving in Threaded mode at port {PORT}")

    # Start Firebase Payment Watcher (Auto-opens Chrome on customer confirmation)
    start_payment_requests_watcher()

    # Start KBank Live Notification Auto-Pay Listener (Auto-approves on deposit)
    start_kbank_notification_listener()

    # Launch floating status and loading progress bar widget (same as Facebook_Bot)
    write_status_file(0, 'idle', 'พร้อมทำงาน', task_type="idle")
    ensure_watcher_gui_running()

    # Clean up any leftover cache files from previous sessions immediately on startup
    cleanup_video_cache(clean_all=True)

    # Used by the Chrome add-on.  Running without a tray is more reliable
    # when the process was launched from a hidden/background session.
    if '--headless' in sys.argv:
        try:
            while server_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            observer.stop()
            observer.join()
            desktop_observer.stop()
            desktop_observer.join()
            httpd.shutdown()
            httpd.server_close()
        raise SystemExit(0)

    from PIL import Image, ImageDraw
    import pystray

    def on_quit(icon, item):
        observer.stop()
        desktop_observer.stop()
        httpd.shutdown()
        httpd.server_close()
        icon.stop()

    tray_icon_instance = pystray.Icon("AI_Hub_Watcher", make_tray_icon(), f"AI Hub Central (Port {PORT})", menu=pystray.Menu(
        pystray.MenuItem("Quit", on_quit)
    ))
    icon = tray_icon_instance

    try:
        icon.run()
        # Some Windows sessions cannot keep a system-tray icon alive.  In that
        # case pystray returns immediately, but the local HTTP API must remain
        # available for the Chrome extension (Edge TTS/Binance Square).
        # on_quit() explicitly shuts the server down, so this loop still exits
        # normally when the user chooses Quit from the tray menu.
        while server_thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        desktop_observer.stop()
        desktop_observer.join()
        httpd.shutdown()
        httpd.server_close()
