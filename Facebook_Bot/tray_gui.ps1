# tray_gui.ps1 - Status Popup Widget docked under Playwright Chrome Window (File-based IPC)
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- Ensure Single Instance of tray_gui.ps1 ---
$currentPid = $PID
Get-WmiObject Win32_Process | Where-Object {
    $_.ProcessId -ne $currentPid -and $_.CommandLine -like "*tray_gui.ps1*"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 200

# --- Win32 API Definitions for Window Management, Dragging & Rect Tracking ---
$code = @"
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)]
public struct RECT {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

public class Win32Gui {
    public const int WM_NCLBUTTONDOWN = 0xA1;
    public const int HT_CAPTION = 0x2;
    [DllImport("user32.dll")]
    public static extern int SendMessage(IntPtr hWnd, int Msg, int wParam, int lParam);
    [DllImport("user32.dll")]
    public static extern bool ReleaseCapture();
    [DllImport("shell32.dll", CharSet = CharSet.Auto)]
    public static extern IntPtr ExtractIcon(IntPtr hInst, string lpszExeFileName, int nIconIndex);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
}
"@
Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue

$botDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $botDir
$statusFile = Join-Path $botDir "status.json"

# --- Functions to Find Playwright Browser Window Hwnd ---
function Get-PlaywrightBrowserHwnds {
    try {
        $nodeProc = Get-WmiObject Win32_Process | Where-Object {
            $_.Name -eq "node.exe" -and $_.CommandLine -like "*bot.js*"
        }
        if (-not $nodeProc) { return @() }
        
        $allProcs = Get-WmiObject Win32_Process
        $descendantPids = @()
        $queue = [System.Collections.Generic.Queue[int]]::new()
        foreach ($np in $nodeProc) { $queue.Enqueue($np.ProcessId) }
        while ($queue.Count -gt 0) {
            $parentPid = $queue.Dequeue()
            $children = $allProcs | Where-Object { $_.ParentProcessId -eq $parentPid }
            foreach ($child in $children) {
                $descendantPids += $child.ProcessId
                $queue.Enqueue($child.ProcessId)
            }
        }
        
        $hwnds = @()
        foreach ($pid in $descendantPids) {
            try {
                $p = [System.Diagnostics.Process]::GetProcessById($pid)
                if ($p -and ($p.ProcessName -eq "chrome" -or $p.ProcessName -eq "msedge" -or $p.ProcessName -eq "chromium")) {
                    if ($p.MainWindowHandle -ne [IntPtr]::Zero) {
                        $hwnds += $p.MainWindowHandle
                    }
                }
            } catch {}
        }
        return $hwnds
    } catch {
        return @()
    }
}

# --- Extract Globe Icon for Form ---
$hIcon = [Win32Gui]::ExtractIcon(0, "shell32.dll", 13)
if ($hIcon -ne [IntPtr]::Zero) {
    $fbIcon = [System.Drawing.Icon]::FromHandle($hIcon)
} else {
    $fbIcon = [System.Drawing.SystemIcons]::Application
}

# --- Create Form (Status Popup Widget) ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "Facebook Bot Status"
$form.Icon = $fbIcon
$form.Size = New-Object System.Drawing.Size(380, 78)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 46)

$null = $form.Handle

# Position initially at Bottom-Right of Screen
$screens = [System.Windows.Forms.Screen]::AllScreens
$targetScreen = if ($screens.Count -gt 1) { $screens[1] } else { $screens[0] }
$wa = $targetScreen.WorkingArea
$posX = $wa.Right - 380 - 15
$posY = $wa.Bottom - 78 - 15
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$form.Location = New-Object System.Drawing.Point($posX, $posY)

# Border Panel
$panelBorder = New-Object System.Windows.Forms.Panel
$panelBorder.Dock = [System.Windows.Forms.DockStyle]::Fill
$panelBorder.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$form.Controls.Add($panelBorder)

# Header Panel
$panelHeader = New-Object System.Windows.Forms.Panel
$panelHeader.Height = 22
$panelHeader.Dock = [System.Windows.Forms.DockStyle]::Top
$panelHeader.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 37)

