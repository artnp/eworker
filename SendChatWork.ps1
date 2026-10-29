param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath
)

$ErrorActionPreference = 'Stop'
$activeRoomPath = Join-Path $PSScriptRoot 'chat\.active-room.json'

if (-not (Test-Path -LiteralPath $FilePath -PathType Leaf)) {
    throw "ไม่พบไฟล์ที่ต้องการส่ง: $FilePath"
}
if (-not (Test-Path -LiteralPath $activeRoomPath -PathType Leaf)) {
    throw 'ยังไม่มีห้องแชทที่ใช้งานอยู่ กรุณาเปิด chat\GenRoom.bat ก่อน'
}

$allowedExtensions = '.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif', '.pdf'
if ([IO.Path]::GetExtension($FilePath).ToLowerInvariant() -notin $allowedExtensions) {
    throw 'รองรับเฉพาะไฟล์ภาพหรือ PDF'
}

$room = Get-Content -LiteralPath $activeRoomPath -Raw | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($room.roomId)) {
    throw 'ข้อมูลห้องแชทไม่ถูกต้อง กรุณาสร้างห้องใหม่'
}

$payload = @{ roomId = [string]$room.roomId; filePath = (Resolve-Path -LiteralPath $FilePath).Path } |
    ConvertTo-Json -Compress

try {
    Invoke-RestMethod -Uri 'http://127.0.0.1:5000/chat-delivery' -Method Post `
        -ContentType 'application/json; charset=utf-8' -Body $payload -TimeoutSec 10 | Out-Null
    Write-Host "ส่งไฟล์เข้าคิวห้อง $($room.roomId) แล้ว — Edge จะสร้างลายน้ำและบิลให้" -ForegroundColor Green
} catch {
    throw "ส่งไฟล์เข้าคิวไม่สำเร็จ: $($_.Exception.Message)"
}
