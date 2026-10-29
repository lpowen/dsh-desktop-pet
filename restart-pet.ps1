# 静默重启桌宠（隐藏后找不回来、或卡住时的兜底）
$ErrorActionPreference = 'SilentlyContinue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonw = '$(Join-Path $env:USERPROFILE '.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\pythonw.exe')'

Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" |
  Where-Object { $_.CommandLine -like '*pet.py*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Start-Sleep -Seconds 1
Start-Process -FilePath $pythonw -ArgumentList 'pet.py' -WorkingDirectory $here -WindowStyle Hidden
