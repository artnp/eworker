$OutputEncoding = [console]::InputEncoding = [console]::OutputEncoding = New-Object System.Text.UTF8Encoding

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     สร้างสลิปโอนเงินพร้อมเพย์ (Offline)      " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# บังคับพิมพ์ได้เฉพาะตัวเลขและจุดทศนิยมเท่านั้นแบบ Real-time (กดปุ่มตัวหนังสือจะไม่ติด)
function Get-NumericOnlyInput {
    param(
        [string]$Prompt = "ใส่จำนวนเงิน (เช่น 250 หรือ 0.1): "
    )
    Write-Host -NoNewline $Prompt -ForegroundColor Yellow
    $val = ""
    while ($true) {
        $key = [Console]::ReadKey($true)
        if ($key.Key -eq [ConsoleKey]::Enter) {
            if ($val.Length -gt 0 -and $val -ne "." -and [decimal]$val -gt 0) {
                Write-Host ""
                return $val
            }
        }
        elseif ($key.Key -eq [ConsoleKey]::Backspace) {
            if ($val.Length -gt 0) {
                $val = $val.Substring(0, $val.Length - 1)
                Write-Host -NoNewline "`b `b"
            }
        }
        elseif ($key.KeyChar -ge '0' -and $key.KeyChar -le '9') {
            # ตรวจสอบทศนิยมไม่ให้เกิน 2 ตำแหน่ง
            if ($val -match '\.\d{2}$') {
                continue
            }
            if ($val.Length -lt 10) {
                $val += $key.KeyChar
                Write-Host -NoNewline $key.KeyChar
            }
        }
        elseif ($key.KeyChar -eq '.') {
            # อนุญาตให้ใส่จุดทศนิยมได้เพียง 1 ครั้ง
            if (-not $val.Contains('.') -and $val.Length -lt 10) {
                if ($val.Length -eq 0) {
                    $val += "0."
                    Write-Host -NoNewline "0."
                } else {
                    $val += "."
                }
            }
        }
    }
}

# ฟังก์ชันคำนวณ EMVCo PromptPay Payload ตามมาตรฐานสากล
function Get-PromptPayPayload {
    param(
        [string]$Target = "0988573074",
        [decimal]$Amount = 0
    )
    $cleanTarget = $Target -replace '[^0-9]', ''
    if ($cleanTarget.Length -ge 13) {
        $tf = "02" + $cleanTarget.Length.ToString("D2") + $cleanTarget
    } else {
        if ($cleanTarget.StartsWith("0")) { $cleanTarget = $cleanTarget.Substring(1) }
        $phone = "0066" + $cleanTarget
        $tf = "01" + $phone.Length.ToString("D2") + $phone
    }

    $tag29Data = "0016A000000677010111" + $tf
    $tag29 = "29" + $tag29Data.Length.ToString("D2") + $tag29Data

    $hasAmount = $Amount -gt 0
    $payload = "000201" + $(if ($hasAmount) { "010212" } else { "010211" }) + $tag29 + "5303764"
    if ($hasAmount) {
        $amtStr = "{0:F2}" -f $Amount
        $payload += "54" + $amtStr.Length.ToString("D2") + $amtStr
    }
    $payload += "5802TH6304"

    # CRC16-CCITT
    $crc = 0xFFFF
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($payload)
    foreach ($b in $bytes) {
        $x = (($crc -shr 8) -bxor $b) -band 0xFF
        $x = $x -bxor ($x -shr 4)
        $crc = (($crc -shl 8) -bxor ($x -shl 12) -bxor ($x -shl 5) -bxor $x) -band 0xFFFF
    }
    return $payload + $crc.ToString("X4")
}

$amount = ""
try {
    $amount = Get-NumericOnlyInput -Prompt "ใส่จำนวนเงิน (เช่น 250 หรือ 0.1): "
}
catch {
    # สำรองกรณีไม่ได้รันใน Interactive Console
    while ($true) {
        $inputVal = Read-Host "ใส่จำนวนเงิน (เช่น 250 หรือ 0.1)"
        if ($inputVal) {
            $trimmed = $inputVal.Trim()
            if ($trimmed -match '^\d+(\.\d{1,2})?$' -and [decimal]$trimmed -gt 0) {
                $amount = $trimmed
                break
            }
        }
        Write-Host ">> กรุณากรอกเฉพาะตัวเลขเท่านั้น (เช่น 250 หรือ 0.1)" -ForegroundColor Red
    }
}

$amountNumber = [decimal]$amount
$formattedAmount = "{0:N2}" -f $amountNumber
$amountForUrl = if ($amountNumber % 1 -eq 0) { [int]$amountNumber } else { "{0:F2}" -f $amountNumber }

Write-Host ""
Write-Host "กำลังสร้างรูปภาพบิลใบเสร็จ..." -ForegroundColor Yellow

$tempDir = [System.IO.Path]::GetTempPath()
$randId = [System.Guid]::NewGuid().ToString("N").Substring(0, 8)
$qrTempFile = Join-Path $tempDir "temp_qr_$randId.png"
$htmlPath = Join-Path $tempDir "temp_bill_$randId.html"
$outPng = Join-Path $tempDir "temp_slip_$randId.png"
$outLog = Join-Path $tempDir "temp_edge_out_$randId.log"
$errLog = Join-Path $tempDir "temp_edge_err_$randId.log"

