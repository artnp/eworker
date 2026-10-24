# -*- coding: utf-8 -*-
"""
text_retouch_engine.py
ระบบแบบ Agent-Style สำหรับ Text-Retouch service (โครงการ retouch-ebid)
- ลูกค้าส่งโจทย์ (crop + note) -> สถานะ pending_review
- เด้งหลังบ้านให้แอดมินดู -> เสนอราคา หรือ ปฏิเสธ (เสี่ยงกฎหมาย, มีลายเซ็นต์, ติดตราครุฑ)
- เมื่อส่งราคา -> หน้าจอลูกค้าเด้ง PromptPay QR ให้โอนเงินก่อน
- เมื่อโอนสำเร็จ (status=paid) -> ส่งภาพเข้า Photoshop ทันที
- เมื่อแอดมินแก้เสร็จใน Photoshop (F12) -> ส่งงานกลับให้ลูกค้าแบบไม่มีลายน้ำ
"""

import os, sys, json, base64, urllib.request, urllib.parse, subprocess, time
from io import BytesIO
from PIL import Image

FIREBASE_DB_URL = "https://retouch-ebid-default-rtdb.asia-southeast1.firebasedatabase.app"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "text_retouch")
ACTIVE_STATE_FILE = os.path.join(CACHE_DIR, "active_patch.json")

os.makedirs(CACHE_DIR, exist_ok=True)


