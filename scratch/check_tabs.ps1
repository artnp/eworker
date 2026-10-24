$code = @'
using System;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class WinEnumNoFilter {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder strText, int maxCount);

    public static List<string> Run() {
        var list = new List<string>();
        EnumWindows((h, l) => {
            var sb = new StringBuilder(512);
            GetWindowText(h, sb, 512);
            string s = sb.ToString();
            if (s.Length > 2) list.Add(s);
            return true;
        }, IntPtr.Zero);
        return list;
    }
}
'@
Add-Type -TypeDefinition $code
[WinEnumNoFilter]::Run() | Select-Object -First 20
