# -*- coding: utf-8 -*-
"""
text_retouch_engine.py
ระบบแบบ Agent-Style สำหรับ Text-Retouch service
- รับ patch เล็กๆ จาก Firebase (ไม่ใช่ไฟล์เต็ม)
- เปิด patch ใน Photoshop พร้อม text layer โน้ต
- ส่ง result กลับ + watermark
- หลังชำระเงิน: ส่ง result ไม่มีลายน้ำ
"""

import os, sys, json, base64, urllib.request, urllib.parse, subprocess, time
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

FIREBASE_DB_URL = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "text_retouch")
ACTIVE_STATE_FILE = os.path.join(CACHE_DIR, "active_patch.json")

os.makedirs(CACHE_DIR, exist_ok=True)


def fb_get(path):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())


def fb_set(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PUT",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def fb_patch(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PATCH",
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def get_photoshop_path():
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Photoshop.exe")
        path, _ = winreg.QueryValueEx(key, "")
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    candidates = [
        r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop CC 2019\Photoshop.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "photoshop"


# ─────────────────────────────────────────────────────────────────
#  1. WATCH FOR NEW PATCHES — Called by auto_donate_watcher.py
# ─────────────────────────────────────────────────────────────────
def watch_and_open_next():
    """
    สแกน Firebase หา patch ที่ status=working แล้วยังไม่มีในเครื่อง
    เปิด patch นั้นเข้า Photoshop ทันที
    """
    print("[TextRetouch] 🔍 ค้นหางานใหม่...")
    sessions = fb_get("text_retouch") or {}

    for session_id, session in sessions.items():
        patches = session.get("patches", {})
        for patch_id, patch in patches.items():
            if patch.get("status") == "working" and patch.get("patchImage"):
                # ตรวจสอบว่าเราทำ patch นี้อยู่แล้วหรือเปล่า
                if os.path.exists(ACTIVE_STATE_FILE):
                    with open(ACTIVE_STATE_FILE) as f:
                        active = json.load(f)
                    if active.get("patch_id") == patch_id:
                        print(f"[TextRetouch] ⏳ กำลังทำ patch {patch_id} อยู่แล้ว")
                        return

                open_patch_in_photoshop(session_id, patch_id, patch)
                return  # ทำทีละอัน

    print("[TextRetouch] 💤 ไม่มีงานใหม่")


def open_patch_in_photoshop(session_id, patch_id, patch_data):
    """เปิด patch image เข้า Photoshop + สร้าง layer โน้ต"""

    # 1. Decode base64 patch image → บันทึกเป็น PNG
    patch_path = os.path.join(CACHE_DIR, f"{patch_id}.png")
    result_path = os.path.join(CACHE_DIR, f"{patch_id}_result.png")
    note_path = os.path.join(CACHE_DIR, f"{patch_id}_note.txt")

    b64_data = patch_data.get("patchImage", "")
    img_bytes = base64.b64decode(b64_data)
    with open(patch_path, "wb") as f:
        f.write(img_bytes)

    note = patch_data.get("note", "")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(note)

    # 2. บันทึก active state
    state = {
        "session_id": session_id,
        "patch_id": patch_id,
        "patch_num": patch_data.get("num", 1),
        "note": note,
        "patch_path": patch_path,
        "result_path": result_path,
        "opened_at": time.time()
    }
    with open(ACTIVE_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    # 3. สร้าง JSX script สำหรับเปิด PS + layer text
    jsx_path = os.path.join(CACHE_DIR, "open_patch.jsx")
    patch_path_jsx = patch_path.replace("\\", "/")
    note_escaped = note.replace('"', '\\"').replace('\n', '\\n')
    result_path_jsx = result_path.replace("\\", "/")
    num = patch_data.get("num", 1)

    jsx = f"""
// Text-Retouch: Auto-open patch #{num}
var patchFile = new File("{patch_path_jsx}");
var doc = app.open(patchFile);
doc.resizeCanvas(doc.width, doc.height + 60, AnchorPosition.TOPCENTER);

// Add note text layer
var textLayer = doc.artLayers.add();
textLayer.kind = LayerKind.TEXT;
textLayer.name = "📝 โน้ต #" + {num};
var txt = textLayer.textItem;
txt.contents = "#{num}: " + "{note_escaped}";
txt.size = 18;
txt.color.rgb.hexValue = "FFDD00";
txt.position = [10, doc.height - 40];

// Active layer = Background (for editing)
doc.activeLayer = doc.layers[doc.layers.length - 1];

// Save result path for submit
app.putCustomOptions("TextRetouchResultPath", new ActionDescriptor(), true);
var desc = new ActionDescriptor();
desc.putString(app.stringIDToTypeID("resultPath"), "{result_path_jsx}");
app.putCustomOptions("TextRetouchResultPath", desc, true);

alert("✅ Text-Retouch #" + {num} + " โหลดแล้ว!\\n\\nโน้ต: {note_escaped}\\n\\nแก้ไขให้เสร็จแล้วกด F12 เพื่อส่งงาน");
"""
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx)

    # 4. เปิด Photoshop + รัน script
    ps_path = get_photoshop_path()
    print(f"[TextRetouch] 🎨 เปิด Photoshop: patch #{num} — '{note}'")
    subprocess.Popen([ps_path, "-run", jsx_path], shell=False)

    # 5. อัพเดท status Firebase → opened
    try:
        fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
            "status": "working",
            "openedAt": int(time.time() * 1000)
        })
    except Exception as e:
        print(f"[TextRetouch] ⚠️ ไม่สามารถอัพเดท Firebase: {e}")


