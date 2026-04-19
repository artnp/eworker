Add-Type -AssemblyName System.Drawing, System.Windows.Forms

# รับค่าไฟล์จากการลากวาง
$filePath = $args[0]
$noPrice = $args[1] -eq "-noPrice"

if (-not $filePath) {
    [System.Windows.Forms.MessageBox]::Show("กรุณาลากไฟล์ภาพมาวางที่ไอคอนนี้เพื่อส่งงาน", "PrivateSend")
    exit
}

# 1. ตรวจสอบประเภทไฟล์
$extension = [System.IO.Path]::GetExtension($filePath).ToLower()
$isImage = $extension -match "\.(jpg|jpeg|png|gif|bmp|webp)"
$isPdf = $extension -eq ".pdf"

# ตั้งค่าประเภทไฟล์ และใช้ไฟล์ต้นฉบับในการอัปโหลด
$fileToUpload = $filePath
$fileTypeParam = "file"
if ($isImage) { $fileTypeParam = "img" }
elseif ($isPdf) { $fileTypeParam = "pdf" }

# 2. ขอราคางาน (ข้ามหากเป็น -noPrice)
$price = "0"
if (-not $noPrice) {
    Write-Host "💰 ยอดเรียกเก็บ (บาท) [รอ 6 วิ หรือพิมพ์ราคา]: " -NoNewline
    $startTime = Get-Date
    $timeout = 6
    $inputStarted = $false

    while (((Get-Date) - $startTime).TotalSeconds -lt $timeout) {
        if ([Console]::KeyAvailable) {
            $price = Read-Host
            $inputStarted = $true
            break
        }
        Start-Sleep -Milliseconds 100
    }

    if (-not $inputStarted) {
        Write-Host "0 (อัตโนมัติ)"
    }
    elseif ([string]::IsNullOrWhiteSpace($price)) {
        $price = "0"
    }
}

# 3. ตรวจสอบและอัปโหลด (ใช้ Python เพื่อความเสถียรสูงสุด)
Write-Host "กำลังอัปโหลด (Uploading)..." -ForegroundColor Yellow

$expiryHours = 1
$timestamp = [DateTimeOffset]::Now.AddHours($expiryHours).ToUnixTimeMilliseconds()

# ตรวจสอบและติดตั้งโมดูลที่จำเป็น
Write-Host "- กำลังตรวจสอบความพร้อมของระบบ... " -NoNewline
python -c "import requests, PIL" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "กำลังติดตั้งโมดูลเพิ่มเติม..." -ForegroundColor Cyan
    python -m pip install requests Pillow --quiet
}
else {
    Write-Host "พร้อมใช้งาน" -ForegroundColor Green
}

# เรียกใช้ Python script เพื่ออัปโหลด
$scriptPath = Join-Path $PSScriptRoot "upload.py"
$uploadResultJson = python "$scriptPath" "$fileToUpload"
$result = $uploadResultJson | ConvertFrom-Json

if ($result.url) {
    $uploadUrl = $result.url
    Write-Host "- ส่งผ่านระบบ: $($result.source) " -NoNewline
    Write-Host "สำเร็จ" -ForegroundColor Green
}
else {
    Write-Host "ล้มเหลว" -ForegroundColor Red
    [System.Windows.Forms.MessageBox]::Show("ไม่สามารถอัปโหลดไฟล์ได้: $($result.error)", "Upload Error")
    if ($tempPath) { Remove-Item $tempPath -ErrorAction SilentlyContinue }
    exit
}

# 4. สร้าง URL และ Copy ลง Clipboard
$baseUrl = "https://artnp.github.io/eworker/download.html"
$b64Url = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($uploadUrl))
$viewUrl = "$($baseUrl)?d=$($b64Url)&exp=$($timestamp)&type=$($fileTypeParam)"

if ($noPrice) {
    # Format สำหรับ Screenshot ตัวอย่าง
    $message = "🧩ตัวอย่างงานของท่านเสร็จแล้ว!`n$($viewUrl)"
} else {
    # Format ปกติพร้อมเก็บเงิน
    $viewUrl += "&price=$price"
    $message = "$($viewUrl)"
}

Set-Clipboard -Value $message
Write-Host "- คัดลอกลิงก์ลง Clipboard เรียบร้อยแล้ว" -ForegroundColor Cyan

