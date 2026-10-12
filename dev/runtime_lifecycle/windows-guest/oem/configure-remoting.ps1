# Runs only inside the disposable guest. Installs no development tools.
$ErrorActionPreference = 'Stop'
Enable-PSRemoting -Force -SkipNetworkProfileCheck
Get-ChildItem WSMan:\localhost\Listener |
    Where-Object { $_.Keys -contains 'Transport=HTTP' } |
    Remove-Item -Recurse -Force
$guestCertificate = New-SelfSignedCertificate -DnsName CadrumoGuest,localhost -CertStoreLocation Cert:\LocalMachine\My
New-Item WSMan:\localhost\Listener -Transport HTTPS -Address '*' -CertificateThumbPrint $guestCertificate.Thumbprint -Force | Out-Null
Set-Item WSMan:\localhost\Service\AllowUnencrypted $false
Set-Item WSMan:\localhost\Service\Auth\Basic $false
Get-NetFirewallRule -Name 'WINRM-HTTP-In-TCP*' -ErrorAction SilentlyContinue | Disable-NetFirewallRule
New-NetFirewallRule -Name CadrumoGuestWinRMHTTPS -DisplayName 'Cadrumo disposable guest HTTPS commands' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5986 | Out-Null
# Local disposable administrators need their full token for the installation lane.
New-ItemProperty -Path HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System -Name LocalAccountTokenFilterPolicy -Value 1 -PropertyType DWord -Force | Out-Null
Set-Service WinRM -StartupType Automatic
Start-Service WinRM
Export-Certificate -Cert $guestCertificate -FilePath C:\OEM\winrm-public.cer | Out-Null
$guestSystem = Get-CimInstance Win32_ComputerSystem
$guestProduct = Get-CimInstance Win32_ComputerSystemProduct
@{
    uuid = $guestProduct.UUID
    manufacturer = $guestSystem.Manufacturer
    model = $guestSystem.Model
    winrmCertificateThumbprint = $guestCertificate.Thumbprint
} | ConvertTo-Json | Set-Content C:\OEM\guest-ready.json -Encoding UTF8
