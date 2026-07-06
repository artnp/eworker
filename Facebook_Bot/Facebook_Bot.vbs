Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

' กำหนดพาธต่างๆ แบบ Dynamic ของ Facebook_Bot (แยกอิสระจาก ImageEditing_Bot)
botDir = fso.GetParentFolderName(WScript.ScriptFullName)
trayGuiScript = botDir & "\tray_gui.ps1"

' 1. เริ่มต้นรัน Tray GUI & Status Widget ของ Facebook Bot แบบซ่อนหน้าต่าง Console
WshShell.Run "powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File """ & trayGuiScript & """", 0, False

' รอ 1 วินาทีให้ Status Widget และ File IPC พร้อมทำงาน
WScript.Sleep 1000

' 2. รัน node bot.js --bot แบบซ่อนหน้าต่าง cmd (0) ( Chrome รันแบบแสดงเพื่อสลับได้ แต่เปิดย่อเก็บไว้ )
WshShell.Run "cmd /c cd /d """ & botDir & """ && node bot.js --bot", 0, True