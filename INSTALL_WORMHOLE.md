# การติดตั้ง Wormhole.app Support

Wormhole.app เป็นบริการอัพโหลดไฟล์ที่มี **end-to-end encryption** และ **auto-expire links** 

## ⚠️ ข้อแม้:
- ต้องติดตั้ง Node.js + wormhole-cli (~250MB)
- ใช้เวลาอัพโหลดนานกว่าบริการอื่น (เพราะใช้ Puppeteer)
- **ไม่แนะนำถ้าคุณไม่ได้ใช้ Wormhole เป็นประจำ**

## 📦 วิธีติดตั้ง:

### 1. ติดตั้ง Node.js (ถ้ายังไม่มี)
ดาวน์โหลดจาก: https://nodejs.org/

### 2. ติดตั้ง wormhole-cli
```powershell
# Clone repository
git clone https://github.com/Mimickal/wormhole-cli.git
cd wormhole-cli

# ติดตั้ง dependencies
npm ci

# ติดตั้ง globally
npm install -g
```

### 3. ทดสอบ
```powershell
wormhole-cli --version
```

## ✅ หลังติดตั้งเสร็จ:

ระบบจะใช้ Wormhole.app อัตโนมัติเป็น **fallback ลำดับ 1** (หลัง Litterbox)

ลำดับการอัพโหลด:
1. **Litterbox** (เร็ว, 1hr)
2. **Wormhole** (ช้ากว่า, encrypted, auto-expire)
3. **Uguu** (เร็ว, 1hr)

## ⚡ ไม่ต้องติดตั้งก็ได้!

ถ้าไม่ติดตั้ง Wormhole ระบบจะข้ามไปใช้ Uguu.se ทันที (ซึ่งก็ปลอดภัยดีอยู่แล้ว)
