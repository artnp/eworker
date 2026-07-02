param(
    [string]$TitleB64 = "",
    [string]$TextB64 = "",
    [ValidateSet("Info", "Warning", "Error")]
    [string]$Type = "Info"
)

function Decode-Utf8B64([string]$b64) {
    if (-not $b64) { return "" }
    return [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
}

$title = Decode-Utf8B64 $TitleB64
$text = Decode-Utf8B64 $TextB64

# Choose emoji based on Type
$emoji = "ℹ️"
if ($Type -eq "Warning") { $emoji = "⚠️" }
elseif ($Type -eq "Error") { $emoji = "❌" }

$displayTitle = "$emoji $title"

try {
    # Load required Windows Runtime assemblies for Toast Notifications
    [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
    [void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime]
    
    # Create XML payload for Toast Notification
    $xml = [Windows.Data.Xml.Dom.XmlDocument]::new()
    $template = @"
<toast>
    <visual>
        <binding template="ToastGeneric">
            <text>$displayTitle</text>
            <text>$text</text>
        </binding>
    </visual>
</toast>
"@
    $xml.LoadXml($template)
    $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
    
    # Expiration time is set to 5 seconds. If not delivered/read in 5 seconds (e.g. screen locked/off),
    # it expires and won't show up retroactively when the user returns.
    $toast.ExpirationTime = [DateTimeOffset]::Now.AddSeconds(5)
    
    $appId = "Microsoft.Windows.Shell.Run"
    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
    $notifier.Show($toast)
} catch {
    # Fallback to NotifyIcon if ToastNotification fails
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    
    $iconType = [System.Drawing.SystemIcons]::Information
    if ($Type -eq "Warning") { $iconType = [System.Drawing.SystemIcons]::Warning }
    elseif ($Type -eq "Error") { $iconType = [System.Drawing.SystemIcons]::Error }

    $tray = New-Object System.Windows.Forms.NotifyIcon
    $tray.Icon = $iconType
    $tray.Visible = $true
    $tray.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::$Type
    $tray.BalloonTipTitle = $title
    $tray.BalloonTipText = $text
    $tray.ShowBalloonTip(10000)
    Start-Sleep -Seconds 3
    $tray.Dispose()
}