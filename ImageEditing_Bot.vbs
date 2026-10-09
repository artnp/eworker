Set fso = CreateObject("Scripting.FileSystemObject")
Set WshShell = CreateObject("WScript.Shell")

botDir = fso.GetParentFolderName(WScript.ScriptFullName)
guiScript = botDir & "\watcher_gui.ps1"
pyScript = botDir & "\auto_donate_watcher.py"
statusFile = botDir & "\status.json"

' Reset status.json on startup
If fso.FileExists(statusFile) Then fso.DeleteFile statusFile, True

' 1. รัน Floating Loading Process Bar Widget (เหมือน Facebook_Bot)
WshShell.Run "powershell -WindowStyle Hidden -NoProfile -ExecutionPolicy Bypass -File """ & guiScript & """", 0, False

WScript.Sleep 400

' 2. รัน AI Hub Central Watcher Daemon (Python)
WshShell.CurrentDirectory = botDir
WshShell.Run "cmd /c pythonw """ & pyScript & """", 0, False