def fb_get(path):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def fb_set(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PUT",
                                  headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def fb_patch(path, data):
    url = f"{FIREBASE_DB_URL}/{path}.json"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method="PATCH",
                                  headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def ensure_photoshop_config():
    """เพิ่ม WarnRunningScripts 0 ให้กับ Photoshop settings ทุกเวอร์ชัน เพื่อไม่ให้เด้งถามสคริปต์"""
    try:
        appdata = os.environ.get("APPDATA", "")
        adobe_dir = os.path.join(appdata, "Adobe")
        if not os.path.exists(adobe_dir):
            return
        for item in os.listdir(adobe_dir):
            if "Photoshop" in item:
                ps_folder = os.path.join(adobe_dir, item)
                if os.path.isdir(ps_folder):
                    for sub in os.listdir(ps_folder):
                        if "Settings" in sub:
                            settings_dir = os.path.join(ps_folder, sub)
                            cfg_path = os.path.join(settings_dir, "PSUserConfig.txt")
                            content = ""
                            if os.path.exists(cfg_path):
                                with open(cfg_path, "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read()
                            if "WarnRunningScripts" not in content:
                                with open(cfg_path, "a", encoding="utf-8") as f:
                                    f.write("\nWarnRunningScripts 0\n")
    except Exception as e:
        pass


def get_photoshop_path():
    ensure_photoshop_config()
    candidates = [
        r"C:\Program Files\Adobe\Adobe Photoshop 2023\PhotoshopLauncher.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2024\PhotoshopLauncher.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2025\PhotoshopLauncher.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2023\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2024\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop 2025\Photoshop.exe",
        r"C:\Program Files\Adobe\Adobe Photoshop CC 2019\Photoshop.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Photoshop.exe")
        path, _ = winreg.QueryValueEx(key, "")
        if path and os.path.exists(path):
            launcher = os.path.join(os.path.dirname(path), "PhotoshopLauncher.exe")
            if os.path.exists(launcher):
                return launcher
            return path
    except Exception:
        pass
    return "photoshop"



# ─────────────────────────────────────────────────────────────────
#  1. ADMIN REVIEW POPUP (Tkinter) — เด้งขึ้นมาให้คิดราคา หรือ ปฏิเสธ
# ─────────────────────────────────────────────────────────────────
def show_review_popup(session_id, patch_id):
    """
    หน้าต่างเด้งขึ้นมาบนจอแอดมินทันทีเมื่อมีโจทย์ใหม่
    - แสดงรูป patch + โน้ต
    - เลือกคิดราคา (ส่ง QR ให้ลูกค้าโอน)
    - หรือเลือกปฏิเสธ เพราะอะไร (เสี่ยงกฎหมาย, มีลายเซ็นต์, ติดตราครุฑ)
    """
    import tkinter as tk
    from tkinter import ttk, messagebox
    from PIL import ImageTk

    try:
        import winsound
        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass

    patch_data = fb_get(f"text_retouch/{session_id}/patches/{patch_id}") or {}
    if not patch_data:
        print(f"[TextRetouch] ❌ ไม่พบข้อมูล patch {patch_id}")
        return

    # บันทึกรูปชั่วคราวเพื่อแสดงใน GUI
    patch_b64 = patch_data.get("patchImage", "")
    patch_img = None
    if patch_b64:
        try:
            img_bytes = base64.b64decode(patch_b64)
            patch_img = Image.open(BytesIO(img_bytes))
        except Exception as e:
            print(f"[TextRetouch] แปลงรูปภาพล้มเหลว: {e}")

    num = patch_data.get("num", 1)
    note = patch_data.get("note", "(ไม่มีโน้ต)")

    root = tk.Tk()
    root.title(f"🔔 Text-Retouch: โจทย์ใหม่ #{num} (Session: {session_id[:10]}...)")
    root.geometry("820x620")
    root.configure(bg="#0b1120")
    root.attributes("-topmost", True)

    # Styling colors
    BG_CARD = "#1e293b"
    TEXT_MAIN = "#f8fafc"
    TEXT_MUTED = "#94a3b8"
    ACCENT_GREEN = "#10b981"
    ACCENT_RED = "#ef4444"
    ACCENT_BLUE = "#6366f1"

    # Header
    header_frame = tk.Frame(root, bg="#0f172a", padx=20, pady=12)
    header_frame.pack(fill="x")
    title_lbl = tk.Label(header_frame, text=f"✨ มีงานใหม่ส่งเข้ามา! จุดที่ #{num}", 
                         font=("Sarabun", 15, "bold"), fg="#fbbf24", bg="#0f172a")
    title_lbl.pack(side="left")
    sub_lbl = tk.Label(header_frame, text=f"Session: {session_id}", 
                       font=("Consolas", 9), fg=TEXT_MUTED, bg="#0f172a")
    sub_lbl.pack(side="right", pady=4)

    # Main content frame (2 columns)
    content_frame = tk.Frame(root, bg="#0b1120", padx=16, pady=12)
    content_frame.pack(fill="both", expand=True)

    # ── Left Column: Preview Image + Note ──
    left_frame = tk.Frame(content_frame, bg=BG_CARD, padx=14, pady=14, relief="ridge", bd=1)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

    tk.Label(left_frame, text="🔍 ชิ้นส่วนที่ลูกค้าต้องการแก้ไข (Crop Patch):", 
             font=("Sarabun", 11, "bold"), fg=TEXT_MAIN, bg=BG_CARD).pack(anchor="w", pady=(0, 6))

    # Image preview box
    img_lbl = tk.Label(left_frame, bg="#020617", relief="sunken", bd=1)
    img_lbl.pack(fill="both", expand=True, pady=(0, 10))

    photo_ref = None
    if patch_img:
        # Resize to fit in left frame (max 380x280)
        orig_w, orig_h = patch_img.size
        max_w, max_h = 380, 260
        scale = min(max_w / orig_w, max_h / orig_h, 1.0)
        disp_w, disp_h = max(1, int(orig_w * scale)), max(1, int(orig_h * scale))
        resized_img = patch_img.resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        photo_ref = ImageTk.PhotoImage(resized_img)
        img_lbl.config(image=photo_ref)
    else:
        img_lbl.config(text="[ไม่มีภาพชิ้นส่วน]", fg=TEXT_MUTED)

    tk.Label(left_frame, text="📝 คำสั่ง / โน้ตจากลูกค้า:", 
             font=("Sarabun", 11, "bold"), fg="#38bdf8", bg=BG_CARD).pack(anchor="w", pady=(4, 2))
    
    note_box = tk.Text(left_frame, height=4, font=("Sarabun", 10), bg="#0f172a", fg="#f1f5f9",
                       wrap="word", relief="flat", padx=8, pady=8)
    note_box.insert("1.0", note)
    note_box.config(state="disabled")
    note_box.pack(fill="x", pady=(0, 4))

    # ── Right Column: Decisions (Quote or Reject) ──
    right_frame = tk.Frame(content_frame, bg="#0b1120", width=360)
    right_frame.pack(side="right", fill="both", expand=False)

    # Box 1: Quote Price
    quote_card = tk.LabelFrame(right_frame, text="  ✅ อนุมัติ & คิดราคา (ส่งสลิปให้ลูกค้าโอน)  ", 
                               font=("Sarabun", 11, "bold"), fg="#34d399", bg=BG_CARD, padx=12, pady=10)
    quote_card.pack(fill="x", pady=(0, 12))

    tk.Label(quote_card, text="ระบุราคาที่ต้องการคิด (บาท):", font=("Sarabun", 10), fg=TEXT_MAIN, bg=BG_CARD).pack(anchor="w")

    price_input_frame = tk.Frame(quote_card, bg=BG_CARD)
    price_input_frame.pack(fill="x", pady=(4, 8))

    tk.Label(price_input_frame, text="฿", font=("Sarabun", 14, "bold"), fg="#34d399", bg=BG_CARD).pack(side="left", padx=(0, 4))
    price_var = tk.StringVar(value="100")
    price_entry = tk.Entry(price_input_frame, textvariable=price_var, font=("Sarabun", 13, "bold"), 
                           width=10, bg="#0f172a", fg="#f1f5f9", insertbackground="white")
    price_entry.pack(side="left")

    # Quick preset buttons
    preset_frame = tk.Frame(quote_card, bg=BG_CARD)
    preset_frame.pack(fill="x", pady=(0, 8))
    for p in [50, 100, 150, 200]:
        btn = tk.Button(preset_frame, text=f"฿{p}", font=("Sarabun", 9), bg="#334155", fg=TEXT_MAIN,
                        relief="flat", padx=6, pady=2, command=lambda val=p: price_var.set(str(val)))
        btn.pack(side="left", padx=2)

    def on_submit_quote():
        try:
            val = float(price_var.get().strip())
            if val <= 0:
                messagebox.showerror("ผิดพลาด", "กรุณาระบุราคามากกว่า 0 บาท")
                return
            quote_patch(session_id, patch_id, val)
            messagebox.showinfo("สำเร็จ", f"✅ ส่งราคา ฿{val} ให้ลูกค้าแล้ว!\n\nหน้าจอลูกค้าจะเด้งสลิป PromptPay ให้โอนเงินทันที")
            root.destroy()
        except ValueError:
            messagebox.showerror("ผิดพลาด", "กรุณากรอกตัวเลขราคาที่ถูกต้อง")

    btn_quote = tk.Button(quote_card, text="📤 ส่งราคาให้ลูกค้าโอนเงิน", font=("Sarabun", 11, "bold"),
                          bg=ACCENT_GREEN, fg="#ffffff", activebackground="#059669",
                          relief="flat", padx=12, pady=8, cursor="hand2", command=on_submit_quote)
    btn_quote.pack(fill="x")

    # Box 2: Reject Work
    reject_card = tk.LabelFrame(right_frame, text="  ❌ ปฏิเสธงานนี้ (เลือกเหตุผล)  ", 
                                font=("Sarabun", 11, "bold"), fg="#f87171", bg=BG_CARD, padx=12, pady=10)
    reject_card.pack(fill="x")

    reject_reason_var = tk.StringVar(value="เสี่ยงต่อกฎหมาย / เอกสารราชการ")

    reasons = [
        "เสี่ยงต่อกฎหมาย / เอกสารราชการ",
        "มีลายเซ็นต์ติด",
        "ติดตราครุฑ",
        "ภาพไม่ชัดเจน ไม่สามารถแก้ไขได้",
        "อื่นๆ (ระบุเอง)"
    ]

    custom_reason_entry = None

    for r in reasons:
        rb = tk.Radiobutton(reject_card, text=r, variable=reject_reason_var, value=r,
                            font=("Sarabun", 9), fg=TEXT_MAIN, bg=BG_CARD, selectcolor="#0f172a",
                            activebackground=BG_CARD, activeforeground=TEXT_MAIN)
        rb.pack(anchor="w", pady=2)

    custom_reason_var = tk.StringVar(value="")
    custom_entry = tk.Entry(reject_card, textvariable=custom_reason_var, font=("Sarabun", 9),
                            bg="#0f172a", fg="#f1f5f9", insertbackground="white")
    custom_entry.pack(fill="x", pady=(2, 8))

    def on_submit_reject():
        selected = reject_reason_var.get()
        if selected == "อื่นๆ (ระบุเอง)":
            reason = custom_reason_var.get().strip() or "ไม่สามารถรับงานนี้ได้"
        else:
            reason = selected
        
        if messagebox.askyesno("ยืนยัน", f"ต้องการปฏิเสธงานนี้ใช่หรือไม่?\n\nเหตุผล: {reason}"):
            reject_patch(session_id, patch_id, reason)
            messagebox.showinfo("สำเร็จ", f"❌ ปฏิเสธงานเรียบร้อยแล้ว\n\nระบบจะแจ้งเหตุผลให้ลูกค้าทราบทันที")
            root.destroy()

    btn_reject = tk.Button(reject_card, text="⛔ ปฏิเสธงาน", font=("Sarabun", 10, "bold"),
                           bg=ACCENT_RED, fg="#ffffff", activebackground="#dc2626",
                           relief="flat", padx=12, pady=6, cursor="hand2", command=on_submit_reject)
    btn_reject.pack(fill="x", pady=(4, 0))

    root.mainloop()


# ─────────────────────────────────────────────────────────────────
#  2. ACTIONS: QUOTE / REJECT / PAID
# ─────────────────────────────────────────────────────────────────
def quote_patch(session_id, patch_id, price):
    """แอดมินส่งราคา -> อัพเดท Firebase เป็น pending_payment เพื่อให้ลูกค้าเห็นสลิปโอน"""
    print(f"[TextRetouch] 💰 เสนอราคาจุดที่ {patch_id}: ฿{price}")
    fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
        "status": "pending_payment",
        "price": float(price),
        "quotedAt": int(time.time() * 1000)
    })


