$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding
Write-Host "========================================"
Write-Host "         สร้างห้องแชท (GenRoom)           "
Write-Host "========================================"
Write-Host ""

$baseUrl = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app"

# 1. ตรวจสอบและล้างห้องที่ปิดแล้วใน Firebase
Write-Host "🧹 กำลังตรวจสอบและล้างข้อมูลห้องที่ปิดแล้วใน Firebase..." -ForegroundColor Yellow
try {
    $closedData = Invoke-RestMethod -Uri "$baseUrl/rooms/_closed_rooms.json" -Method Get -TimeoutSec 6 -ErrorAction SilentlyContinue
    if ($closedData -and ($closedData -is [PSCustomObject] -or $closedData -is [System.Collections.IDictionary])) {
        $count = 0
        foreach ($prop in $closedData.psobject.Properties) {
            $cId = $prop.Name
            Invoke-RestMethod -Uri "$baseUrl/rooms/$cId.json" -Method Delete -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
            $count++
        }
        # ล้างรายการ _closed_rooms
        Invoke-RestMethod -Uri "$baseUrl/rooms/_closed_rooms.json" -Method Delete -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
        Write-Host "✅ ล้างห้องที่ปิดแล้วใน Firebase สำเร็จ ($count ห้อง)" -ForegroundColor Green
    } else {
        Write-Host "✅ ไม่มีขยะห้องค้างใน Firebase (สะอาดเรียบร้อย)" -ForegroundColor Gray
    }
} catch {
    Write-Host "⚠️ ข้ามขั้นตอนล้าง Firebase: $_" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "กำลังสร้างห้องแชทใหม่..."

# สุ่ม Room ID อัตโนมัติ (8 ตัวอักษร)
$chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
$roomId = -join (1..8 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })

# เคลียร์ให้แน่ใจว่าห้องใหม่นี้สะอาด 100%
try {
    Invoke-RestMethod -Uri "$baseUrl/rooms/$roomId.json" -Method Delete -TimeoutSec 5 -ErrorAction SilentlyContinue | Out-Null
} catch {}

$publicDomain = "https://artnp.github.io/eworker/chat"
$publicUrl = "$publicDomain/?room=$roomId"
$localUrl = "http://127.0.0.1:5000/chat/?room=$roomId"

$msg = "✅ส่งงานในนี้ ปลอดภัยกว่า!`r`n$publicUrl"

Set-Clipboard -Value $msg

Write-Host "เสร็จเรียบร้อย! คัดลอกข้อความลงคลิปบอร์ดแล้ว" -ForegroundColor Green
Write-Host "คุณสามารถนำไปวาง (Ctrl+V) ให้ลูกค้าในแชทอื่นได้เลย: $publicUrl"
Write-Host ""
Write-Host "กำลังเปิดหน้าต่าง Edge ไปที่: $localUrl" -ForegroundColor Cyan

Start-Process "msedge.exe" $localUrl

Start-Sleep -Seconds 3
