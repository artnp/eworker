# eWorker Service Starter Template

ไฟล์แม่แบบมาตรฐาน (`shop/services/_template/index.html`) สำหรับใช้สร้างเครื่องมือหรือหน้าร้านค้าบริการใหม่ในเครือ `eWorker`

---

## 🌟 คุณสมบัติเด่นที่มีให้ในตัว
1. **Responsive Studio Layout**:
   - แบ่ง 2 ฝั่งชัดเจน (ฝั่งซ้ายเป็นแผงตั้งค่าและอัปโหลด / ฝั่งขวาเป็นพื้นที่แสดงผล Preview/Canvas)
   - รองรับหน้าจอมือถือและแท็บเล็ตอัตโนมัติ (สลับเป็นแนวดิ่ง พร้อมขนาดปุ่มที่กดง่ายด้วยนิ้วโป้ง)
2. **ปุ่มแอ็กชันลอยมุมล่างขวา (Floating Action Button)**:
   - สไตล์พรีเมียม `.btn-start-job` เหมือนกับหน้า `send.html`
   - เอฟเฟกต์ **Radar Pulse**, **Gradient Shift**, **Shimmer Light Sweep** และ **Rocket Bouncing**
   - **ล็อคตำแหน่งคงที่เสมอ (`position: fixed`)**: เลื่อนหน้าจอ สกอร์ล Canvas หรือซูมภาพ ปุ่มจะไม่ขยับหนี
   - **ซ่อนปุ่มอัตโนมัติ** จนกว่าลูกค้าจะอัปโหลดงาน/ไฟล์
3. **ระบบลากวางไฟล์ทั้งหน้าจอ (Full-Screen Drag & Drop)**:
   - สามารถลากไฟล์เอกสารหรือรูปภาพมาวางได้จากทุกจุดของหน้าต่างเบราว์เซอร์
   - มีหน้าต่างโอเวอร์เลย์การ์ดลอย (`pageDragOverlay`) ปรากฏขึ้นอัตโนมัติเมื่อมีการลากไฟล์เข้ามา
4. **ระบบชำระเงิน Beam Payment PromptPay QR อัตโนมัติ**:
   - สร้าง QR Code Dynamic PromptPay จาก Beam Checkout API
   - ตรวจจับยอดเงินเข้าอัตโนมัติผ่าน Beam Webhook & Firebase RTDB
   - มีปุ่มจำลองการทดสอบชำระเงินสำเร็จ (Admin Test Bypass) สำหรับการพัฒนา
   - เอฟเฟกต์พลุกระดาษ Confetti เมื่อยอดเงินเข้า
5. **ความปลอดภัย Client-Side**:
   - โค้ดทั้งหมดรันและประมวลผลบนเบราว์เซอร์ของลูกค้าโดยตรง ไฟล์ไม่หลุดออกนอกเครื่อง

---

## 🚀 วิธีนำแม่แบบไปสร้างบริการใหม่ (3 ขั้นตอน)

### 1. ทำสำเนาโฟลเดอร์
ก๊อปปี้โฟลเดอร์ `_template` แล้วเปลี่ยนชื่อเป็นชื่อบริการใหม่ เช่น `myNewTool`:
```bash
cp -r shop/services/_template shop/services/myNewTool
```

### 2. กำหนดค่าใน `SERVICE_CONFIG`
เปิดไฟล์ `shop/services/myNewTool/index.html` แล้วปรับแต่งส่วนหัวสคริปต์ (บรรทัด ~430):
```javascript
const SERVICE_CONFIG = {
    serviceName: "MyNewTool",            // ชื่อบริการ
    servicePriceThb: 5.00,                // ราคาค่าบริการ (บาท)
    beamWorkerUrl: "https://eworker-beam-pay.moonverse69.workers.dev",
    firebaseBase: "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app/temp_files/payment_requests"
};
```

### 3. ใส่ตรรกะประมวลผลใน `[STEP 3]` และ `[STEP 5]`
- ปรับแต่งการวาดผลลัพธ์ในฟังก์ชัน `renderCanvas()`
- ปรับแต่งการดาวน์โหลดในฟังก์ชัน `executeDownload()` (เช่น ดาวน์โหลดเป็น PDF หรือ JPG/PNG)