try {
    # 1. คำนวณ PromptPay Payload และดาวน์โหลด QR Code พร้อมเพย์ (มี Fallback หลายช่องทาง)
    $payload = Get-PromptPayPayload -Target "0988573074" -Amount $amountNumber
    $encPayload = [System.Uri]::EscapeDataString($payload)

    $qrUrls = @(
        "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=$encPayload&margin=10",
        "https://quickchart.io/qr?size=300&margin=2&text=$encPayload",
        "https://promptpay.io/0988573074/$amountForUrl.png"
    )

    $qrSuccess = $false
    foreach ($url in $qrUrls) {
        try {
            Invoke-WebRequest -Uri $url -OutFile $qrTempFile -UserAgent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" -TimeoutSec 6 -ErrorAction Stop
            if ((Test-Path $qrTempFile) -and (Get-Item $qrTempFile).Length -gt 100) {
                $qrSuccess = $true
                break
            }
        } catch {}
    }

    if (-not $qrSuccess) {
        throw "ไม่สามารถสร้างหรือดาวน์โหลดภาพ QR Code ได้ (กรุณาตรวจสอบการเชื่อมต่ออินเทอร์เน็ต)"
    }
    
    # 2. แปลงรูป QR code เป็น Base64
    $qrBytes = [System.IO.File]::ReadAllBytes($qrTempFile)
    $qrBase64 = [System.Convert]::ToBase64String($qrBytes)
    
    # 3. สร้าง HTML ดีไซน์กระดาษใบเสร็จสลิปธนาคาร / สมุดบัญชี
    $html = @"
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }
  html, body {
    width: 250px;
    height: 340px;
    overflow: hidden;
    background: #ffffff;
    font-family: 'Tahoma', 'Leelawadee UI', 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .receipt-card {
    width: 250px;
    height: 340px;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    text-align: center;
  }
  .header-title {
    font-size: 13px;
    font-weight: normal;
    color: #222222;
    padding: 13px 10px 9px 10px;
    letter-spacing: 0.1px;
  }
  .dash-line {
    border: none;
    border-top: 1.5px dashed #aaaaaa;
    width: 100%;
    margin: 0;
  }
  .amount-section {
    padding: 7px 10px 6px 10px;
  }
  .service-label {
    font-size: 10px;
    color: #666666;
    margin-bottom: 2px;
    font-weight: normal;
  }
  .amount-val {
    font-family: 'Consolas', monospace;
    font-size: 27px;
    font-weight: 700;
    color: #000000;
    line-height: 1.15;
    letter-spacing: 0.5px;
  }
  .qr-label {
    font-size: 9.5px;
    color: #777777;
    margin-top: 2px;
  }
  .qr-section {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 5px 0;
  }
  .qr-image {
    width: 172px;
    height: 172px;
    display: block;
    image-rendering: -webkit-optimize-contrast;
  }
  .bottom-bar {
    width: 100%;
    height: 13px;
    background: #00a651;
  }
</style>
</head>
<body>
  <div class="receipt-card">
    <div class="content-body">
      <div class="header-title">สแกนจ่ายได้ทุกธนาคาร!</div>
      <div class="dash-line"></div>
      
      <div class="amount-section">
        <div class="service-label">ยอดชำระค่าบริการ</div>
        <div class="amount-val">฿ $formattedAmount</div>
        <div class="qr-label">( ยอดตาม QR Code )</div>
      </div>
      <div class="dash-line"></div>
      
      <div class="qr-section">
        <img src="data:image/png;base64,$qrBase64" class="qr-image" alt="QR Code">
      </div>
      <div class="dash-line"></div>
    </div>
    
    <div class="bottom-bar"></div>
  </div>
</body>
</html>
"@
    $html | Out-File -FilePath $htmlPath -Encoding utf8
    
    # 4. เรียก Microsoft Edge Headless เพื่อบันทึกภาพหน้าจอ
    $edgePath = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (-not (Test-Path $edgePath)) {
        $edgePath = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    }
    
    $edgeArgs = @(
        "--headless",
        "--screenshot=$outPng",
        "--window-size=250,340",
        "--hide-scrollbars",
        "--log-level=3",
        $htmlPath
    )
    
    $proc = Start-Process -FilePath $edgePath -ArgumentList $edgeArgs -NoNewWindow -RedirectStandardError $errLog -RedirectStandardOutput $outLog -PassThru -Wait
    
    if (-not (Test-Path $outPng)) {
        throw "ไม่สามารถบันทึกภาพสลิปจาก Edge ได้"
    }

    # 5. คัดลอกภาพสลิปลง Clipboard ของ Windows
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    
    $slipBytes = [System.IO.File]::ReadAllBytes($outPng)
    $clipStream = New-Object System.IO.MemoryStream(,$slipBytes)
    $clipImg = [System.Drawing.Image]::FromStream($clipStream)
    [System.Windows.Forms.Clipboard]::SetImage($clipImg)
    $clipImg.Dispose()
    $clipStream.Dispose()
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host " [OK] คัดลอกรูปภาพบิลลงคลิปบอร์ดแล้ว!" -ForegroundColor Green
    Write-Host " ยอดเงิน: ฿ $formattedAmount" -ForegroundColor Yellow
    Write-Host " สามารถกดวาง (Ctrl+V) ส่งในแชทได้ทันที" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Green
}
catch {
    Write-Host "เกิดข้อผิดพลาด: $_" -ForegroundColor Red
}
finally {
    # 6. ลบไฟล์ชั่วคราว
    if (Test-Path $qrTempFile) { Remove-Item $qrTempFile -Force -ErrorAction SilentlyContinue }
    if (Test-Path $htmlPath) { Remove-Item $htmlPath -Force -ErrorAction SilentlyContinue }
    if (Test-Path $outPng) { Remove-Item $outPng -Force -ErrorAction SilentlyContinue }
    if (Test-Path $outLog) { Remove-Item $outLog -Force -ErrorAction SilentlyContinue }
    if (Test-Path $errLog) { Remove-Item $errLog -Force -ErrorAction SilentlyContinue }
}

Write-Host ""
Start-Sleep -Seconds 3
