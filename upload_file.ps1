# PowerShell Upload Script for File Hosting Services
# Usage: .\upload_file.ps1 -FilePath "path\to\file.jpg"

param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath
)

# Validate file exists
if (-not (Test-Path $FilePath)) {
    Write-Host "Error: File not found: $FilePath" -ForegroundColor Red
    exit 1
}

$fileName = Split-Path $FilePath -Leaf
$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)

Write-Host "`n- กำลังตรวจสอบความพร้อมของระบบ..." -NoNewline
Write-Host " พร้อมใช้งาน`n" -ForegroundColor Green

# Try uploading with multiple services
$uploadSuccess = $false
$resultUrl = $null

# Service 1: Litterbox (1 hour expiry)
try {
    Write-Host "- ลองอัพโหลดผ่าน: Litterbox" -ForegroundColor Cyan
    
    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    
    $bodyLines = (
        "--$boundary",
        "Content-Disposition: form-data; name=`"reqtype`"$LF",
        "fileupload",
        "--$boundary",
        "Content-Disposition: form-data; name=`"time`"$LF",
        "1h",
        "--$boundary",
        "Content-Disposition: form-data; name=`"fileToUpload`"; filename=`"$fileName`"",
        "Content-Type: application/octet-stream$LF",
        [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($fileBytes),
        "--$boundary--$LF"
    ) -join $LF

    $response = Invoke-RestMethod -Uri "https://litterbox.catbox.moe/resources/internals/api.php" `
        -Method Post `
        -ContentType "multipart/form-data; boundary=$boundary" `
        -Body $bodyLines `
        -TimeoutSec 60
    
    if ($response -match "^https://litter\.catbox\.moe/") {
        $resultUrl = $response.Trim()
        $uploadSuccess = $true
        Write-Host "`n- ส่งผ่านระบบ: Litterbox สำเร็จ" -ForegroundColor Green
    } else {
        throw "Invalid response from Litterbox: $response"
    }
} catch {
    Write-Host "`nLitterbox upload failed: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Service 2: TmpFiles.org (Fallback)
if (-not $uploadSuccess) {
    try {
        Write-Host "`n- ส่งผ่านระบบ: Litterbox ล้มเหลว - กำลังลองระบบสำรอง..." -ForegroundColor Yellow
        Write-Host "- ลองอัพโหลดผ่าน: TmpFiles" -ForegroundColor Cyan
        
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        
        $bodyLines = (
            "--$boundary",
            "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
            "Content-Type: application/octet-stream$LF",
            [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($fileBytes),
            "--$boundary--$LF"
        ) -join $LF

        $response = Invoke-RestMethod -Uri "https://tmpfiles.org/api/v1/upload" `
            -Method Post `
            -ContentType "multipart/form-data; boundary=$boundary" `
            -Body $bodyLines `
            -TimeoutSec 60
        
        if ($response.status -eq "success" -and $response.data.url) {
            # TmpFiles returns full URL like "https://tmpfiles.org/123456"
            $fileId = $response.data.url -replace "https://tmpfiles\.org/", ""
            $resultUrl = "tf_$fileId"
            $uploadSuccess = $true
            Write-Host "`n- ส่งผ่านระบบ: TempFile สำเร็จ" -ForegroundColor Green
        } else {
            throw "Invalid response from TmpFiles: $($response | ConvertTo-Json)"
        }
    } catch {
        Write-Host "`n- ส่งผ่านระบบ: TempFile ล้มเหลว: $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Service 3: 0x0.st (Final fallback)
if (-not $uploadSuccess) {
    try {
        Write-Host "`n- ลองอัพโหลดผ่าน: 0x0.st" -ForegroundColor Cyan
        
        $boundary = [System.Guid]::NewGuid().ToString()
        $LF = "`r`n"
        
        $bodyLines = (
            "--$boundary",
            "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
            "Content-Type: application/octet-stream$LF",
            [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($fileBytes),
            "--$boundary--$LF"
        ) -join $LF

        $response = Invoke-RestMethod -Uri "https://0x0.st" `
            -Method Post `
            -ContentType "multipart/form-data; boundary=$boundary" `
            -Body $bodyLines `
            -TimeoutSec 60
        
        if ($response -match "^https://0x0\.st/") {
            $fileId = $response.Trim() -replace "https://0x0\.st/", ""
            $resultUrl = "0x0_$fileId"
            $uploadSuccess = $true
            Write-Host "`n- ส่งผ่านระบบ: 0x0.st สำเร็จ" -ForegroundColor Green
        }
    } catch {
        Write-Host "`n- ส่งผ่านระบบ: 0x0.st ล้มเหลว: $($_.Exception.Message)" -ForegroundColor Red
    }
}

if ($uploadSuccess) {
    Write-Host "- คัดลอกลิงก์ลง Clipboard เรียบร้อยแล้ว`n `n " -ForegroundColor Green
    # Return the file ID for the calling script
    return $resultUrl
} else {
    Write-Host "`n❌ ทั้งหมดล้มเหลว - กรุณาลองใหม่อีกครั้ง`n" -ForegroundColor Red
    exit 1
}