$panelHeader.add_MouseDown({
    if ($_.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
        [Win32Gui]::ReleaseCapture() | Out-Null
        [Win32Gui]::SendMessage($form.Handle, [Win32Gui]::WM_NCLBUTTONDOWN, [Win32Gui]::HT_CAPTION, 0) | Out-Null
    }
})

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "ⓕ Facebook Bot Status"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::White
$lblTitle.AutoSize = $true
$lblTitle.Location = New-Object System.Drawing.Point(8, 3)
$panelHeader.Controls.Add($lblTitle)

# Toggle Browser View Button on Widget (👁 Show / Hide Offscreen Browser)
$btnToggleBrowser = New-Object System.Windows.Forms.Button
$btnToggleBrowser.Text = "👁"
$btnToggleBrowser.Size = New-Object System.Drawing.Size(22, 18)
$btnToggleBrowser.Location = New-Object System.Drawing.Point(326, 2)
$btnToggleBrowser.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnToggleBrowser.FlatAppearance.BorderSize = 0
$btnToggleBrowser.ForeColor = [System.Drawing.Color]::FromArgb(180, 180, 180)
$btnToggleBrowser.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnToggleBrowser.add_Click({
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:12122/toggle-browser" -Method POST -TimeoutSec 2 -ErrorAction SilentlyContinue | Out-Null
    } catch {}
})
$panelHeader.Controls.Add($btnToggleBrowser)

# Close Button on Widget (Exits entire bot process)
$btnCloseWidget = New-Object System.Windows.Forms.Button
$btnCloseWidget.Text = "✕"
$btnCloseWidget.Size = New-Object System.Drawing.Size(22, 18)
$btnCloseWidget.Location = New-Object System.Drawing.Point(352, 2)
$btnCloseWidget.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnCloseWidget.FlatAppearance.BorderSize = 0
$btnCloseWidget.ForeColor = [System.Drawing.Color]::FromArgb(180, 180, 180)
$btnCloseWidget.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnCloseWidget.add_Click({
    Stop-FacebookBotProcess
})
$panelHeader.Controls.Add($btnCloseWidget)
$panelBorder.Controls.Add($panelHeader)

# Status Text Label
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "กำลังเริ่มต้นระบบ..."
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(79, 195, 247)
$lblStatus.Location = New-Object System.Drawing.Point(8, 25)
$lblStatus.Size = New-Object System.Drawing.Size(364, 16)
$lblStatus.AutoEllipsis = $true
$panelBorder.Controls.Add($lblStatus)

# Progress Bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(8, 43)
$progressBar.Size = New-Object System.Drawing.Size(318, 11)
$progressBar.Minimum = 0
$progressBar.Maximum = 100
$progressBar.Value = 0
$panelBorder.Controls.Add($progressBar)

# Percent Label
$lblPercent = New-Object System.Windows.Forms.Label
$lblPercent.Text = "0%"
$lblPercent.Font = New-Object System.Drawing.Font("Segoe UI", 8.0, [System.Drawing.FontStyle]::Bold)
$lblPercent.ForeColor = [System.Drawing.Color]::White
$lblPercent.Location = New-Object System.Drawing.Point(330, 41)
$lblPercent.Size = New-Object System.Drawing.Size(44, 14)
$lblPercent.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
$panelBorder.Controls.Add($lblPercent)

# Detail Label
$lblDetail = New-Object System.Windows.Forms.Label
$lblDetail.Text = "รอการเชื่อมต่อจาก Facebook Bot..."
$lblDetail.Font = New-Object System.Drawing.Font("Segoe UI", 8.0)
$lblDetail.ForeColor = [System.Drawing.Color]::FromArgb(186, 194, 222)
$lblDetail.Location = New-Object System.Drawing.Point(8, 57)
$lblDetail.Size = New-Object System.Drawing.Size(364, 16)
$lblDetail.AutoEllipsis = $true
$panelBorder.Controls.Add($lblDetail)

function Stop-FacebookBotProcess {
    try {
        Get-WmiObject Win32_Process | Where-Object {
            $_.CommandLine -like "*bot.js*"
        } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    } catch {}

    if ($form) {
        $form.Close()
    }
    [System.Windows.Forms.Application]::Exit()
}

