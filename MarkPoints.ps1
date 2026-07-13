param([string]$filePath)

Add-Type -AssemblyName System.Windows.Forms

if (-not $filePath) {
    [System.Windows.Forms.MessageBox]::Show("กรุณาลากไฟล์ภาพหรือ PDF มาวางที่ไอคอนนี้", "มาร์คจุดที")
    exit
}

# ตรวจสอบประเภทไฟล์
$extension = [System.IO.Path]::GetExtension($filePath).ToLower()
$isImage = $extension -match "\.(jpg|jpeg|png|gif|bmp|webp)"
$isPdf = $extension -eq ".pdf"

if (-not $isImage -and -not $isPdf) {
    [System.Windows.Forms.MessageBox]::Show("กรุณาลากไฟล์รูปภาพหรือ PDF เท่านั้น", "มาร์คจุดที")
    exit
}

$fileTypeParam = if ($isImage) { "image" } else { "pdf" }

Write-Host "══════════════════════════════" -ForegroundColor Cyan
Write-Host "      มาร์คจุดที v1.0" -ForegroundColor Cyan
Write-Host "══════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. อัปโหลดไฟล์ผ่าน Python
Write-Host "📤 กำลังอัปโหลดไฟล์..." -ForegroundColor Yellow
Write-Host "   ไฟล์: $(Split-Path $filePath -Leaf)" -ForegroundColor Gray

$scriptPath = Join-Path $PSScriptRoot "upload.py"
$uploadOutput = python "$scriptPath" "$filePath" 2>&1
$uploadResultJson = $uploadOutput | Select-String -Pattern '^\{"' | Select-Object -First 1 -ExpandProperty Line

if (-not $uploadResultJson) {
    Write-Host "❌ อัปโหลดล้มเหลว (ไม่มีผลลัพธ์จาก Python)" -ForegroundColor Red
    Write-Host "   ตรวจสอบว่า Python และ requests/Pillow ได้ติดตั้งแล้ว" -ForegroundColor Red
    [System.Windows.Forms.MessageBox]::Show("ไม่สามารถอัปโหลดได้ กรุณาตรวจสอบ Python", "มาร์คจุดที")
    exit
}

$result = $uploadResultJson | ConvertFrom-Json

if (-not $result.url) {
    Write-Host "❌ อัปโหลดล้มเหลว: $($result.error)" -ForegroundColor Red
    [System.Windows.Forms.MessageBox]::Show("ไม่สามารถอัปโหลดไฟล์ได้: $($result.error)", "มาร์คจุดที")
    exit
}

Write-Host "✅ อัปโหลดสำเร็จ" -ForegroundColor Green
Write-Host "   ผ่าน: $($result.source)" -ForegroundColor Gray

# 2. สร้าง Session ID (รูปแบบเดียวกับ JS: Date.now().toString(36) + Math.random().toString(36).substr(2))
Write-Host "📝 กำลังสร้างเซสชัน..." -ForegroundColor Yellow

function ConvertTo-Base36 {
    param([long]$value)
    $chars = '0123456789abcdefghijklmnopqrstuvwxyz'
    if ($value -eq 0) { return '0' }
    $result = ''
    while ($value -gt 0) {
        $remainder = $value % 36
        $result = $chars[$remainder] + $result
        $value = [math]::Floor($value / 36)
    }
    return $result
}

$now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$timestampPart = ConvertTo-Base36 -value $now

# สร้าง random base36 8 ตัว (เทียบเท่า Math.random().toString(36).substr(2))
$chars = '0123456789abcdefghijklmnopqrstuvwxyz'
$randomPart = -join (1..8 | ForEach-Object { $chars[(Get-Random -Maximum 36)] })
$sessionId = $timestampPart + $randomPart

# 3. สร้าง Session ใน Firebase ผ่าน REST API
$firebaseUrl = "https://chat-11059-default-rtdb.asia-southeast1.firebasedatabase.app"
$nowMs = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
$expiresAt = [DateTimeOffset]::UtcNow.AddHours(1).ToUnixTimeMilliseconds()

$sessionData = @{
    fileUrl = $result.url
    fileType = $fileTypeParam
    createdAt = $nowMs
    expiresAt = $expiresAt
    markers = @{}
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "$firebaseUrl/annotations/$sessionId.json" -Method Put -Body $sessionData -ContentType "application/json" -ErrorAction Stop
    Write-Host "✅ สร้างเซสชันสำเร็จ" -ForegroundColor Green
} catch {
    Write-Host "❌ สร้างเซสชันล้มเหลว: $_" -ForegroundColor Red
    [System.Windows.Forms.MessageBox]::Show("ไม่สามารถสร้างเซสชันได้ โปรดตรวจสอบ Firebase`n$_", "มาร์คจุดที")
    exit
}

# 4. เปิดเบราว์เซอร์ไปที่ send.html พร้อม session ID
$sendUrl = "https://artnp.github.io/eworker/send.html?id=$sessionId"
Write-Host ""
Write-Host "🌐 กำลังเปิดเบราว์เซอร์..." -ForegroundColor Yellow
Write-Host "   $sendUrl" -ForegroundColor Gray
Start-Process $sendUrl

Write-Host ""
Write-Host "✅ เสร็จสิ้น! สามารถเริ่มมาร์คจุดได้เลย" -ForegroundColor Green