# ─────────────────────────────────────────────────────────────────
#  2. SUBMIT RESULT — Called when admin presses F12 in Photoshop
# ─────────────────────────────────────────────────────────────────
def submit_result_from_photoshop():
    """
    อ่านไฟล์ผลลัพธ์จาก Photoshop แล้วส่งขึ้น Firebase พร้อมลายน้ำ
    """
    if not os.path.exists(ACTIVE_STATE_FILE):
        print("[TextRetouch] ❌ ไม่พบ active patch state")
        return False

    with open(ACTIVE_STATE_FILE, encoding="utf-8") as f:
        state = json.load(f)

    session_id = state["session_id"]
    patch_id = state["patch_id"]
    patch_num = state.get("patch_num", 1)
    result_path = state["result_path"]

    if not os.path.exists(result_path):
        # ลองหาไฟล์ที่ save จาก PS โดยตรง
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fallback = os.path.join(desktop, "text_retouch_result.png")
        if os.path.exists(fallback):
            result_path = fallback
        else:
            print(f"[TextRetouch] ❌ ไม่พบไฟล์ผลลัพธ์: {result_path}")
            print(f"   กรุณา Save As → {result_path} แล้วลองใหม่")
            return False

    print(f"[TextRetouch] ✅ พบผลลัพธ์: {result_path}")

    # 1. เพิ่มลายน้ำ
    watermarked_path = result_path.replace(".png", "_wm.jpg")
    watermarked_b64 = apply_watermark(result_path, watermarked_path, patch_num)

    # 2. เข้ารหัส clean version
    with open(result_path, "rb") as f:
        clean_b64 = base64.b64encode(f.read()).decode()

    # 3. อ่านข้อมูล patch จาก Firebase สำหรับกำหนดราคา
    try:
        patch_data = fb_get(f"text_retouch/{session_id}/patches/{patch_id}") or {}
        current_price = patch_data.get("price", 0)
    except Exception:
        current_price = 0

    if current_price == 0:
        # ถามราคา
        try:
            price_input = input(f"💰 กำหนดราคาสำหรับจุดที่ {patch_num} (บาท): ").strip()
            current_price = float(price_input) if price_input else 0
        except Exception:
            current_price = 0

    # 4. ส่งขึ้น Firebase
    print(f"[TextRetouch] ☁️ ส่งผลลัพธ์ขึ้น Firebase...")
    fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
        "status": "preview",
        "price": current_price,
        "resultImage": watermarked_b64,       # มีลายน้ำ (ลูกค้าเห็น)
        "resultImageClean": clean_b64,          # ไม่มีลายน้ำ (ปลดหลังชำระ)
        "submittedAt": int(time.time() * 1000)
    })

    print(f"[TextRetouch] 🚀 ส่งจุดที่ {patch_num} ให้ลูกค้าตรวจแล้ว! ราคา ฿{current_price}")

    # 5. ลบ active state
    try:
        os.remove(ACTIVE_STATE_FILE)
    except Exception:
        pass

    return True


