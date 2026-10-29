Add-Type -AssemblyName System.Drawing, System.Windows.Forms

# รับค่าไฟล์จากการลากวาง
$filePath = $args[0]
$noPrice = $args[1] -eq "-noPrice"
$givenPrice = $null

if ($args[1] -eq "-price" -and $args[2]) {
    $givenPrice = ($args[2] -replace '[^\d.]', '')
} elseif ($args[1] -and $args[1] -ne "-noPrice" -and ($args[1] -match '^\d+(\.\d{1,2})?$')) {
    $givenPrice = $args[1]
}

if (-not $filePath) {
    [System.Windows.Forms.MessageBox]::Show("กรุณาลากไฟล์ภาพมาวางที่ไอคอนนี้เพื่อส่งงาน", "PrivateSend")
    exit
}

# โหมด PrivateSend: ทำงานอัปโหลดส่งงานลับเพื่อสร้างลิงก์ download.html

# 1. ตรวจสอบประเภทไฟล์
$extension = [System.IO.Path]::GetExtension($filePath).ToLower()
$isImage = $extension -match "\.(jpg|jpeg|png|gif|bmp|webp)"
$isPdf = $extension -eq ".pdf"

# ตั้งค่าประเภทไฟล์ และใช้ไฟล์ต้นฉบับในการอัปโหลด
$fileToUpload = $filePath
$fileTypeParam = "file"
if ($isImage) { $fileTypeParam = "img" }
elseif ($isPdf) { $fileTypeParam = "pdf" }

# 2. ขอราคางาน (ข้ามหากเป็น -noPrice หรือระบุราคามาแล้ว) บังคับให้กรอกเฉพาะตัวเลขเท่านั้น
$price = "0"
if ($null -ne $givenPrice -and $givenPrice -ne "") {
    $price = $givenPrice
    Write-Host "💰 ยอดเรียกเก็บ (ระบุจากระบบ): $price บาท" -ForegroundColor Green
} elseif (-not $noPrice) {
    Write-Host "💰 ยอดเรียกเก็บ (บาท) [รอ 6 วิ หรือพิมพ์ราคา]: " -NoNewline
    $startTime = Get-Date
    $timeout = 6
    $inputStarted = $false

    try {
        # รอตรวจจับการกดปุ่มภายใน 6 วินาที
        while (((Get-Date) - $startTime).TotalSeconds -lt $timeout) {
            if ([Console]::KeyAvailable) {
                $inputStarted = $true
                break
            }
            Start-Sleep -Milliseconds 100
        }

        if (-not $inputStarted) {
            Write-Host "0 (อัตโนมัติ)"
            $price = "0"
        }
        else {
            # บังคับรับเฉพาะตัวเลข 0-9 และจุดทศนิยมเท่านั้น
            $buffer = ""
            while ($true) {
                $keyInfo = [Console]::ReadKey($true)
                if ($keyInfo.Key -eq [ConsoleKey]::Enter) {
                    Write-Host ""
                    break
                }
                elseif ($keyInfo.Key -eq [ConsoleKey]::Backspace) {
                    if ($buffer.Length -gt 0) {
                        $buffer = $buffer.Substring(0, $buffer.Length - 1)
                        Write-Host -NoNewline "`b `b"
                    }
                }
                elseif ($keyInfo.KeyChar -match '^[0-9]$') {
                    $buffer += $keyInfo.KeyChar
                    Write-Host -NoNewline $keyInfo.KeyChar
                }
                elseif ($keyInfo.KeyChar -eq '.' -and -not $buffer.Contains('.')) {
                    if ($buffer.Length -eq 0) {
                        $buffer = "0."
                        Write-Host -NoNewline "0."
                    } else {
                        $buffer += "."
                        Write-Host -NoNewline "."
                    }
                }
                # ตัวอักษรและสัญลักษณ์อื่นๆ จะถูกตัดทิ้ง ไม่แสดงบนหน้าจอ
            }

            $price = ($buffer -replace '[^\d.]', '')
            if ([string]::IsNullOrWhiteSpace($price)) {
                $price = "0"
            }
        }
    }
    catch {
        # กรณีรันในสภาพแวดล้อมที่ไม่รองรับ Console Key (Fallback)
        $raw = Read-Host
        $price = ($raw -replace '[^\d.]', '')
        if ([string]::IsNullOrWhiteSpace($price)) { $price = "0" }
    }
}