def reject_patch(session_id, patch_id, reason):
    """แอดมินปฏิเสธงาน -> อัพเดท Firebase พร้อมเหตุผล และลบภาพออกจากระบบไม่ให้รก"""
    print(f"[TextRetouch] ❌ ปฏิเสธจุดที่ {patch_id}: {reason}")
    fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
        "status": "rejected",
        "rejectReason": reason,
        "rejectedAt": int(time.time() * 1000),
        "patchImage": None
    })
    for fname in [f"{patch_id}.png", f"{patch_id}_note.txt", f"{patch_id}_result.png"]:
        fpath = os.path.join(CACHE_DIR, fname)
        if os.path.exists(fpath):
            try:
                os.remove(fpath)
            except Exception:
                pass


def mark_patch_paid(session_id, patch_id):
    """เมื่อลูกค้าโอนเงินสำเร็จ -> เปิดเข้า Photoshop ทันที"""
    print(f"[TextRetouch] 💳 ลูกค้าชำระเงินแล้ว! กำลังส่งเข้า Photoshop: {patch_id}")
    patch_data = fb_get(f"text_retouch/{session_id}/patches/{patch_id}") or {}
    fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
        "status": "working",
        "paidAt": int(time.time() * 1000)
    })
    open_patch_in_photoshop(session_id, patch_id, patch_data)


