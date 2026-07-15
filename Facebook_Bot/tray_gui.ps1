# tray_gui.ps1 - System Tray Icon & Status Popup Widget for Facebook Bot (File-based IPC)
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

# --- Win32 API Definitions for Window Management & Dragging ---
$code = @"
using System;
using System.Runtime.InteropServices;
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
}
"@
Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue

$botDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $botDir
$statusFile = Join-Path $botDir "status.json"

# --- State for Browser Visibility (Default to True/Shown) ---
$script:browserVisible = $true

# --- Functions to Find & Control Playwright Browser Window Hwnd ---
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
        
        if ($hwnds.Count -eq 0) {
            $chromeProcs = Get-WmiObject Win32_Process | Where-Object {
                ($_.Name -eq "chrome.exe" -or $_.Name -eq "msedge.exe") -and $_.CommandLine -like "*Facebook_Bot*"
            }
            foreach ($cp in $chromeProcs) {
                try {
                    $p = [System.Diagnostics.Process]::GetProcessById($cp.ProcessId)
                    if ($p -and $p.MainWindowHandle -ne [IntPtr]::Zero) {
                        $hwnds += $p.MainWindowHandle
                    }
                } catch {}
            }
        }
        
        return $hwnds
    } catch {
        return @()
    }
}

function Show-ChromeWindow {
    $script:browserVisible = $true
    try {
        $hwnds = Get-PlaywrightBrowserHwnds
        foreach ($hwnd in $hwnds) {
            [Win32Gui]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE = 9
            [Win32Gui]::SetForegroundWindow($hwnd) | Out-Null
        }
    } catch {}
}

function Toggle-ChromeWindow {
    $script:browserVisible = -not $script:browserVisible
    try {
        $hwnds = Get-PlaywrightBrowserHwnds
        foreach ($hwnd in $hwnds) {
            if ($script:browserVisible) {
                [Win32Gui]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE
                [Win32Gui]::SetForegroundWindow($hwnd) | Out-Null
            } else {
                [Win32Gui]::ShowWindow($hwnd, 6) | Out-Null  # SW_MINIMIZE
            }
        }
    } catch {}
}

# --- Extract Globe Icon for Tray ---
$hIcon = [Win32Gui]::ExtractIcon(0, "shell32.dll", 13)
if ($hIcon -ne [IntPtr]::Zero) {
    $fbIcon = [System.Drawing.Icon]::FromHandle($hIcon)
} else {
    $fbIcon = [System.Drawing.SystemIcons]::Application
}

# --- Create Form (Popup Widget) ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "Facebook Bot Status"
$form.Icon = $fbIcon
$form.Size = New-Object System.Drawing.Size(390, 155)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 46)

$null = $form.Handle

# Position at Bottom-Right of Screen 2 (if exists) or Screen 1
$screens = [System.Windows.Forms.Screen]::AllScreens
if ($screens.Count -gt 1) {
    $targetScreen = $screens[1]
} else {
    $targetScreen = $screens[0]
}
$wa = $targetScreen.WorkingArea
$posX = $wa.Right - 390 - 20
$posY = $wa.Bottom - 155 - 20
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual
$form.Location = New-Object System.Drawing.Point($posX, $posY)

# Border Panel
$panelBorder = New-Object System.Windows.Forms.Panel
$panelBorder.Dock = [System.Windows.Forms.DockStyle]::Fill
$panelBorder.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$form.Controls.Add($panelBorder)

# Header Panel
$panelHeader = New-Object System.Windows.Forms.Panel
$panelHeader.Height = 32
$panelHeader.Dock = [System.Windows.Forms.DockStyle]::Top
$panelHeader.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 37)

$panelHeader.add_MouseDown({
    if ($_.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
        [Win32Gui]::ReleaseCapture() | Out-Null
        [Win32Gui]::SendMessage($form.Handle, [Win32Gui]::WM_NCLBUTTONDOWN, [Win32Gui]::HT_CAPTION, 0) | Out-Null
    }
})

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "ⓕ Facebook Bot (กำลังเตรียมระบบ...)"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::White
$lblTitle.AutoSize = $true
$lblTitle.Location = New-Object System.Drawing.Point(10, 6)
$panelHeader.Controls.Add($lblTitle)

