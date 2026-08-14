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

# Move Chrome window offscreen (X=10000, Y=10000) so it continues rendering in background without throttling
Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | ForEach-Object {
  [Win32]::ShowWindow($_.MainWindowHandle, 4) | Out-Null # SW_SHOWNOACTIVATE
  [Win32]::SetWindowPos($_.MainWindowHandle, [IntPtr]::Zero, 10000, 10000, 1280, 800, 0x0054) | Out-Null # SWP_NOACTIVATE | SWP_NOZORDER | SWP_SHOWWINDOW
  Write-Host "Moved Chrome window offscreen: $($_.Id)"
}
