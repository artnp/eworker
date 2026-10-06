# KBank Live Notification Listener for Windows 10/11
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
    $_.Name -eq 'AsTask' -and 
    $_.GetParameters().Count -eq 1 -and 
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' 
} | Select-Object -First 1

function Await-AsyncOp($asyncOp, $resultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($resultType)
    $netTask = $asTask.Invoke($null, @($asyncOp))
    $netTask.Wait()
    return $netTask.Result
}

$listener = [Windows.UI.Notifications.Management.UserNotificationListener, Windows.UI.Notifications, ContentType = WindowsRuntime]::Current
$status = $listener.GetAccessStatus()
if ($status -ne [Windows.UI.Notifications.Management.UserNotificationListenerAccessStatus]::Allowed) {
    Write-Output "ERROR: Access not allowed ($status)"
    exit 1
}

Write-Output "READY: Listening for KBank notifications..."

$seenIds = New-Object System.Collections.Generic.HashSet[uint32]

# Initial fetch to populate seenIds so past notifications are ignored
try {
    $asyncOp = $listener.GetNotificationsAsync([Windows.UI.Notifications.NotificationKinds]::Toast)
    $listType = [System.Collections.Generic.IReadOnlyList[Windows.UI.Notifications.UserNotification]]
    $initialNotifications = Await-AsyncOp $asyncOp $listType
    foreach ($n in $initialNotifications) {
        $seenIds.Add($n.Id) | Out-Null
    }
} catch { }

function Check-NotificationItem($n) {
    if (-not $n) { return }
    $id = $n.Id
    if ($seenIds.Contains($id)) { return }
    $seenIds.Add($id) | Out-Null

    $app = ""
    try { $app = $n.AppInfo.DisplayInfo.DisplayName } catch { }

    $binding = $null
    try {
        $binding = $n.Notification.Visual.GetBinding([Windows.UI.Notifications.KnownNotificationBindings]::ToastGeneric)
    } catch { }

    if (-not $binding) { return }

    $textElements = @()
    try {
        $textElements = $binding.GetTextElements() | ForEach-Object { $_.Text }
    } catch { }

    $fullText = $textElements -join " "
    
    # เงื่อนไขคัดกรอง 3 ชั้น (Strict Triple-Check):
    # 1. ผู้ส่งต้องเป็น KBank Live หรือ K PLUS เท่านั้น (ตัดแชทเพื่อนและแชทกลุ่มทิ้ง 100%)
    $isKBank = ($fullText -like "*KBank Live*" -or $fullText -like "*K PLUS*" -or ($textElements.Count -gt 0 -and $textElements[0] -like "*KBank*") -or ($app -like "*LINE*" -and $fullText -like "*KBank*"))
    # 2. ต้องมีคำว่า รายการเงินเข้า หรือ เงินเข้า หรือ แจ้งเตือนเงินเข้า
    $isDeposit = ($fullText -like "*รายการเงินเข้า*" -or $fullText -like "*เงินเข้า*" -or $fullText -like "*แจ้งเตือนเงินเข้า*")

    if ($isKBank -and $isDeposit) {
        # 3. ดึงยอดเงินออกมาถ้ามี เช่น "จำนวนเงิน: 60.00 บาท" (ถ้าเป็น LINE Flex Message จะไม่มีตัวเลข ให้ส่ง amount เป็น null)
        $amount = $null
        $match = [regex]::Match($fullText, '(?:จำนวนเงิน|ยอดเงิน|เงินเข้า)[\s:]*([0-9,]+(?:\.[0-9]{1,2})?)\s*(?:บาท|บ\.)')
        if (-not $match.Success) {
            $match = [regex]::Match($fullText, '([0-9,]+\.[0-9]{2})\s*(?:บาท|บ\.)')
        }
        if ($match.Success) {
            $amtStr = $match.Groups[1].Value -replace ',', ''
            $amount = [double]$amtStr
        }

        $obj = @{
            event = "kbank_deposit"
            amount = $amount
            raw_text = $fullText
            app = $app
            id = $id
            timestamp = [DateTimeOffset]::Now.ToUnixTimeMilliseconds()
        }
        $json = $obj | ConvertTo-Json -Compress
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        Write-Output "EVENT:$json"
    }
}

# Polling loop ทุกๆ 1 วินาที (กิน CPU 0.0%)
while ($true) {
    try {
        $asyncOp = $listener.GetNotificationsAsync([Windows.UI.Notifications.NotificationKinds]::Toast)
        $listType = [System.Collections.Generic.IReadOnlyList[Windows.UI.Notifications.UserNotification]]
        $notifications = Await-AsyncOp $asyncOp $listType
        foreach ($n in $notifications) {
            Check-NotificationItem $n
        }
    } catch { }
    Start-Sleep -Seconds 1
}
