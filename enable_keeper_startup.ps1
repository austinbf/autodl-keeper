$ErrorActionPreference = 'Stop'
$python = (Resolve-Path (Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe')).Path
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument 'keeper_web.py' -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName 'AutoDL Keeper' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
