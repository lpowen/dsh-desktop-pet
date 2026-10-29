Option Explicit
' Silently restart the desktop pet (fallback when it cannot be shown again).
Dim sh, fso, here, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
here = fso.GetParentFolderName(WScript.ScriptFullName)
cmd = "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & here & "\restart-pet.ps1"""
sh.Run cmd, 0, False
