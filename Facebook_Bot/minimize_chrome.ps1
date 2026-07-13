Add-Type @"
  using System;
  using System.Runtime.InteropServices;
  public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  }
"@

# SW_MINIMIZE = 6
Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | ForEach-Object {
  [Win32]::ShowWindow($_.MainWindowHandle, 6) | Out-Null
  Write-Host "Minimized Chrome window: $($_.Id)"
}
