@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\OEM\configure-remoting.ps1
exit /b %errorlevel%