_last_opened_patch = {"id": None, "time": 0}

# ─────────────────────────────────────────────────────────────────
#  3. OPEN IN PHOTOSHOP — ส่งงานเข้า Photoshop
# ─────────────────────────────────────────────────────────────────
def open_patch_in_photoshop(session_id, patch_id, patch_data):
    """เปิด patch image เข้า Photoshop + สร้าง layer โน้ต (ป้องกันส่งซ้ำ)"""
    now = time.time()
    if _last_opened_patch.get("id") == patch_id and (now - _last_opened_patch.get("time", 0)) < 8:
        print(f"[TextRetouch] ⏩ งานจุดที่ {patch_data.get('num', 1)} เพิ่งถูกเปิดเข้า Photoshop เมื่อสักครู่ ข้ามเพื่อป้องกันการส่งซ้ำ")
        return
    _last_opened_patch["id"] = patch_id
    _last_opened_patch["time"] = now

    patch_path = os.path.join(CACHE_DIR, f"{patch_id}.png")
    result_path = os.path.join(CACHE_DIR, f"{patch_id}_result.png")
    note_path = os.path.join(CACHE_DIR, f"{patch_id}_note.txt")

    b64_data = patch_data.get("patchImage", "")
    if not b64_data:
        print("[TextRetouch] ⚠️ ไม่มี patchImage ในข้อมูล")
        return

    img_bytes = base64.b64decode(b64_data)
    with open(patch_path, "wb") as f:
        f.write(img_bytes)

    note = patch_data.get("note", "")
    with open(note_path, "w", encoding="utf-8") as f:
        f.write(note)

    # บันทึก active state
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

    # สร้าง JSX script สำหรับเปิด PS + layer text
    jsx_path = os.path.join(CACHE_DIR, "open_patch.jsx")
    patch_path_jsx = patch_path.replace("\\", "/")
    note_escaped = note.replace('"', '\\"').replace('\n', '\\n')
    result_path_jsx = result_path.replace("\\", "/")
    num = patch_data.get("num", 1)

    # เช็คว่าโจทย์คือการสั่งลบหรือไม่
    is_delete_cmd = note.strip().lower() in ["ลบ", "delete", "remove", "ลบออก", "ลบข้อความ", "ลบคำ", "เอาออก"]
    layer_name = f"📝 #{num}: {note_escaped}"

    jsx = f"""#target photoshop
app.displayDialogs = DialogModes.NO;

// Text-Retouch: Auto-open patch #{num}
var patchFile = new File("{patch_path_jsx}");
var doc = app.open(patchFile);

// ลบเลเยอร์โน้ตเก่าที่อาจสร้างซ้ำออกก่อนเสมอ เพื่อให้เหลือเพียงเลเยอร์เดียว 100%
try {{
    for (var i = doc.artLayers.length - 1; i >= 0; i--) {{
        var ly = doc.artLayers[i];
        if (ly.kind == LayerKind.TEXT && (ly.name.indexOf("#{num}:") != -1 || ly.name == "{layer_name}")) {{
            ly.remove();
        }}
    }}
}} catch(errClean) {{}}

// สร้าง Text Layer แยกสำหรับข้อความที่จะแก้เพียงอันเดียว
try {{
    var textLayer = doc.artLayers.add();
    textLayer.kind = LayerKind.TEXT;
    textLayer.name = "{layer_name}";
    var txt = textLayer.textItem;
    txt.contents = "{note_escaped}";
    txt.size = Math.min(Math.max(doc.height * 0.4, 14), 60);
    txt.position = [10, Math.min(doc.height * 0.75, doc.height - 5)];
    txt.color.rgb.hexValue = "000000";

    // ซ่อนเลเยอร์โน้ตไว้เสมอ เพื่อไม่ให้มีตัวหนังสือหรือสัญลักษณ์ส่วนเกินปรากฏบังภาพงาน
    textLayer.visible = false;
}} catch(e) {{}}

// Active layer = Background (สำหรับรีทัชภาพ)
try {{
    doc.activeLayer = doc.layers[doc.layers.length - 1];
}} catch(e) {{}}

// Save result path for submit
try {{
    app.putCustomOptions("TextRetouchResultPath", new ActionDescriptor(), true);
    var desc = new ActionDescriptor();
    desc.putString(app.stringIDToTypeID("resultPath"), "{result_path_jsx}");
    app.putCustomOptions("TextRetouchResultPath", desc, true);
}} catch(e) {{}}

// ดึง Photoshop ขึ้นมาบนหน้าจอหลัก
try {{
    app.bringToFront();
}} catch(e) {{}}
"""
    with open(jsx_path, "w", encoding="utf-8") as f:
        f.write(jsx)

    print(f"[TextRetouch] 🎨 กำลังเปิดเข้า Photoshop: patch #{num} — '{note}'")
    ps_path = get_photoshop_path()
    ps_dir = os.path.dirname(ps_path) if ps_path and os.path.exists(ps_path) else None

    # ตรวจสอบว่า Photoshop กำลังรันอยู่หรือไม่
    import psutil
    has_ps_running = False

    for p in psutil.process_iter(['name']):
        try:
            if 'photoshop' in p.info.get('name', '').lower():
                has_ps_running = True
                break
        except Exception:
            pass

    # หากยังไม่เปิด ให้รันผ่าน Launcher (พร้อม cwd ที่ถูกต้อง เพื่อให้โหลด GUI เต็มรูปแบบ)
    if not has_ps_running and ps_path and os.path.exists(ps_path):
        print(f"[TextRetouch] 🚀 เปิดโปรแกรม Photoshop ผ่าน Launcher: {ps_path}")
        try:
            subprocess.Popen([ps_path, jsx_path], cwd=ps_dir, shell=False)
        except Exception:
            try:
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(None, "open", ps_path, f'"{jsx_path}"', ps_dir, 1)
            except Exception:
                pass

    # ส่งคำสั่ง JSX ผ่าน COM Automation
    connected = False
    for attempt in range(25):
        try:
            import win32com.client
            ps = win32com.client.Dispatch("Photoshop.Application")
            ps.DoJavaScriptFile(jsx_path)
            print(f"[TextRetouch] ⚡ Photoshop โหลดภาพและเลเยอร์เรียบร้อยสมบูรณ์")
            connected = True
            break
        except Exception:
            time.sleep(1)

    if not connected and ps_path and os.path.exists(ps_path):
        # Fallback สั่งเปิดไฟล์ JSX โดยตรง
        try:
            subprocess.Popen([ps_path, jsx_path], cwd=ps_dir, shell=False)
        except Exception:
            pass

    # ดึงหน้าต่าง Photoshop ขึ้นหน้าจอหลักทันที (Activate Foreground)
    try:
        import win32com.client
        wsh = win32com.client.Dispatch("WScript.Shell")
        wsh.AppActivate("Adobe Photoshop")
        wsh.AppActivate("Photoshop")
    except Exception:
        pass

    try:
        import winsound
        winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────
