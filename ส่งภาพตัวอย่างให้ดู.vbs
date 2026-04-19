Set WshShell = CreateObject("WScript.Shell")
' Run the python script in the same directory as the VBScript
' 0 = Hide window
WshShell.Run "python """ & CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName) & "\screenshot_selection.py""", 0, False
