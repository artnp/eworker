import os
import sys
import psutil

print("=" * 45)
print("  กำลังปิดระบบ AI Hub Watcher & Server...")
print("=" * 45)

killed_count = 0

# 1. Kill any python processes running auto_donate_watcher.py
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = ' '.join(proc.info.get('cmdline') or [])
        if 'auto_donate_watcher.py' in cmdline and proc.pid != os.getpid():
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
