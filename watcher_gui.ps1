param([int]$ParentPid = 0)

# watcher_gui.ps1 - Floating Status & Loading Progress Bar Widget for AI Hub Central (Bigdata & Binance Square)
# Modeled after Facebook_Bot tray_gui.ps1
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# --- Ensure Single Instance ---
$currentPid = $PID
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq "powershell.exe" -or $_.Name -eq "pwsh.exe") -and
    $_.ProcessId -ne $currentPid -and
    ($_.CommandLine -like "*watcher_gui.ps1*")
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 100

# --- Win32 API Definitions for Dragging & Window Management ---
$win32Code = @"
using System;
using System.Runtime.InteropServices;

public class Win32WatcherGui {
    public const int WM_NCLBUTTONDOWN = 0xA1;
    public const int HT_CAPTION = 0x2;
    [DllImport("user32.dll")]
    public static extern int SendMessage(IntPtr hWnd, int Msg, int wParam, int lParam);
    [DllImport("user32.dll")]
    public static extern bool ReleaseCapture();
    [DllImport("shell32.dll", CharSet = CharSet.Auto)]
    public static extern IntPtr ExtractIcon(IntPtr hInst, string lpszExeFileName, int nIconIndex);
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
Add-Type -TypeDefinition $win32Code -ErrorAction SilentlyContinue

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$statusFile = Join-Path $scriptDir "status.json"

# --- Extract Movie/Video Icon ---
$hIcon = [Win32WatcherGui]::ExtractIcon(0, "shell32.dll", 115)
if ($hIcon -ne [IntPtr]::Zero) {
    $appIcon = [System.Drawing.Icon]::FromHandle($hIcon)
} else {
    $appIcon = [System.Drawing.SystemIcons]::Application
}

# --- Create Form (Status Popup Widget) ---
$form = New-Object System.Windows.Forms.Form
$form.Text = "AI Hub Central Status"
$form.Icon = $appIcon
$form.Size = New-Object System.Drawing.Size(385, 82)
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::None
$form.TopMost = $true
$form.ShowInTaskbar = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(30, 30, 46)

$form.StartPosition = [System.Windows.Forms.FormStartPosition]::Manual

$posFile = Join-Path $scriptDir "watcher_pos.json"
$script:lastSavedX = -99999
$script:lastSavedY = -99999

function Save-WidgetPosition {
    try {
        if ($form -and $form.Handle -ne [IntPtr]::Zero) {
            $x = $form.Location.X
            $y = $form.Location.Y
            if ($x -eq $script:lastSavedX -and $y -eq $script:lastSavedY) { return }
            if ($x -gt -4000 -and $y -gt -4000) {
                $script:lastSavedX = $x
                $script:lastSavedY = $y
                $posObj = @{ x = $x; y = $y }
                $jsonStr = $posObj | ConvertTo-Json -Compress
                [System.IO.File]::WriteAllText($posFile, $jsonStr, [System.Text.Encoding]::UTF8)
            }
        }
    } catch {}
}

function Load-WidgetPosition {
    $hasValidSaved = $false
    if (Test-Path $posFile) {
        try {
            $raw = [System.IO.File]::ReadAllText($posFile, [System.Text.Encoding]::UTF8)
            $saved = ConvertFrom-Json $raw -ErrorAction SilentlyContinue
            if ($saved -and $null -ne $saved.x -and $null -ne $saved.y) {
                $savedRect = New-Object System.Drawing.Rectangle([int]$saved.x, [int]$saved.y, $form.Width, $form.Height)
                foreach ($scr in [System.Windows.Forms.Screen]::AllScreens) {
                    if ($scr.WorkingArea.IntersectsWith($savedRect)) {
                        $form.Location = New-Object System.Drawing.Point([int]$saved.x, [int]$saved.y)
                        $hasValidSaved = $true
                        break
                    }
                }
            }
        } catch {}
    }

    if (-not $hasValidSaved) {
        # Default to Bottom-Right of PrimaryScreen WorkingArea (above taskbar)
        $wa = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
        $posX = $wa.Right - $form.Width - 18
        $posY = $wa.Bottom - $form.Height - 18
        $form.Location = New-Object System.Drawing.Point($posX, $posY)
    }
}

Load-WidgetPosition
$null = $form.Handle

$form.add_LocationChanged({
    if ($form.Visible) {
        Save-WidgetPosition
    }
})

# Border Panel
$panelBorder = New-Object System.Windows.Forms.Panel
$panelBorder.Dock = [System.Windows.Forms.DockStyle]::Fill
$panelBorder.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
$form.Controls.Add($panelBorder)

# Header Panel (Draggable)
$panelHeader = New-Object System.Windows.Forms.Panel
$panelHeader.Height = 22
$panelHeader.Dock = [System.Windows.Forms.DockStyle]::Top
$panelHeader.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 37)