# Button to Show/Hide Browser on Widget Header
$btnToggleBrowser = New-Object System.Windows.Forms.Button
$btnToggleBrowser.Text = "ⓕ เบราว์เซอร์"
$btnToggleBrowser.Size = New-Object System.Drawing.Size(95, 23)
$btnToggleBrowser.Location = New-Object System.Drawing.Point(255, 4)
$btnToggleBrowser.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnToggleBrowser.FlatAppearance.BorderSize = 1
$btnToggleBrowser.FlatAppearance.BorderColor = [System.Drawing.Color]::FromArgb(79, 195, 247)
$btnToggleBrowser.BackColor = [System.Drawing.Color]::FromArgb(35, 45, 65)
$btnToggleBrowser.ForeColor = [System.Drawing.Color]::FromArgb(79, 195, 247)
$btnToggleBrowser.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$btnToggleBrowser.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnToggleBrowser.add_Click({
    Toggle-ChromeWindow
})
$panelHeader.Controls.Add($btnToggleBrowser)

# Close (Hide) Button on Widget
$btnCloseWidget = New-Object System.Windows.Forms.Button
$btnCloseWidget.Text = "✕"
$btnCloseWidget.Size = New-Object System.Drawing.Size(26, 22)
$btnCloseWidget.Location = New-Object System.Drawing.Point(356, 4)
$btnCloseWidget.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnCloseWidget.FlatAppearance.BorderSize = 0
$btnCloseWidget.ForeColor = [System.Drawing.Color]::FromArgb(180, 180, 180)
$btnCloseWidget.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnCloseWidget.add_Click({
    $form.Hide()
})
$panelHeader.Controls.Add($btnCloseWidget)
$panelBorder.Controls.Add($panelHeader)

# Status Text Label
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "กำลังเริ่มต้นระบบ..."
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 9.5, [System.Drawing.FontStyle]::Bold)
$lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(79, 195, 247)
$lblStatus.Location = New-Object System.Drawing.Point(12, 40)
$lblStatus.Size = New-Object System.Drawing.Size(360, 22)
$panelBorder.Controls.Add($lblStatus)

# Progress Bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(12, 66)
$progressBar.Size = New-Object System.Drawing.Size(315, 18)
$progressBar.Minimum = 0
$progressBar.Maximum = 100
$progressBar.Value = 0
$panelBorder.Controls.Add($progressBar)

# Percent Label
$lblPercent = New-Object System.Windows.Forms.Label
$lblPercent.Text = "0%"
$lblPercent.Font = New-Object System.Drawing.Font("Segoe UI", 9, [System.Drawing.FontStyle]::Bold)
$lblPercent.ForeColor = [System.Drawing.Color]::White
$lblPercent.Location = New-Object System.Drawing.Point(332, 66)
$lblPercent.Size = New-Object System.Drawing.Size(45, 18)
$lblPercent.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
$panelBorder.Controls.Add($lblPercent)

# Detail / Reason Label
$lblDetail = New-Object System.Windows.Forms.Label
$lblDetail.Text = "รอการเชื่อมต่อจาก Facebook Bot..."
$lblDetail.Font = New-Object System.Drawing.Font("Segoe UI", 8.5)
$lblDetail.ForeColor = [System.Drawing.Color]::FromArgb(186, 194, 222)
$lblDetail.Location = New-Object System.Drawing.Point(12, 90)
$lblDetail.Size = New-Object System.Drawing.Size(365, 52)
$panelBorder.Controls.Add($lblDetail)

# System Tray Icon & Context Menu
$trayIcon = New-Object System.Windows.Forms.NotifyIcon
$trayIcon.Icon = $fbIcon
$trayIcon.Text = "Facebook Bot (Running)"
$trayIcon.Visible = $true

$contextMenu = New-Object System.Windows.Forms.ContextMenuStrip

$menuToggle = New-Object System.Windows.Forms.ToolStripMenuItem
$menuToggle.Text = "📌 แสดง/ซ่อน หน้าต่างสถานะ"
$menuToggle.add_Click({
    if ($form.Visible) {
        $form.Hide()
    } else {
        $form.Show()
        $form.BringToFront()
    }
})
$contextMenu.Items.Add($menuToggle) | Out-Null

$menuBrowser = New-Object System.Windows.Forms.ToolStripMenuItem
$menuBrowser.Text = "ⓕ แสดง/ซ่อน หน้าต่างเบราว์เซอร์"
$menuBrowser.add_Click({
    Toggle-ChromeWindow
})
$contextMenu.Items.Add($menuBrowser) | Out-Null

$contextMenu.Items.Add((New-Object System.Windows.Forms.ToolStripSeparator)) | Out-Null