#  4. SUBMIT RESULT FROM PHOTOSHOP (F12) — แบบไม่มีลายน้ำ
# ─────────────────────────────────────────────────────────────────
def submit_result_from_photoshop(custom_file=None):
    """
    อ่านไฟล์ผลลัพธ์จาก Photoshop แล้วส่งขึ้น Firebase แบบ Clean (ไม่มีลายน้ำ)
    เพราะลูกค้าได้ชำระเงินก่อนแล้ว
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

    if custom_file and os.path.exists(custom_file):
        import shutil
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        shutil.copy2(custom_file, result_path)
        print(f"[TextRetouch] คัดลอกผลลัพธ์จาก {custom_file} -> {result_path}")

    if not os.path.exists(result_path):
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        fallback = os.path.join(desktop, "text_retouch_result.png")
        if os.path.exists(fallback):
            result_path = fallback
        else:
            print(f"[TextRetouch] ❌ ไม่พบไฟล์ผลลัพธ์: {result_path}")
            return False

    print(f"[TextRetouch] ✅ พบผลลัพธ์: {result_path}")

    # เข้ารหัส Clean version โดยตรง (ไม่มีลายน้ำ)
    with open(result_path, "rb") as f:
        clean_b64 = base64.b64encode(f.read()).decode()

    # ส่งขึ้น Firebase: status=done
    print(f"[TextRetouch] 🚀 ส่งงานจุดที่ {patch_num} ให้ลูกค้า (แบบไม่มีลายน้ำ)...")
    fb_patch(f"text_retouch/{session_id}/patches/{patch_id}", {
        "status": "done",
        "resultImage": clean_b64,
        "completedAt": int(time.time() * 1000)
    })

    print(f"[TextRetouch] 🎉 สำเร็จ! จุดที่ {patch_num} ส่งถึงลูกค้าเรียบร้อย")

    try:
        os.remove(ACTIVE_STATE_FILE)
    except Exception:
        pass

    return True


# ─────────────────────────────────────────────────────────────────
#  5. HTTP DISPATCHER — for auto_donate_watcher.py
# ─────────────────────────────────────────────────────────────────
def handle_request(action, post_data=None):
    post_data = post_data or {}
    sid = post_data.get("session_id", "")
    pid = post_data.get("patch_id", "")

    if action == "submit":
        return {"ok": submit_result_from_photoshop()}

    elif action == "quote":
        price = float(post_data.get("price", 0))
        quote_patch(sid, pid, price)
        return {"ok": True}

    elif action == "reject":
        reason = post_data.get("reason", "ไม่สามารถรับงานนี้ได้")
        reject_patch(sid, pid, reason)
        return {"ok": True}

    elif action == "mark_paid":
        mark_patch_paid(sid, pid)
        return {"ok": True}

    elif action == "review":
        # เปิดหน้าแอดมิน HTML ใน Chrome
        admin_url = "http://127.0.0.1:5000/admin-text-retouch.html"
        chrome_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        opened = False
        for cpath in chrome_candidates:
            if os.path.exists(cpath):
                subprocess.Popen([cpath, admin_url])
                opened = True
                break
        if not opened:
            import webbrowser
            webbrowser.open(admin_url)
        return {"ok": True}

    return {"ok": False, "error": f"Unknown action: {action}"}


# ─────────────────────────────────────────────────────────────────
#  6. CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1]
        if action == "--review" and len(sys.argv) > 3:
            show_review_popup(sys.argv[2], sys.argv[3])
        elif action == "--quote" and len(sys.argv) > 4:
            quote_patch(sys.argv[2], sys.argv[3], float(sys.argv[4]))
        elif action == "--reject" and len(sys.argv) > 4:
            reject_patch(sys.argv[2], sys.argv[3], sys.argv[4])
        elif action == "--paid" and len(sys.argv) > 3:
            mark_patch_paid(sys.argv[2], sys.argv[3])
        elif action == "--submit":
            custom_arg = sys.argv[2] if len(sys.argv) > 2 else None
            submit_result_from_photoshop(custom_arg)
        else:
            print("Usage:")
            print("  python text_retouch_engine.py --review <session_id> <patch_id>")
            print("  python text_retouch_engine.py --quote <session_id> <patch_id> <price>")
            print("  python text_retouch_engine.py --reject <session_id> <patch_id> <reason>")
            print("  python text_retouch_engine.py --paid <session_id> <patch_id>")
            print("  python text_retouch_engine.py --submit")
    else:
        print("Text-Retouch Engine v3 (New Pay-First Flow)")
