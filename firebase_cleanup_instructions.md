# วิธีตั้งค่าลบข้อมูล Firebase อัตโนมัติ

## วิธีที่ 1: ใช้ Firebase Rules (แนะนำ - ง่ายที่สุด)

ตั้งค่าให้ข้อมูลที่หมดอายุไม่สามารถอ่านได้:

```json
{
  "rules": {
    "annotations": {
      "$sessionId": {
        ".read": "data.child('expiresAt').val() > now",
        ".write": "data.child('expiresAt').val() > now || !data.exists()"
      }
    }
  }
}
```

**ข้อดี**: ไม่ต้องเขียนโค้ดเพิ่ม  
**ข้อเสีย**: ข้อมูลยังอยู่ใน Database (แต่อ่านไม่ได้)

---

## วิธีที่ 2: ใช้ Firebase Cloud Function (ลบจริง)

### ขั้นตอน:

1. ติดตั้ง Firebase CLI:
```bash
npm install -g firebase-tools
firebase login
```

2. Init Functions:
```bash
cd d:\Github\eworker
firebase init functions
```

3. สร้างไฟล์ `functions/index.js`:

```javascript
const functions = require('firebase-functions');
const admin = require('firebase-admin');
admin.initializeApp();

// ทุกวันเวลา 00:00 จะลบข้อมูลที่หมดอายุ
exports.cleanupExpiredSessions = functions.pubsub
  .schedule('0 0 * * *') // Cron: ทุกวันเที่ยงคืน
  .timeZone('Asia/Bangkok')
  .onRun(async (context) => {
    const db = admin.database();
    const now = Date.now();
    
    const snapshot = await db.ref('annotations').once('value');
    const data = snapshot.val();
    
    if (!data) return null;
    
    const deletePromises = [];
    
    for (const sessionId in data) {
      const session = data[sessionId];
      
      if (session.expiresAt && session.expiresAt < now) {
        console.log(`Deleting expired session: ${sessionId}`);
        deletePromises.push(
          db.ref(`annotations/${sessionId}`).remove()
        );
      }
    }
    
    await Promise.all(deletePromises);
    console.log(`Cleaned up ${deletePromises.length} expired sessions`);
    
    return null;
  });
```

4. Deploy:
```bash
firebase deploy --only functions
```

---

## วิธีที่ 3: ใช้ PHP Cron Job (ถ้าไม่ต้องการ Firebase Functions)

สร้างไฟล์ `d:\Github\eworker\api\cleanup_firebase.php`:

```php
<?php
// Run this via cron: */10 * * * * php cleanup_firebase.php

$firebaseUrl = 'https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app';
$now = time() * 1000; // milliseconds

// Fetch all sessions
$ch = curl_init("$firebaseUrl/annotations.json");
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
$response = curl_exec($ch);
curl_close($ch);

$sessions = json_decode($response, true);

if (!$sessions) {
    exit("No sessions found\n");
}

$deletedCount = 0;

foreach ($sessions as $sessionId => $session) {
    if (isset($session['expiresAt']) && $session['expiresAt'] < $now) {
        // Delete session
        $ch = curl_init("$firebaseUrl/annotations/$sessionId.json");
        curl_setopt($ch, CURLOPT_CUSTOMREQUEST, 'DELETE');
        curl_exec($ch);
        curl_close($ch);
        
        echo "Deleted expired session: $sessionId\n";
        $deletedCount++;
    }
}

echo "Cleaned up $deletedCount expired sessions\n";
?>
```

ตั้ง Cron (Windows Task Scheduler):
```
ชื่อ: Firebase Cleanup
โปรแกรม: php.exe
พารามิเตอร์: d:\Github\eworker\api\cleanup_firebase.php
ทำซ้ำ: ทุก 10 นาที
```

---

## สรุปแนะนำ:

- **ถ้าใช้ Firebase ฟรี** → ใช้ **วิธีที่ 1** (Firebase Rules)
- **ถ้าต้องการลบจริง** → ใช้ **วิธีที่ 2** (Cloud Functions) หรือ **วิธีที่ 3** (PHP Cron)

ปัจจุบันระบบมี:
✅ ไฟล์รูป/PDF ลบใน 1 ชม. (Litterbox/tmpfiles)
✅ ข้อมูล Firebase มี expiresAt
✅ แสดง countdown timer
✅ แจ้งเตือนเมื่อหมดอายุ

เหลือแค่ตั้งค่าลบ Firebase ตามวิธีที่เลือก! 🚀