def apply_watermark(input_path, output_path, patch_num):
    """เพิ่มลายน้ำ PREVIEW บน result patch"""
    img = Image.open(input_path).convert("RGBA")
    W, H = img.size

    overlay = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # เส้นทแยงมุม
    step = max(12, min(W, H) // 8)
    for offset in range(-H, W + H, step):
        draw.line([(offset, 0), (offset + H, H)], fill=(255, 255, 255, 70), width=2)

    # กรอบสีส้ม
    draw.rectangle([0, 0, W-1, H-1], outline=(245, 158, 11, 200), width=3)

    # ตัวหนังสือ PREVIEW
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", max(14, min(W, H) // 5))
    except Exception:
        font = ImageFont.load_default()

    label = "PREVIEW"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx, ty = (W - tw) // 2, (H - th) // 2
    draw.rectangle([tx - 8, ty - 4, tx + tw + 8, ty + th + 4], fill=(15, 23, 42, 210))
    draw.text((tx, ty), label, font=font, fill=(254, 240, 138, 255))

    final = Image.alpha_composite(img, overlay).convert("RGB")
    final.save(output_path, "JPEG", quality=90)

    with open(output_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


# ─────────────────────────────────────────────────────────────────
#  3. CONFIRM PAYMENT — Called after payment verified
# ─────────────────────────────────────────────────────────────────
def confirm_payment(session_id, patch_id):
    """ปลดลายน้ำ — อัพเดทสถานะเป็น 'done'"""
    try:
        patch_data = fb_get(f"text_retouch/{session_id}/patches/{patch_id}") or {}
        fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
            "status": "done",
            "paidAt": int(time.time() * 1000)
        })
        print(f"[TextRetouch] ✅ ยืนยันชำระเงิน patch {patch_id} เรียบร้อย")
        return True
    except Exception as e:
        print(f"[TextRetouch] ❌ ยืนยันชำระเงินล้มเหลว: {e}")
        return False


# ─────────────────────────────────────────────────────────────────
#  HTTP HANDLER — for auto_donate_watcher.py to call
# ─────────────────────────────────────────────────────────────────
def handle_request(action, post_data=None):
    """
    action = 'watch'      → ค้นหา + เปิด patch ใหม่
    action = 'submit'     → ส่งผลลัพธ์หลัง PS บันทึก
    action = 'confirm_payment' → ยืนยันชำระเงิน (post_data: {session_id, patch_id})
    """
    if action == "watch":
        watch_and_open_next()
        return {"ok": True}

    elif action == "submit":
        success = submit_result_from_photoshop()
        return {"ok": success}

    elif action == "confirm_payment":
        data = post_data or {}
        sid = data.get("session_id", "")
        pid = data.get("patch_id", "")
        success = confirm_payment(sid, pid)
        return {"ok": success}

    return {"ok": False, "error": "Unknown action"}


# ─────────────────────────────────────────────────────────────────
#  CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "--watch":
            watch_and_open_next()
        elif action == "--submit":
            submit_result_from_photoshop()
        elif action == "--confirm" and len(sys.argv) > 3:
            confirm_payment(sys.argv[2], sys.argv[3])
        else:
            print("Usage:")
            print("  python text_retouch_engine.py --watch")
            print("  python text_retouch_engine.py --submit")
            print("  python text_retouch_engine.py --confirm <session_id> <patch_id>")
    else:
        print("Text-Retouch Engine v2 — Agent Style")
        print("Run with --watch / --submit / --confirm")
