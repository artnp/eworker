import os
import sys
import psutil

import urllib.request
import json

print("=" * 45)
print("  กำลังปิดระบบ AI Hub Watcher & Server...")
print("=" * 45)

# 0. แจ้ง Firebase ทันทีว่าร้านค้า Offline แล้ว
try:
    hb_url = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/store_status.json"
    hb_data = json.dumps({"online": False, "lastSeen": 0, "source": "system_closed"}).encode('utf-8')
    req = urllib.request.Request(hb_url, data=hb_data, method='PUT', headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=3)
    print("📡 ส่งสัญญาณแจ้ง Firebase: ปิดสถานะร้านค้า (Offline) เรียบร้อย")
except Exception:
    pass

killed_count = 0

# 1. Kill any python processes running auto_donate_watcher.py
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = ' '.join(proc.info.get('cmdline') or [])
        if ('auto_donate_watcher.py' in cmdline or 'watcher_gui.ps1' in cmdline) and proc.pid != os.getpid():
            print(f"[KILL] สั่งปิดโปรเซส PID {proc.pid} ({proc.info.get('name')})")
            proc.kill()
            killed_count += 1
    except Exception:
        pass

# 2. Kill any process listening on port 5000
try:
    for conn in psutil.net_connections():
        try:
            if conn.laddr.port == 5000 and conn.pid and conn.pid != os.getpid():
                p = psutil.Process(conn.pid)
                print(f"[KILL] สั่งปิดโปรเซสพอร์ต 5000 PID {conn.pid} ({p.name()})")
                p.kill()
                killed_count += 1
        except Exception:
            pass
except Exception:
    pass

print("=" * 45)
if killed_count > 0:
    print(f"✅ ปิดการทำงานสำเร็จทั้งหมด {killed_count} โปรเซส (ระบบหยุดทำงานสนิท 100%)")
else:
    print("ℹ️ ไม่พบโปรเซส auto_donate_watcher ที่ทำงานค้างอยู่ (ระบบปิดอยู่แล้ว)")
print("=" * 45)
