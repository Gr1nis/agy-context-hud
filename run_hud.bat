@echo off
cd /d "%~dp0"
powershell -NoProfile -WindowStyle Hidden -Command "$s = New-Object -ComObject Shell.Application; $s.ShellExecute('pythonw.exe', '\"C:\Users\MIXPC\.gemini\antigravity\scratch\agy-context-hud\hud_app.py\"', 'C:\Users\MIXPC\.gemini\antigravity\scratch\agy-context-hud', 'open', 1)"
