$DesktopPath = [Environment]::GetFolderPath('Desktop')
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\CropConnect.lnk")
$Shortcut.TargetPath = 'd:\crop connect\cropconnect01-master\Start-CropConnect.bat'
$Shortcut.WorkingDirectory = 'd:\crop connect\cropconnect01-master'
$Shortcut.IconLocation = 'c:\Windows\System32\cmd.exe,0'
$Shortcut.Save()
Write-Host 'Desktop shortcut "CropConnect.lnk" created successfully!'