$dragAction = {
    if ($_.Button -eq [System.Windows.Forms.MouseButtons]::Left) {
        [Win32WatcherGui]::ReleaseCapture() | Out-Null
        [Win32WatcherGui]::SendMessage($form.Handle, [Win32WatcherGui]::WM_NCLBUTTONDOWN, [Win32WatcherGui]::HT_CAPTION, 0) | Out-Null
        Save-WidgetPosition
    }
}
$panelHeader.add_MouseDown($dragAction)
$panelBorder.add_MouseDown($dragAction)

$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "🎬 AI Hub Process Status"
$lblTitle.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblTitle.ForeColor = [System.Drawing.Color]::White
$lblTitle.AutoSize = $true
$lblTitle.Location = New-Object System.Drawing.Point(8, 3)
$lblTitle.add_MouseDown($dragAction)
$panelHeader.Controls.Add($lblTitle)

# Close / Hide Button on Widget
$btnCloseWidget = New-Object System.Windows.Forms.Button
$btnCloseWidget.Text = "✕"
$btnCloseWidget.Size = New-Object System.Drawing.Size(22, 18)
$btnCloseWidget.Location = New-Object System.Drawing.Point(356, 2)
$btnCloseWidget.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
$btnCloseWidget.FlatAppearance.BorderSize = 0
$btnCloseWidget.ForeColor = [System.Drawing.Color]::FromArgb(180, 180, 180)
$btnCloseWidget.Cursor = [System.Windows.Forms.Cursors]::Hand
$btnCloseWidget.add_Click({
    $form.Visible = $false
})
$panelHeader.Controls.Add($btnCloseWidget)
$panelBorder.Controls.Add($panelHeader)

# Status Text Label
$lblStatus = New-Object System.Windows.Forms.Label
$lblStatus.Text = "พร้อมทำงาน..."
$lblStatus.Font = New-Object System.Drawing.Font("Segoe UI", 8.5, [System.Drawing.FontStyle]::Bold)
$lblStatus.ForeColor = [System.Drawing.Color]::FromArgb(137, 220, 235)
$lblStatus.Location = New-Object System.Drawing.Point(8, 25)
$lblStatus.Size = New-Object System.Drawing.Size(368, 16)
$lblStatus.AutoEllipsis = $true
$panelBorder.Controls.Add($lblStatus)

# Progress Bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(8, 43)
$progressBar.Size = New-Object System.Drawing.Size(320, 12)
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
$lblPercent.Size = New-Object System.Drawing.Size(46, 14)
$lblPercent.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
$panelBorder.Controls.Add($lblPercent)

# Detail Label
$lblDetail = New-Object System.Windows.Forms.Label
$lblDetail.Text = "รอคำสั่งจาก Gemini หรือ Binance Square..."
$lblDetail.Font = New-Object System.Drawing.Font("Segoe UI", 7.8)
$lblDetail.ForeColor = [System.Drawing.Color]::FromArgb(186, 194, 222)
$lblDetail.Location = New-Object System.Drawing.Point(8, 59)
$lblDetail.Size = New-Object System.Drawing.Size(368, 16)
$lblDetail.AutoEllipsis = $true
$panelBorder.Controls.Add($lblDetail)

# --- State Variables for Auto-Hide ---
$script:doneTimestamp = 0
$form.Visible = $false
$form.Hide()

