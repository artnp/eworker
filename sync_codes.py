import json
import os
import hashlib

SRC_CODES = r"D:\Github\RedPacket_Code\codes_today.json"
SRC_CLAIMS = r"D:\Github\RedPacket_Code\claimed_success_codes.json"
DST = r"d:\Github\eworker\shop\services\redPacket\codes_today.json"

POPULAR_COINS = ["USDT", "BNB", "FDUSD", "PEPE", "SHIB", "DOGE", "SOL", "ETH", "BTTC"]

def get_stable_coin(code: str) -> str:
    h = int(hashlib.md5(code.encode("utf-8")).hexdigest(), 16)
    return POPULAR_COINS[h % len(POPULAR_COINS)]

def sync():
    if not os.path.exists(SRC_CODES):
        print("Source not found:", SRC_CODES)
        return

    with open(SRC_CODES, "r", encoding="utf-8") as f:
        data = json.load(f)

    coin_map = {}
    if os.path.exists(SRC_CLAIMS):
        try:
            with open(SRC_CLAIMS, "r", encoding="utf-8") as cf:
                claim_data = json.load(cf)
                coin_map = claim_data.get("coin_map", {})
        except Exception as e:
            print("Error loading claims:", e)

    final_coin_map = {}
    for c in data.get("codes", []):
        if c in coin_map and coin_map[c]:
            final_coin_map[c] = coin_map[c]
        else:
            final_coin_map[c] = get_stable_coin(c)

    data["coin_map"] = final_coin_map

    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[OK] Synced {len(data.get('codes', []))} codes with coin names to {DST}")

if __name__ == "__main__":
    sync()
