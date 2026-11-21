#Requires -Version 5.1
<#
.SYNOPSIS
  Activates one control of the packaged window through UI Automation.

.DESCRIPTION
  Started by silent-controls.test.mjs. Finds the element whose AutomationId
  (the HTML id Chromium exposes) is -AutomationId under the top-level windows
  of process -ProcessId or of a process it started. Chromium builds its tree
  when a client first asks and does not carry an id the page sets afterwards,
  so when no element has that id the one button whose name is -Name is taken;
  names are compared without white space, and more than one such button is a
  failure, never a guess. The control is then activated through the pattern
  an assistive technology uses: Invoke, or where Chromium offers none, Expand
  on a control that opens something and Toggle on a pressed button. Writes
  one JSON line: found, how it was found, invoked, the pattern used and, on
  failure, the error. It sends no keys or clicks, changes no system setting
  and starts nothing.
#>
param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$AutomationId,
    [string]$Name = '',
    [int]$TimeoutMs = 8000
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$Automation = [System.Windows.Automation.AutomationElement]
$Scope = [System.Windows.Automation.TreeScope]
# The window can belong to a process the host started.
$family = @($ProcessId)
$all = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
for ($i = 0; $i -lt $family.Count; $i++) {
    $family += @($all | Where-Object { $_.ParentProcessId -eq $family[$i] } |
        ForEach-Object { [int]$_.ProcessId })
}
$byProcess = New-Object System.Windows.Automation.OrCondition(
    [System.Windows.Automation.Condition[]]@(
        $family | ForEach-Object {
            New-Object System.Windows.Automation.PropertyCondition(
                $Automation::ProcessIdProperty, $_)
        }
        [System.Windows.Automation.Condition]::FalseCondition
    ))
$byId = New-Object System.Windows.Automation.PropertyCondition(
    $Automation::AutomationIdProperty, $AutomationId)
$button = New-Object System.Windows.Automation.PropertyCondition(
    $Automation::ControlTypeProperty, [System.Windows.Automation.ControlType]::Button)
$wanted = $Name -replace '\s', ''

function Find-Control {
    $named = @()
    foreach ($window in $Automation::RootElement.FindAll($Scope::Children, $byProcess)) {
        $found = $window.FindFirst($Scope::Descendants, $byId)
        if ($null -ne $found) { return @{ element = $found; by = 'id' } }
        if ($wanted) {
            $named += @($window.FindAll($Scope::Descendants, $button) |
                Where-Object { ($_.Current.Name -replace '\s', '') -eq $wanted })
        }
    }
    if ($named.Count -eq 1) { return @{ element = $named[0]; by = 'name' } }
    if ($named.Count -gt 1) { throw "$($named.Count) buttons are named '$Name'" }
    return $null
}

function Use-Pattern($control, $pattern) {
    $found = $null
    if ($control.TryGetCurrentPattern($pattern, [ref]$found)) { return $found }
    return $null
}

$reply = @{ found = $false; invoked = $false }
try {
    # The tree is built when it is first asked for, and takes a moment to
    # carry what the page changed just before.
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    $hit = Find-Control
    while ($null -eq $hit -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 150
        $hit = Find-Control
    }
    if ($null -ne $hit) {
        $control = $hit.element
        $reply.found = $true
        $reply.by = $hit.by
        $patterns = [System.Windows.Automation.InvokePattern]::Pattern,
            [System.Windows.Automation.ExpandCollapsePattern]::Pattern,
            [System.Windows.Automation.TogglePattern]::Pattern
        foreach ($pattern in $patterns) {
            $use = Use-Pattern $control $pattern
            if ($null -eq $use) { continue }
            if ($use -is [System.Windows.Automation.InvokePattern]) { $use.Invoke() }
            elseif ($use -is [System.Windows.Automation.ExpandCollapsePattern]) { $use.Expand() }
            else { $use.Toggle() }
            $reply.pattern = $pattern.ProgrammaticName
            $reply.invoked = $true
            break
        }
        if (-not $reply.invoked) {
            $reply.error = 'no Invoke, Expand or Toggle: ' + (($control.GetSupportedPatterns() |
                ForEach-Object { $_.ProgrammaticName }) -join ' ')
        }
    }
}
catch {
    $reply.error = $_.Exception.Message
}
$reply | ConvertTo-Json -Compress