function Update-StatusUI ($data) {
    if (-not $data) {
        if ($form.Visible) { $form.Hide() }
        return
    }

    $pct = 0
    if ($null -ne $data.percent) {
        $pct = [Math]::Max(0, [Math]::Min(100, [int]$data.percent))
    }

    $phase = if ($data.phase) { $data.phase.ToLower() } else { "idle" }
    $taskType = if ($data.taskType) { $data.taskType.ToLower() } else { "idle" }

    # Only show for actual Bigdata Video or Binance Square jobs
    $isTargetTask = ($taskType -in @("bigdata", "binance"))
    $isActive = $isTargetTask -and ($phase -ne "idle" -and $phase -ne "done")
    $isDone = $isTargetTask -and ($phase -eq "done" -or $pct -ge 100)
    $isIdle = ($phase -eq "idle" -or $taskType -eq "idle" -or -not $isTargetTask)

    if ($isIdle) {
        $script:doneTimestamp = 0
        if ($form.Visible) {
            $form.Hide()
        }
        return
    }

    # Update Title
    $taskName = if ($data.taskType -eq "binance") { "🔶 Binance Square" } else { "🎬 Bigdata Video" }
    $qSize = if ($data.queueSize -and [int]$data.queueSize -gt 0) { " (คิวรอ: $($data.queueSize))" } else { "" }
    $newTitle = "$taskName$qSize"
    if ($lblTitle.Text -ne $newTitle) { $lblTitle.Text = $newTitle }

    # Update Progress
    if ($progressBar.Value -ne $pct) { $progressBar.Value = $pct }
    $newPercent = "$pct%"
    if ($lblPercent.Text -ne $newPercent) { $lblPercent.Text = $newPercent }

    # Update Status Text
    if ($data.status) {
        if ($lblStatus.Text -ne $data.status) { $lblStatus.Text = $data.status }
    }

    # Update Detail Text
    if ($data.detail) {
        if ($lblDetail.Text -ne $data.detail) { $lblDetail.Text = $data.detail }
    }

    # Dynamic Status Color
    $targetColor = [System.Drawing.Color]::FromArgb(137, 220, 235) # Cyan
    if ($phase -eq "queued") {
        $targetColor = [System.Drawing.Color]::FromArgb(249, 226, 175) # Warm Yellow
    } elseif ($phase -eq "error") {
        $targetColor = [System.Drawing.Color]::FromArgb(243, 139, 168) # Red
    } elseif ($isDone) {
        $targetColor = [System.Drawing.Color]::FromArgb(166, 227, 161) # Vibrant Green
    }
    if ($lblStatus.ForeColor -ne $targetColor) {
        $lblStatus.ForeColor = $targetColor
    }

    function Set-AlwaysOnTop {
        if ($form.Handle -ne [IntPtr]::Zero) {
            $form.TopMost = $true
            [Win32WatcherGui]::ShowWindow($form.Handle, 8) | Out-Null
            [Win32WatcherGui]::SetWindowPos($form.Handle, [IntPtr](-1), 0, 0, 0, 0, 0x0043) | Out-Null
        }
    }

    # Show only when actively working or newly finished
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
    if ($isActive) {
        $script:doneTimestamp = 0
        if (-not $form.Visible) {
            Load-WidgetPosition
            $form.Show()
            Set-AlwaysOnTop
            $form.BringToFront()
        } else {
            Set-AlwaysOnTop
        }
    } elseif ($isDone) {
        if ($script:doneTimestamp -eq 0) {
            $script:doneTimestamp = $now
            if (-not $form.Visible) {
                Load-WidgetPosition
                $form.Show()
                Set-AlwaysOnTop
                $form.BringToFront()
            } else {
                Set-AlwaysOnTop
            }
        } elseif ($now - $script:doneTimestamp -gt 4000) {
            # Auto-hide after 4 seconds of completion
            if ($form.Visible) {
                $form.Hide()
            }
        }
    }
}

# --- Timer to Read status.json ---
$script:lastFileModTime = [DateTime]::MinValue
$script:checkCounter = 0
$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 350
$timer.add_Tick({
    try {
        # Keep Always on Top while visible
        if ($form.Visible) {
            [Win32WatcherGui]::SetWindowPos($form.Handle, [IntPtr](-1), 0, 0, 0, 0, 0x0043) | Out-Null
        }

        # Check auto-hide for finished job
        if ($form.Visible -and $script:doneTimestamp -gt 0) {
            $now = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
            if ($now - $script:doneTimestamp -gt 4000) {
                $form.Hide()
            }
        }

        if (Test-Path $statusFile) {
            $fi = Get-Item $statusFile -ErrorAction SilentlyContinue
            if ($fi -and $fi.LastWriteTime -ne $script:lastFileModTime) {
                $script:lastFileModTime = $fi.LastWriteTime
                $rawJson = [System.IO.File]::ReadAllText($statusFile, [System.Text.Encoding]::UTF8)
                if ($rawJson) {
                    $parsed = ConvertFrom-Json $rawJson -ErrorAction SilentlyContinue
                    if ($parsed) {
                        Update-StatusUI $parsed
                    }
                }
            }
        } else {
            if ($form.Visible) { $form.Hide() }
        }
    } catch {}

    # Check if parent python watcher is still alive every ~3.5 seconds
    $script:checkCounter++
    if ($script:checkCounter -ge 10) {
        $script:checkCounter = 0
        $isAlive = $false
        if ($ParentPid -gt 0) {
            $isAlive = [bool](Get-Process -Id $ParentPid -ErrorAction SilentlyContinue)
        } else {
            $isAlive = [bool](Get-Process -Name "python*", "pythonw*" -ErrorAction SilentlyContinue)
        }
        if (-not $isAlive) {
            $form.Close()
            if ($appContext) { $appContext.ExitThread() }
            [System.Windows.Forms.Application]::Exit()
        }
    }
})
$timer.Start()

# Run Application Silently in Background without showing form
$appContext = New-Object System.Windows.Forms.ApplicationContext
[System.Windows.Forms.Application]::Run($appContext)