function Update-StatusUI ($data) {
    if (-not $data) { return }

    if ($data.action -eq "exit" -or $data.action -eq "crash") {
        Stop-FacebookBotProcess
        return
    }

    if ($data.postIndex -and $data.maxPosts) {
        $newTitle = "ⓕ Facebook Bot (โพสต์ $($data.postIndex)/$($data.maxPosts))"
        if ($lblTitle.Text -ne $newTitle) {
            $lblTitle.Text = $newTitle
        }
    }

    if ($null -ne $data.percent) {
        $val = [Math]::Max(0, [Math]::Min(100, [int]$data.percent))
        if ($progressBar.Value -ne $val) { $progressBar.Value = $val }
        $newPercent = "$val%"
        if ($lblPercent.Text -ne $newPercent) { $lblPercent.Text = $newPercent }
    }

    if ($data.status) {
        if ($lblStatus.Text -ne $data.status) { $lblStatus.Text = $data.status }
    }

    if ($data.detail) {
        if ($lblDetail.Text -ne $data.detail) { $lblDetail.Text = $data.detail }
    }

    $targetColor = [System.Drawing.Color]::FromArgb(79, 195, 247)
    if ($data.logType -eq "warn") {
        $targetColor = [System.Drawing.Color]::FromArgb(255, 183, 77)
    } elseif ($data.logType -eq "error") {
        $targetColor = [System.Drawing.Color]::FromArgb(239, 83, 80)
    } elseif ($data.logType -eq "success") {
        $targetColor = [System.Drawing.Color]::FromArgb(102, 187, 106)
    }

    if ($lblStatus.ForeColor -ne $targetColor) {
        $lblStatus.ForeColor = $targetColor
    }
}

# --- Timer to Sync Widget Position & Read status.json ---
$script:lastReadTimestamp = 0
$script:nodeProcessCheckCount = 0
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 500
$timer.add_Tick({
    # Align widget directly below Chrome's bottom-right edge IF Chrome is on visible screen
    try {
        $hwnds = Get-PlaywrightBrowserHwnds
        if ($hwnds.Count -gt 0) {
            $rect = New-Object RECT
            if ([Win32Gui]::GetWindowRect($hwnds[0], [ref]$rect)) {
                $isChromeVisibleOnScreen = ($rect.Left -ge -100 -and $rect.Left -lt 5000 -and $rect.Top -ge -100 -and $rect.Top -lt 5000 -and ($rect.Right - $rect.Left) -gt 100)
                if ($isChromeVisibleOnScreen) {
                    $dockX = $rect.Right - 380
                    $dockY = $rect.Bottom + 2
                    $screen = [System.Windows.Forms.Screen]::FromHandle($hwnds[0])
                    if ($dockY + 78 -gt $screen.WorkingArea.Bottom) {
                        $dockY = $screen.WorkingArea.Bottom - 78
                    }
                    $newLoc = New-Object System.Drawing.Point($dockX, $dockY)
                    if ($form.Location -ne $newLoc) { $form.Location = $newLoc }
                } else {
                    # Chrome is offscreen: keep status widget at bottom-right corner of target screen
                    $screens = [System.Windows.Forms.Screen]::AllScreens
                    $targetScreen = if ($screens.Count -gt 1) { $screens[1] } else { $screens[0] }
                    $wa = $targetScreen.WorkingArea
                    $defX = $wa.Right - 380 - 15
                    $defY = $wa.Bottom - 78 - 15
                    $defLoc = New-Object System.Drawing.Point($defX, $defY)
                    if ($form.Location -ne $defLoc) { $form.Location = $defLoc }
                }
            }
        }
    } catch {}

    $script:nodeProcessCheckCount++
    if ($script:nodeProcessCheckCount -ge 6) {
        $script:nodeProcessCheckCount = 0
        $nodeRunning = Get-WmiObject Win32_Process | Where-Object {
            $_.Name -eq "node.exe" -and $_.CommandLine -like "*bot.js*"
        }
        if (-not $nodeRunning) {
            Stop-FacebookBotProcess
            return
        }
    }

    if (Test-Path $statusFile) {
        try {
            $stream = [System.IO.File]::Open($statusFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
            $reader = New-Object System.IO.StreamReader($stream)
            $content = $reader.ReadToEnd()
            $reader.Close()
            $stream.Close()
            if ($content) {
                $json = $content | ConvertFrom-Json
                if ($json.timestamp -and $json.timestamp -ne $script:lastReadTimestamp) {
                    $script:lastReadTimestamp = $json.timestamp
                    Update-StatusUI $json
                }
            }
        } catch {}
    }
})
$timer.Start()

$form.Show()
[System.Windows.Forms.Application]::Run($form)
