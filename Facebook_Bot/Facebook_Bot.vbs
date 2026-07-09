Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

botDir = fso.GetParentFolderName(WScript.ScriptFullName)
trayGuiScript = botDir & "\tray_gui.ps1"
statusFile = botDir & "\status.json"

' 0. ลบ status.json เดิมทิ้ง ป้องกันค่าเก่าค้าง (เช่น 10/10)
If fso.FileExists(statusFile) Then fso.DeleteFile statusFile, True

' 1. รัน Tray GUI & Status Widget แบบซ่อนหน้าต่าง Console
WshShell.Run "powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File """ & trayGuiScript & """", 0, False

WScript.Sleep 1000

' 2. รัน node bot.js --bot แบบซ่อนหน้าต่าง cmd (ไม่รอให้เสร็จ)
WshShell.Run "cmd /c cd /d """ & botDir & """ && node bot.js --bot", 0, False
