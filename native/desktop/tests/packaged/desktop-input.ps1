#Requires -Version 5.1
<#
.SYNOPSIS
  Window, input and process queries for the packaged desktop test.

.DESCRIPTION
  Started by packaged.test.mjs. Reads one JSON request per line on standard
  input and writes one JSON reply per line. Keys and clicks are sent only while
  the foreground window belongs to the process the request names, so input
  never reaches another application. It changes no system setting and starts
  nothing.
#>
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class CadrumoDesktopInput {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public IntPtr extra; }
    [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort vk, scan; public uint flags, time; public IntPtr extra; }
    [StructLayout(LayoutKind.Explicit)] struct UNION { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; }
    [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public UNION u; }
    delegate bool EnumProc(IntPtr hwnd, IntPtr lparam);

    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hwnd, int command);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool AttachThreadInput(uint attach, uint to, bool on);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc proc, IntPtr lparam);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr hwnd, uint command);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, StringBuilder text, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr hwnd, StringBuilder text, int size);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hwnd, uint message, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern uint SendInput(uint count, INPUT[] inputs, int size);
    [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr hwnd, ref POINT point);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);

    public static void PhysicalPixels() { SetProcessDpiAwarenessContext(new IntPtr(-4)); }

    public static bool InputDesktop() {
        IntPtr desktop = OpenInputDesktop(0, false, 0x0100);
        if (desktop == IntPtr.Zero) return false;
        CloseDesktop(desktop);
        return true;
    }

    public static uint ProcessOf(IntPtr hwnd) { uint pid; GetWindowThreadProcessId(hwnd, out pid); return pid; }

    public static uint ForegroundProcess() { return ProcessOf(GetForegroundWindow()); }

    public static string Text(IntPtr hwnd, bool className) {
        StringBuilder text = new StringBuilder(256);
        if (className) GetClassName(hwnd, text, 256); else GetWindowText(hwnd, text, 256);
        return text.ToString();
    }

    public static List<object[]> Windows(uint[] pids) {
        HashSet<uint> wanted = new HashSet<uint>(pids);
        List<object[]> found = new List<object[]>();
        EnumWindows(delegate (IntPtr hwnd, IntPtr l) {
            uint pid = ProcessOf(hwnd);
            if (wanted.Contains(pid) && IsWindowVisible(hwnd))
                found.Add(new object[] { hwnd.ToInt64(), pid, Text(hwnd, true), Text(hwnd, false), GetWindow(hwnd, 4).ToInt64() });
            return true;
        }, IntPtr.Zero);
        return found;
    }

    public static IntPtr MainWindow(uint pid) {
        IntPtr best = IntPtr.Zero;
        EnumWindows(delegate (IntPtr hwnd, IntPtr l) {
            if (ProcessOf(hwnd) == pid && IsWindowVisible(hwnd) && GetWindow(hwnd, 4) == IntPtr.Zero && Text(hwnd, false).Length > 0) {
                best = hwnd;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return best;
    }

    public static bool Activate(IntPtr hwnd) {
        if (IsIconic(hwnd)) ShowWindow(hwnd, 9);
        uint ignored;
        uint target = GetWindowThreadProcessId(hwnd, out ignored);
        uint current = GetCurrentThreadId();
        uint foreground = GetWindowThreadProcessId(GetForegroundWindow(), out ignored);
        AttachThreadInput(current, foreground, true);
        AttachThreadInput(current, target, true);
        BringWindowToTop(hwnd);
        bool done = SetForegroundWindow(hwnd);
        AttachThreadInput(current, target, false);
        AttachThreadInput(current, foreground, false);
        return done;
    }

    public static int[] ClientOrigin(IntPtr hwnd) {
        POINT origin = new POINT();
        ClientToScreen(hwnd, ref origin);
        RECT rect;
        GetClientRect(hwnd, out rect);
        return new int[] { origin.X, origin.Y, rect.Right, rect.Bottom };
    }

    public static bool Post(IntPtr hwnd, uint message) { return PostMessage(hwnd, message, IntPtr.Zero, IntPtr.Zero); }

    static INPUT Key(ushort vk, bool up) {
        INPUT input = new INPUT();
        input.type = 1;
        input.u.ki.vk = vk;
        input.u.ki.flags = up ? 2u : 0u;
        return input;
    }

    static INPUT Mouse(uint flags) {
        INPUT input = new INPUT();
        input.type = 0;
        input.u.mi.dwFlags = flags;
        return input;
    }

    public static uint Chord(ushort[] modifiers, ushort key) {
        List<INPUT> inputs = new List<INPUT>();
        foreach (ushort modifier in modifiers) inputs.Add(Key(modifier, false));
        inputs.Add(Key(key, false));
        inputs.Add(Key(key, true));
        for (int i = modifiers.Length - 1; i >= 0; i--) inputs.Add(Key(modifiers[i], true));
        return SendInput((uint)inputs.Count, inputs.ToArray(), Marshal.SizeOf(typeof(INPUT)));
    }

    public static uint Click(int x, int y, bool right) {
        SetCursorPos(x, y);
        INPUT[] inputs = new INPUT[] { Mouse(right ? 0x0008u : 0x0002u), Mouse(right ? 0x0010u : 0x0004u) };
        return SendInput(2, inputs, Marshal.SizeOf(typeof(INPUT)));
    }
}
'@

[CadrumoDesktopInput]::PhysicalPixels()

$VirtualKeys = @{
    'control' = 0x11; 'shift' = 0x10; 'alt' = 0x12; 'escape' = 0x1B; 'enter' = 0x0D
    'f5' = 0x74; 'f12' = 0x7B; 'r' = 0x52; 'p' = 0x50; 'f' = 0x46; 'k' = 0x4B; 'i' = 0x49
    'plus' = 0xBB; 'minus' = 0xBD; 'zero' = 0x30
}

function Get-Window([uint32]$ProcessId) {
    $hwnd = [CadrumoDesktopInput]::MainWindow($ProcessId)
    if ($hwnd -eq [IntPtr]::Zero) { throw "process $ProcessId has no visible main window" }
    return $hwnd
}

function Assert-Foreground([uint32]$ProcessId) {
    $owner = [CadrumoDesktopInput]::ForegroundProcess()
    if ($owner -ne $ProcessId) { throw "the foreground window belongs to process $owner, not $ProcessId; input withheld" }
}

function Invoke-Request($request) {
    switch ($request.op) {
        'session' {
            return @{
                sessionId    = [Diagnostics.Process]::GetCurrentProcess().SessionId
                inputDesktop = [CadrumoDesktopInput]::InputDesktop()
            }
        }
        'windows' {
            $list = [CadrumoDesktopInput]::Windows([uint32[]]@($request.pids))
            return ,@($list | ForEach-Object {
                    @{ hwnd = [long]$_[0]; pid = [long]$_[1]; class = [string]$_[2]; title = [string]$_[3]; owner = [long]$_[4] }
                })
        }
        'activate' {
            $hwnd = Get-Window $request.pid
            [void][CadrumoDesktopInput]::Activate($hwnd)
            Start-Sleep -Milliseconds 300
            return @{ foreground = [CadrumoDesktopInput]::ForegroundProcess() }
        }
        'client' {
            $hwnd = Get-Window $request.pid
            $origin = [CadrumoDesktopInput]::ClientOrigin($hwnd)
            return @{ x = $origin[0]; y = $origin[1]; width = $origin[2]; height = $origin[3] }
        }
        'chord' {
            Assert-Foreground $request.pid
            $modifiers = [uint16[]]@($request.modifiers | ForEach-Object { $VirtualKeys[$_] })
            $key = $VirtualKeys[[string]$request.key]
            if ($null -eq $key) { throw "unknown key $($request.key)" }
            return @{ sent = [CadrumoDesktopInput]::Chord($modifiers, [uint16]$key) }
        }
        'click' {
            Assert-Foreground $request.pid
            return @{ sent = [CadrumoDesktopInput]::Click([int]$request.x, [int]$request.y, [bool]$request.right) }
        }
        'post' {
            $messages = @{ 'close' = 0x0010; 'cancelmode' = 0x001F }
            $handle = $request.PSObject.Properties['hwnd']
            $target = if ($handle -and $handle.Value) { [IntPtr][long]$handle.Value } else { Get-Window $request.pid }
            return @{ posted = [CadrumoDesktopInput]::Post($target, [uint32]$messages[[string]$request.message]) }
        }
        'processes' {
            $names = @($request.names)
            $all = @(Get-CimInstance Win32_Process | Where-Object { $names -contains $_.Name })
            return ,@($all | ForEach-Object {
                    @{
                        pid         = [long]$_.ProcessId
                        ppid        = [long]$_.ParentProcessId
                        name        = [string]$_.Name
                        created     = if ($_.CreationDate) { $_.CreationDate.ToString('o') } else { '' }
                        commandLine = [string]$_.CommandLine
                    }
                })
        }
        default { throw "unknown request $($request.op)" }
    }
}

[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    if (-not $line.Trim()) { continue }
    $request = $line | ConvertFrom-Json
    try {
        $reply = @{ id = $request.id; ok = $true; result = (Invoke-Request $request) }
    } catch {
        $reply = @{ id = $request.id; ok = $false; error = $_.Exception.Message }
    }
    [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 6))
    [Console]::Out.Flush()
}