# 3. ตรวจสอบและอัปโหลด (ใช้ Python เพื่อความเสถียรสูงสุด)
Write-Host "กำลังอัปโหลด (Uploading)..." -ForegroundColor Yellow

# ใช้ runtime เดียวกับ local watcher เพื่อรักษา upload.py และ signature flow เดิม
# endpoint นี้สร้างลิงก์ download.html พร้อมราคาและคัดลอกลง Clipboard ให้
# โหมด -noPrice คงข้อความตัวอย่างแบบเดิมไว้ จึงข้าม endpoint นี้
if (-not $noPrice) {
    try {
        $legacyPayload = @{
            path = (Resolve-Path -LiteralPath $fileToUpload).Path
            amount = $price
        } | ConvertTo-Json -Compress
        $legacyResult = Invoke-RestMethod -Uri 'http://127.0.0.1:5000/send-work-link' -Method Post `
            -ContentType 'application/json; charset=utf-8' -Body $legacyPayload -TimeoutSec 120 -ErrorAction Stop
        if ($legacyResult.success -and $legacyResult.url) {
            Write-Host "อัปโหลดสำเร็จผ่าน $($legacyResult.source)" -ForegroundColor Green
            Write-Host "คัดลอกลิงก์ download.html พร้อมราคา $($legacyResult.amount) บาท ลง Clipboard แล้ว" -ForegroundColor Cyan
            Write-Host $legacyResult.url
            exit 0
        }
        $legacyError = [string]$legacyResult.error
        if ([string]::IsNullOrWhiteSpace($legacyError)) {
            $legacyError = 'ไม่ได้รับลิงก์ download.html จากระบบอัปโหลด'
        }
        throw $legacyError
    } catch {
        Write-Host "ระบบอัปโหลดในเครื่องไม่พร้อม ใช้ตัวอัปโหลดสำรอง: $($_.Exception.Message)" -ForegroundColor DarkYellow
    }
}

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

# แปลง URL ให้ถูกรูปแบบ
if ($uploadUrl -match "^fb_(.+)$") {
    # Firebase format: fb_12345_abcd -> ส่งตรงไป (download.html จะแปลงเอง)
    $fullUrl = $uploadUrl
} elseif ($uploadUrl -match "^tf_(.+)$") {
    # TmpFiles format: tf_123456 -> https://tmpfiles.org/123456
    $fileId = $Matches[1]
    $fullUrl = "https://tmpfiles.org/$fileId"
} elseif ($uploadUrl -match "^https?://") {
    # URL เต็มจาก Litterbox/Uguu
    $fullUrl = $uploadUrl
} else {
    # Fallback: ถือว่าเป็น file ID ของ Litterbox
    $fullUrl = $uploadUrl
}

$EW_SIGN_SALT = "EW_SALT_2026_SECURE_KEY"
function Get-LinkSignature($dVal, $expVal, $priceVal) {
    $normPrice = "{0:F2}" -f [double]($priceVal -as [double])
    $payload = "$($dVal):$($normPrice):$($expVal):$($EW_SIGN_SALT)"
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($payload)
    $hash = [System.Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    return [BitConverter]::ToString($hash).Replace("-","").ToLower().Substring(0, 12)
}

$b64Url = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($fullUrl))
$escapedB64 = [Uri]::EscapeDataString($b64Url)

if ($noPrice) {
    # Format สำหรับ Screenshot ตัวอย่าง (price = 0)
    $sig = Get-LinkSignature $b64Url $timestamp 0
    $viewUrl = "$($baseUrl)?d=$($escapedB64)&exp=$($timestamp)&type=$($fileTypeParam)&price=0&s=$sig"
    $message = "🧩ตัวอย่างงานของท่านเสร็จแล้ว!`n$($viewUrl)"
} else {
    # Format ปกติพร้อมเก็บเงิน
    $sig = Get-LinkSignature $b64Url $timestamp $price
    $viewUrl = "$($baseUrl)?d=$($escapedB64)&exp=$($timestamp)&type=$($fileTypeParam)&price=$price&s=$sig"
    $message = "✅เสร็จแล้ว!`n$($viewUrl)"
}

Set-Clipboard -Value $message
Write-Host "- คัดลอกลิงก์ลง Clipboard เรียบร้อยแล้ว" -ForegroundColor Cyan

