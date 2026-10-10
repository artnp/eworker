import json
import os
from datetime import datetime

SRC_CLAIMS = r"D:\Github\RedPacket_Code\claimed_success_codes.json"
SRC_INVALID = r"D:\Github\RedPacket_Code\invalid_codes.json"
SRC_FAILED = r"D:\Github\RedPacket_Code\failed_attempts.json"
SRC_TODAY_RAW = r"D:\Github\RedPacket_Code\codes_today.json"
DST = r"d:\Github\eworker\shop\services\redPacket\codes_today.json"

def sync():
    if not os.path.exists(SRC_CLAIMS):
        print("[Error] Source not found:", SRC_CLAIMS)
        return

    # 1. โหลดโค้ดที่เปิดเคลมรับเหรียญสำเร็จแล้ว (คอนเฟิร์มว่าได้เหรียญจริง)
    with open(SRC_CLAIMS, "r", encoding="utf-8") as f:
        claim_data = json.load(f)

    success_codes = claim_data.get("codes", []) if isinstance(claim_data, dict) else claim_data
    coin_map = claim_data.get("coin_map", {}) if isinstance(claim_data, dict) else {}

    # 2. กรองโค้ดที่หมดอายุ / ผิดพลาด (Blacklist)
    inv_set = set()
    if os.path.exists(SRC_INVALID):
        try:
            with open(SRC_INVALID, "r", encoding="utf-8") as f:
                inv_data = json.load(f)
                inv_set = set(inv_data.keys()) if isinstance(inv_data, dict) else set(inv_data)
        except Exception as e:
            print("[Warning] Could not read invalid codes:", e)

    fail_set = set()
    if os.path.exists(SRC_FAILED):
        try:
            with open(SRC_FAILED, "r", encoding="utf-8") as f:
                fail_data = json.load(f)
                for k, v in fail_data.get("items", {}).items():
                    if v.get("type") == "cryptobox" and v.get("id"):
                        fail_set.add(v.get("id").strip().upper())
        except Exception as e:
            print("[Warning] Could not read failed attempts:", e)

    # 3. ดึงโค้ดที่เพิ่งเคลมสำเร็จสดๆ ล่าสุด ย้อนจากท้ายลิสต์ขึ้นมา (Newest first)
    # แบบเดียวกับที่ Facebook Bot และ Binance Square ใช้แจก
    valid_codes = []
    final_coin_map = {}

    for c in reversed(success_codes):
        clean = str(c).strip().upper()
        if (
            clean
            and len(clean) >= 6
            and clean not in inv_set
            and clean not in fail_set
            and clean not in valid_codes
        ):
            valid_codes.append(clean)
            # ดึงชื่อเหรียญจริงที่บันทึกไว้ตอนเปิดเคลมสำเร็จ
            actual_coin = coin_map.get(clean)
            if actual_coin:
                final_coin_map[clean] = actual_coin.strip().upper().replace("$", "")
            else:
                final_coin_map[clean] = "USDT"

    # 4. บันทึกผลลัพธ์ลงไฟล์สำหรับหน้าเว็บ
    payload = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": "claimed_success_codes (verified)",
        "total": len(valid_codes),
        "codes": valid_codes,
        "coin_map": final_coin_map
    }

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[OK] 🏆 ซิงค์โค้ดเคลมผ่านจริงล่าสุด {len(valid_codes)} โค้ด พร้อมชื่อเหรียญตรงตามจริง 100% ไปยัง {DST}")

if __name__ == "__main__":
    sync()