$menuExit = New-Object System.Windows.Forms.ToolStripMenuItem
$menuExit.Text = "❌ ปิดโปรเซส (Exit Bot)"
$menuExit.add_Click({
    Stop-FacebookBotProcess
})
$contextMenu.Items.Add($menuExit) | Out-Null

$trayIcon.ContextMenuStrip = $contextMenu

$trayIcon.add_DoubleClick({
    if ($form.Visible) {
        $form.Hide()
    } else {
        $form.Show()
        $form.BringToFront()
    }
})

function Stop-FacebookBotProcess {
    try {
        Get-WmiObject Win32_Process | Where-Object {
            $_.CommandLine -like "*bot.js*"
        } | ForEach-Object {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    } catch {}

    if ($trayIcon) {
        $trayIcon.Visible = $false
        $trayIcon.Dispose()
    }
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

    if ($data.showBrowser) {
        Show-ChromeWindow
    }

    if ($data.postIndex -and $data.maxPosts) {
        $newTitle = "ⓕ Facebook Bot (โพสต์ $($data.postIndex)/$($data.maxPosts))"
        if ($lblTitle.Text -ne $newTitle) {
            $lblTitle.Text = $newTitle
        }
    }

    if ($null -ne $data.percent) {
        $val = [Math]::Max(0, [Math]::Min(100, [int]$data.percent))
        if ($progressBar.Value -ne $val) {
            $progressBar.Value = $val
        }
        $newPercent = "$val%"
        if ($lblPercent.Text -ne $newPercent) {
            $lblPercent.Text = $newPercent
        }
    }

    if ($data.status) {
        if ($lblStatus.Text -ne $data.status) {
            $lblStatus.Text = $data.status
        }
        
        $newTrayText = "FB Bot: $($data.status)"
        # WinForms NotifyIcon.Text has a strict limit of 63 characters.
        # Exceeding it will throw an exception.
        if ($newTrayText.Length -gt 63) {
            $newTrayText = $newTrayText.Substring(0, 60) + "..."
        }
        
        # Only update if it has changed to prevent Win32 tray redraw focus stealing
        if ($trayIcon.Text -ne $newTrayText) {
            $trayIcon.Text = $newTrayText
        }
    }

    if ($data.detail) {
        if ($lblDetail.Text -ne $data.detail) {
            $lblDetail.Text = $data.detail
        }
    }

    # Only update ForeColor if it changes to prevent redundant WinForms paint events
    $targetColor = [System.Drawing.Color]::FromArgb(79, 195, 247)
    if ($data.logType -eq "warn") {
        $targetColor = [System.Drawing.Color]::FromArgb(255, 183, 77)
    } elseif ($data.logType -eq "error") {
        $targetColor = [System.Drawing.Color]::FromArgb(239, 83, 80)
        Show-ChromeWindow
    } elseif ($data.logType -eq "success") {
        $targetColor = [System.Drawing.Color]::FromArgb(102, 187, 106)
    }

    if ($lblStatus.ForeColor -ne $targetColor) {
        $lblStatus.ForeColor = $targetColor
    }
}

# WinForms Timer to Poll status.json every 1000ms (1 second)
$script:lastReadTimestamp = 0
$script:nodeProcessCheckCount = 0
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 1000
$timer.add_Tick({
    # ✅ ตรวจจับเมื่อ bot.js process 退出 — ปิด tray ตามอัตโนมัติ
    $script:nodeProcessCheckCount++
    if ($script:nodeProcessCheckCount -ge 5) {
        $script:nodeProcessCheckCount = 0
        $nodeRunning = Get-WmiObject Win32_Process | Where-Object {
            $_.Name -eq "node.exe" -and $_.CommandLine -like "*bot.js*"
        }
        if (-not $nodeRunning) {
            # ตรวจสอบ status.json ว่ามี action=exit หรือ crash หรือไม่
            $shouldExit = $false
            if (Test-Path $statusFile) {
                try {
                    $s = Get-Content $statusFile -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
                    if ($s.action -eq "exit" -or $s.logType -eq "error") {
                        $shouldExit = $true
                    }
                } catch {}
            }
            # ถ้า node หยุดทำงานและ status ไม่ใช่ running ให้ปิดตัว
            if ($shouldExit -or -not (Test-Path $statusFile)) {
                Stop-FacebookBotProcess
                return
            }
        }
    }

    # Read status.json
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
