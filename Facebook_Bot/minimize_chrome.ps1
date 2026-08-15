Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  }
"@

# Move & tuck window to bottom-right corner of Screen 2 (X=3800, Y=1000)
Get-Process -ErrorAction SilentlyContinue | Where-Object { 
  ($_.ProcessName -like "*chrome*" -or $_.ProcessName -like "*chromium*" -or $_.ProcessName -like "*msedge*") -and 
  $_.MainWindowHandle -ne [IntPtr]::Zero 
} | ForEach-Object {
  [Win32]::ShowWindow($_.MainWindowHandle, 4) | Out-Null # SW_SHOWNOACTIVATE
  [Win32]::SetWindowPos($_.MainWindowHandle, [IntPtr]1, 3800, 1000, 1280, 800, 0x0054) | Out-Null # SWP_NOACTIVATE | SWP_NOZORDER | SWP_SHOWWINDOW
  Write-Host "Tucked away $($_.ProcessName) ($($_.Id)) on Screen 2"
}


