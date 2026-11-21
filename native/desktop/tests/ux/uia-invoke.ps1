#Requires -Version 5.1
<#
.SYNOPSIS
  Activates one control of the packaged window through UI Automation.

.DESCRIPTION
  Started by silent-controls.test.mjs. Finds the element whose AutomationId
  (the HTML id Chromium exposes) is -AutomationId under the top-level windows
  of process -ProcessId or of a process it started, and calls its Invoke
  pattern, as an assistive technology or an automation client does; where the
  control has no Invoke (Chromium offers Expand instead on a control that
  opens something) it calls the control's MSAA default action, as a screen
  reader does. Writes one JSON line: found, invoked, the patterns and default
  action used when there was no Invoke and, on failure, the error. It sends no
  keys or clicks, changes no system setting and starts nothing.
#>
param(
    [Parameter(Mandatory = $true)][int]$ProcessId,
    [Parameter(Mandatory = $true)][string]$AutomationId,
    [int]$TimeoutMs = 3000
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

function Find-Control {
    foreach ($window in $Automation::RootElement.FindAll($Scope::Children, $byProcess)) {
        $found = $window.FindFirst($Scope::Descendants, $byId)
        if ($null -ne $found) { return $found }
    }
    return $null
}

Add-Type -ReferencedAssemblies Accessibility -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Accessibility;
public static class DefaultAction {
    [DllImport("oleacc.dll")]
    static extern int AccessibleObjectFromWindow(
        IntPtr hwnd, uint id, ref Guid iid,
        [MarshalAs(UnmanagedType.Interface)] out object accessible);
    // Chromium answers a negative child id with the node of that unique id:
    // the last part of the element's UI Automation runtime id.
    public static string Do(IntPtr window, int uniqueId) {
        Guid iid = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71");
        object found;
        int hr = AccessibleObjectFromWindow(window, 0xFFFFFFFC, ref iid, out found);
        if (hr != 0) Marshal.ThrowExceptionForHR(hr);
        IAccessible root = (IAccessible)found;
        object child = -uniqueId;
        string verb = root.get_accDefaultAction(child);
        root.accDoDefaultAction(child);
        return verb;
    }
}
'@

function Invoke-DefaultAction($control) {
    $walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
    $window = $control
    while ($null -ne $window -and $window.Current.NativeWindowHandle -eq 0) {
        $window = $walker.GetParent($window)
    }
    if ($null -eq $window) { throw 'no window holds the control' }
    $id = $control.GetRuntimeId()
    return [DefaultAction]::Do(
        [IntPtr]$window.Current.NativeWindowHandle, $id[$id.Length - 1])
}

$reply = @{ found = $false; invoked = $false }
try {
    # The accessibility tree takes a moment to carry an id set just before.
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMs)
    $control = Find-Control
    while ($null -eq $control -and [DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 150
        $control = Find-Control
    }
    if ($null -ne $control) {
        $reply.found = $true
        $invoke = $null
        if ($control.TryGetCurrentPattern(
                [System.Windows.Automation.InvokePattern]::Pattern, [ref]$invoke)) {
            $invoke.Invoke()
            $reply.invoked = $true
        }
        else {
            # Chromium offers no Invoke on a control that opens something
            # (it offers Expand instead); a screen reader activates it through
            # its default action, so that is what is called here.
            $reply.patterns = @($control.GetSupportedPatterns() |
                ForEach-Object { $_.ProgrammaticName })
            $reply.defaultAction = Invoke-DefaultAction $control
            $reply.invoked = $true
        }
    }
}
catch {
    $reply.error = $_.Exception.Message
}
$reply | ConvertTo-Json -Compress
