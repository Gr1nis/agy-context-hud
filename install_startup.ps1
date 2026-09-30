$WshShell = New-Object -ComObject WScript.Shell
$Startup = [Environment]::GetFolderPath("Startup")
$Shortcut = $WshShell.CreateShortcut("$Startup\AGY Context HUD.lnk")
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Shortcut.TargetPath = "$ScriptDir\run_hud.bat"
$Shortcut.WorkingDirectory = "$ScriptDir"
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Always-on-Top Antigravity Context HUD"
$Shortcut.Save()
Write-Host "✓ AGY Context HUD зарегистрирован в автозагрузке Windows: $Startup\AGY Context HUD.lnk" -ForegroundColor Green
