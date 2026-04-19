Set WshShell = CreateObject("WScript.Shell")
' Run the donate watcher daemon in the system tray
WshShell.Run "pythonw """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\auto_donate_watcher.py""", 0, False
