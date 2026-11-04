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
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll")] static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsChild(IntPtr parent, IntPtr candidate);
    [DllImport("user32.dll", EntryPoint = "GetWindowLongW")] static extern int GetWindowLong(IntPtr hwnd, int index);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll")] static extern IntPtr OpenInputDesktop(uint flags, bool inherit, uint access);
    [DllImport("user32.dll")] static extern bool CloseDesktop(IntPtr desktop);

    public const int MsaaToolTipRole = 13;
    [DllImport("oleacc.dll")] static extern int AccessibleObjectFromWindow(IntPtr hwnd, uint objectId, ref Guid iid, out IntPtr accessible);
    [DllImport("oleacc.dll")] static extern int WindowFromAccessibleObject(IntPtr accessible, out IntPtr hwnd);
    [DllImport("oleaut32.dll")] static extern int VariantClear(IntPtr variant);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ReadRole(IntPtr self, [MarshalAs(UnmanagedType.Struct)] object child, IntPtr value);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ReadName(IntPtr self, [MarshalAs(UnmanagedType.Struct)] object child, out IntPtr value);

    public static IntPtr MsaaRoot(IntPtr hwnd) {
        Guid iid = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71");
        IntPtr accessible;
        int status = AccessibleObjectFromWindow(hwnd, unchecked((uint)-4), ref iid, out accessible);
        if (status != 0 || accessible == IntPtr.Zero) {
            if (accessible != IntPtr.Zero) Marshal.Release(accessible);
            throw new InvalidOperationException("MSAA root unavailable");
        }
        return accessible;
    }

    public static IntPtr MsaaWindow(IntPtr accessible) {
        IntPtr hwnd;
        if (WindowFromAccessibleObject(accessible, out hwnd) != 0) throw new InvalidOperationException("MSAA root window unavailable");
        return hwnd;
    }

    public static object MsaaRole(IntPtr accessible) {
        // IAccessible's SDK vtable: IUnknown/IDispatch, then get_accRole at slot 13.
        IntPtr entry = Marshal.ReadIntPtr(Marshal.ReadIntPtr(accessible), 13 * IntPtr.Size);
        ReadRole read = (ReadRole)Marshal.GetDelegateForFunctionPointer(entry, typeof(ReadRole));
        int size = IntPtr.Size == 8 ? 24 : 16;
        IntPtr value = Marshal.AllocCoTaskMem(size);
        for (int i = 0; i < size; i++) Marshal.WriteByte(value, i, 0);
        try {
            if (read(accessible, 0, value) != 0) throw new InvalidOperationException("MSAA role unavailable");
            if (Marshal.ReadInt16(value) != 3) return null;
            return Marshal.ReadInt32(value, 8);
        } finally { try { VariantClear(value); } finally { Marshal.FreeCoTaskMem(value); } }
    }

    public static bool MsaaNameMatches(IntPtr accessible, string expected) {
        // CHILDID_SELF only; get_accName is slot 10 in the same SDK vtable.
        IntPtr entry = Marshal.ReadIntPtr(Marshal.ReadIntPtr(accessible), 10 * IntPtr.Size);
        ReadName read = (ReadName)Marshal.GetDelegateForFunctionPointer(entry, typeof(ReadName));
        IntPtr name = IntPtr.Zero;
        try {
            if (read(accessible, 0, out name) != 0 || name == IntPtr.Zero) throw new InvalidOperationException("MSAA tooltip name unavailable");
            return String.Equals(Marshal.PtrToStringBSTR(name), expected, StringComparison.Ordinal);
        } finally { if (name != IntPtr.Zero) Marshal.FreeBSTR(name); }
    }

    public sealed class MsaaChild {
        public int ChildId;
        public IntPtr Accessible;
    }
    [DllImport("oleacc.dll")] static extern int AccessibleChildren(IntPtr accessible, int start, int count, IntPtr children, out int obtained);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ReadChildCount(IntPtr self, out int count);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int QueryAccessible(IntPtr self, ref Guid iid, out IntPtr accessible);
    static int MsaaQueryInterface(IntPtr dispatch, ref Guid iid, out IntPtr accessible) {
        IntPtr entry = Marshal.ReadIntPtr(Marshal.ReadIntPtr(dispatch));
        QueryAccessible query = (QueryAccessible)Marshal.GetDelegateForFunctionPointer(entry, typeof(QueryAccessible));
        return query(dispatch, ref iid, out accessible);
    }

    public static int MsaaChildCount(IntPtr accessible) {
        IntPtr entry = Marshal.ReadIntPtr(Marshal.ReadIntPtr(accessible), 8 * IntPtr.Size);
        ReadChildCount read = (ReadChildCount)Marshal.GetDelegateForFunctionPointer(entry, typeof(ReadChildCount));
        int count;
        if (read(accessible, out count) != 0 || count < 0) throw new InvalidOperationException("MSAA child count unavailable");
        return count;
    }

    public static MsaaChild[] MsaaChildren(IntPtr accessible, int count) {
        if (count < 1 || count > 15) throw new InvalidOperationException("MSAA enumeration budget invalid");
        int size = IntPtr.Size == 8 ? 24 : 16;
        IntPtr values = Marshal.AllocCoTaskMem(size * count);
        for (int i = 0; i < size * count; i++) Marshal.WriteByte(values, i, 0);
        List<MsaaChild> children = new List<MsaaChild>();
        List<IntPtr> owned = new List<IntPtr>();
        try {
            try {
                int obtained;
                if (AccessibleChildren(accessible, 0, count, values, out obtained) != 0 || obtained != count)
                    throw new InvalidOperationException("MSAA enumeration incomplete");
                for (int i = 0; i < count; i++) {
                    IntPtr value = IntPtr.Add(values, i * size);
                    short kind = Marshal.ReadInt16(value);
                    if (kind == 3) {
                        int id = Marshal.ReadInt32(value, 8);
                        if (id <= 0) throw new InvalidOperationException("MSAA child ID unsupported");
                        children.Add(new MsaaChild { ChildId = id, Accessible = IntPtr.Zero });
                    } else if (kind == 9) {
                        IntPtr dispatch = Marshal.ReadIntPtr(value, 8);
                        if (dispatch == IntPtr.Zero) throw new InvalidOperationException("MSAA dispatch unavailable");
                        Guid iid = new Guid("618736E0-3C3D-11CF-810C-00AA00389B71");
                        IntPtr child;
                        int status = MsaaQueryInterface(dispatch, ref iid, out child);
                        if (status != 0 || child == IntPtr.Zero) {
                            if (child != IntPtr.Zero) Marshal.Release(child);
                            throw new InvalidOperationException("MSAA child interface unavailable");
                        }
                        owned.Add(child);
                        children.Add(new MsaaChild { ChildId = 0, Accessible = child });
                    } else throw new InvalidOperationException("MSAA child variant unsupported");
                }
                return children.ToArray();
            } finally {
                bool cleared = true;
                try {
                    for (int i = 0; i < count; i++) {
                        try { if (VariantClear(IntPtr.Add(values, i * size)) != 0) cleared = false; }
                        catch { cleared = false; }
                    }
                } finally { Marshal.FreeCoTaskMem(values); }
                if (!cleared) throw new InvalidOperationException("MSAA variants release unavailable");
            }
        } catch {
            foreach (IntPtr child in owned) { try { Marshal.Release(child); } catch { } }
            throw new InvalidOperationException("MSAA enumeration unavailable or incomplete");
        }
    }

    public static object MsaaTreeRole(IntPtr accessible, int childId) {
        if (childId < 0) throw new InvalidOperationException("MSAA child ID unsupported");
        IntPtr entry = Marshal.ReadIntPtr(Marshal.ReadIntPtr(accessible), 13 * IntPtr.Size);
        ReadRole read = (ReadRole)Marshal.GetDelegateForFunctionPointer(entry, typeof(ReadRole));
        int size = IntPtr.Size == 8 ? 24 : 16;
        IntPtr value = Marshal.AllocCoTaskMem(size);
        for (int i = 0; i < size; i++) Marshal.WriteByte(value, i, 0);
        try {
            if (read(accessible, childId, value) != 0) throw new InvalidOperationException("MSAA role unavailable");
            if (Marshal.ReadInt16(value) != 3) return null;
            return Marshal.ReadInt32(value, 8);
        } finally { try { VariantClear(value); } finally { Marshal.FreeCoTaskMem(value); } }
    }

    public static bool MsaaTreeNameMatches(IntPtr accessible, int childId, string expected) {
        if (childId < 0) throw new InvalidOperationException("MSAA child ID unsupported");
        IntPtr entry = Marshal.ReadIntPtr(Marshal.ReadIntPtr(accessible), 10 * IntPtr.Size);
        ReadName read = (ReadName)Marshal.GetDelegateForFunctionPointer(entry, typeof(ReadName));
        IntPtr name = IntPtr.Zero;
        try {
            if (read(accessible, childId, out name) != 0 || name == IntPtr.Zero) throw new InvalidOperationException("MSAA tooltip name unavailable");
            return String.Equals(Marshal.PtrToStringBSTR(name), expected, StringComparison.Ordinal);
        } finally { if (name != IntPtr.Zero) Marshal.FreeBSTR(name); }
    }

    public static void ReleaseMsaaRoot(IntPtr accessible) { Marshal.Release(accessible); }

    public static void PhysicalPixels() { SetProcessDpiAwarenessContext(new IntPtr(-4)); }

    public static bool InputDesktop() {
        IntPtr desktop = OpenInputDesktop(0, false, 0x0100);
        if (desktop == IntPtr.Zero) return false;
        CloseDesktop(desktop);
        return true;
    }

    public static uint ProcessOf(IntPtr hwnd) { uint pid; GetWindowThreadProcessId(hwnd, out pid); return pid; }

    public static uint ForegroundProcess() { return ProcessOf(GetForegroundWindow()); }

    public static bool IsChildOf(IntPtr root, IntPtr candidate) { return IsChild(root, candidate); }

    public static Dictionary<string, object> WindowMetadata(IntPtr hwnd, uint[] pids) {
        HashSet<uint> wanted = new HashSet<uint>(pids);
        uint pid = ProcessOf(hwnd);
        if (!wanted.Contains(pid)) throw new InvalidOperationException("window no longer belongs to supplied process scope");
        Dictionary<string, object> result = new Dictionary<string, object>();
        result["hwnd"] = hwnd.ToInt64();
        result["pid"] = pid;
        result["parent"] = GetParent(hwnd).ToInt64();
        result["owner"] = GetWindow(hwnd, 4).ToInt64();
        result["visible"] = IsWindowVisible(hwnd);
        result["style"] = unchecked((uint)GetWindowLong(hwnd, -16));
        result["extendedStyle"] = unchecked((uint)GetWindowLong(hwnd, -20));
        IntPtr foreground = GetForegroundWindow();
        result["foreground"] = hwnd == foreground;
        result["foregroundHwnd"] = foreground.ToInt64();
        result["foregroundInScope"] = wanted.Contains(ProcessOf(foreground));
        RECT rect;
        if (GetWindowRect(hwnd, out rect))
            result["windowBounds"] = new int[] { rect.Left, rect.Top, rect.Right - rect.Left, rect.Bottom - rect.Top };
        else result["windowBoundsError"] = "GetWindowRect failed";
        POINT origin = new POINT();
        if (GetClientRect(hwnd, out rect) && ClientToScreen(hwnd, ref origin))
            result["clientBounds"] = new int[] { origin.X, origin.Y, rect.Right - rect.Left, rect.Bottom - rect.Top };
        else result["clientBoundsError"] = "GetClientRect or ClientToScreen failed";
        return result;
    }

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

function Get-RoleNodeScope($Element, [long]$Handle, [uint32]$OwnerProcess, [int]$Depth, [bool]$AncestorAdmitted) {
    $scope = @{
        admitted = $false; depth = $Depth; uiPidKnown = $null; uiPidMatchesRoot = $null
        hasNativeHwnd = $null; nativeHwndEqualsRoot = $null
        win32PidKnown = $null; win32PidMatchesRoot = $null; isChildOfRequestedRoot = $null
        ancestorAdmitted = $AncestorAdmitted
    }
    try {
        [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($OwnerProcess))
        $uiPid = $Element.Current.ProcessId
        if ($null -eq $uiPid) { throw 'UIA PID getter unavailable' }
        $scope.uiPidKnown = $uiPid -gt 0
        $scope.uiPidMatchesRoot = $uiPid -eq $OwnerProcess
        if (-not $scope.uiPidKnown) { $scope['diagnosticError'] = 'UIA PID unavailable'; return $scope }
        if (-not $scope.uiPidMatchesRoot) { $scope['diagnosticError'] = 'UIA PID outside requested root'; return $scope }
        [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($OwnerProcess))
        $native = $Element.Current.NativeWindowHandle
        if ($null -eq $native) { throw 'UIA HWND getter unavailable' }
        $native = [long]$native
        $scope.hasNativeHwnd = $native -ne 0
        $scope.nativeHwndEqualsRoot = $native -eq $Handle
        if ($native -eq 0) {
            if ($Depth -eq 0 -or -not $AncestorAdmitted) {
                $scope['diagnosticError'] = 'UIA zero HWND lacks admitted ancestry'
                return $scope
            }
        } else {
            [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($OwnerProcess))
            $nativePid = [CadrumoDesktopInput]::ProcessOf([IntPtr]$native)
            $scope.win32PidKnown = $nativePid -gt 0
            $scope.win32PidMatchesRoot = $nativePid -eq $OwnerProcess
            if (-not $scope.win32PidKnown) { $scope['diagnosticError'] = 'UIA HWND unavailable'; return $scope }
            if (-not $scope.win32PidMatchesRoot) { $scope['diagnosticError'] = 'UIA HWND PID outside requested root'; return $scope }
            if (-not $scope.nativeHwndEqualsRoot) {
                $scope.isChildOfRequestedRoot = [CadrumoDesktopInput]::IsChildOf([IntPtr]$Handle, [IntPtr]$native)
                if (-not $scope.isChildOfRequestedRoot) {
                    $scope['diagnosticError'] = 'UIA HWND outside requested root ancestry'
                    return $scope
                }
            }
            if ([CadrumoDesktopInput]::ProcessOf([IntPtr]$native) -ne $OwnerProcess) {
                $scope['diagnosticError'] = 'UIA HWND ownership changed'
                return $scope
            }
        }
        [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($OwnerProcess))
        $scope.admitted = $true
    } catch { $scope['diagnosticError'] = 'UIA identity unavailable or root ownership changed' }
    return $scope
}

function Get-RootMsaaIdentity([IntPtr]$Object, [long]$Handle, [uint32]$OwnerProcess) {
    $identity = @{ admitted = $false; requestedPidMatches = $null; objectHwndMatches = $null; objectPidKnown = $null; objectPidMatches = $null }
    try {
        [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($OwnerProcess))
        $identity.requestedPidMatches = $true
        $objectHwnd = [CadrumoDesktopInput]::MsaaWindow($Object)
        $identity.objectHwndMatches = $objectHwnd -eq [IntPtr]$Handle
        if (-not $identity.objectHwndMatches) { throw 'identity mismatch' }
        $objectPid = [CadrumoDesktopInput]::ProcessOf($objectHwnd)
        $identity.objectPidKnown = $objectPid -gt 0
        $identity.objectPidMatches = $objectPid -eq $OwnerProcess
        if (-not $identity.objectPidKnown -or -not $identity.objectPidMatches) { throw 'ownership mismatch' }
        [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($OwnerProcess))
        $identity.admitted = $true
    } catch { $identity['diagnosticError'] = 'MSAA root identity unavailable or outside requested HWND ownership' }
    return $identity
}

function Get-RootMsaa([long]$Handle, [uint32[]]$Scope, $ExpectedTitle) {
    $result = @{ complete = $false; requestedInScope = $null; expectedTitleAvailable = $null -ne $ExpectedTitle; released = $null }
    $accessible = [IntPtr]::Zero
    try {
        if ($null -ne $ExpectedTitle -and ($ExpectedTitle -isnot [string] -or $ExpectedTitle.Length -gt 1024)) { throw 'invalid expected title' }
        $owned = [CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, $Scope)
        $result.requestedInScope = $true
        $ownerProcess = [uint32]$owned['pid']
        $accessible = [CadrumoDesktopInput]::MsaaRoot([IntPtr]$Handle)
        if ($accessible -eq [IntPtr]::Zero) { throw 'root unavailable' }
        function Confirm-RootMsaaIdentity {
            $identity = Get-RootMsaaIdentity $accessible $Handle $ownerProcess
            $result['scope'] = $identity
            if (-not $identity.admitted) { throw 'root identity refused' }
        }
        Confirm-RootMsaaIdentity
        $role = [CadrumoDesktopInput]::MsaaRole($accessible)
        Confirm-RootMsaaIdentity
        if ($role -isnot [int] -or $role -lt 1 -or $role -gt 64) { throw 'unsupported numeric role' }
        $result['roleId'] = $role
        if ($role -eq [CadrumoDesktopInput]::MsaaToolTipRole -and $null -ne $ExpectedTitle) {
            Confirm-RootMsaaIdentity
            $matches = [CadrumoDesktopInput]::MsaaNameMatches($accessible, $ExpectedTitle)
            Confirm-RootMsaaIdentity
            $result['nameMatchesExpectedTitle'] = $matches
        }
        $result.complete = $true
        $result['completionReason'] = 'exact HWND root role read'
    } catch { $result['diagnosticError'] = 'MSAA root evidence unavailable, unsupported or ownership changed' }
    finally {
        if ($accessible -ne [IntPtr]::Zero) {
            try { [CadrumoDesktopInput]::ReleaseMsaaRoot($accessible); $result.released = $true }
            catch { $result.released = $false; $result.complete = $false; $result['diagnosticError'] = 'MSAA root release unavailable' }
        }
    }
    return $result
}

function Get-MsaaTree([long]$Handle, [uint32[]]$Scope, $ExpectedTitle) {
    $settlement = @{ acquired = 0; released = 0; errors = 0; complete = $false; enumerationCleanupKnown = $true }
    $result = @{ complete = $false; maxCandidates = 16; maxDepth = 3; candidateCount = 0; candidateCountIncludesReserved = $true; nodes = @(); releaseSettlement = $settlement; expectedTitleAvailable = $null -ne $ExpectedTitle }
    $ownedReferences = New-Object 'System.Collections.Generic.List[System.IntPtr]'
    try {
        if ($null -ne $ExpectedTitle -and ($ExpectedTitle -isnot [string] -or $ExpectedTitle.Length -gt 1024)) { throw 'invalid title' }
        $owned = [CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, $Scope)
        $ownerProcess = [uint32]$owned['pid']
        $root = [CadrumoDesktopInput]::MsaaRoot([IntPtr]$Handle)
        if ($root -eq [IntPtr]::Zero) { throw 'root unavailable' }
        $ownedReferences.Add($root)
        $settlement.acquired++
        function Confirm-MsaaTreeIdentity([IntPtr]$Reference) {
            $identity = Get-RootMsaaIdentity $Reference $Handle $ownerProcess
            if (-not $identity.admitted) { $result['scopeRejection'] = $identity; throw 'MSAA tree scope refused' }
            return $identity
        }
        $pending = New-Object System.Collections.Queue
        $pending.Enqueue(@{ reference = $root; childId = 0; simple = $false; depth = 0; parentIndex = $null })
        $result.candidateCount = 1
        while ($pending.Count -gt 0) {
            $item = $pending.Dequeue()
            $identity = Confirm-MsaaTreeIdentity $item.reference
            $role = [CadrumoDesktopInput]::MsaaTreeRole($item.reference, $item.childId)
            [void](Confirm-MsaaTreeIdentity $item.reference)
            if ($role -isnot [int] -or $role -lt 1 -or $role -gt 64) { throw 'unsupported numeric role' }
            $index = $result.nodes.Count
            $node = @{ index = $index; parentIndex = $item.parentIndex; depth = $item.depth; simpleChild = $item.simple; roleId = $role; scope = $identity }
            if ($role -eq [CadrumoDesktopInput]::MsaaToolTipRole -and $null -ne $ExpectedTitle) {
                [void](Confirm-MsaaTreeIdentity $item.reference)
                $matches = [CadrumoDesktopInput]::MsaaTreeNameMatches($item.reference, $item.childId, $ExpectedTitle)
                [void](Confirm-MsaaTreeIdentity $item.reference)
                $node['nameMatchesExpectedTitle'] = $matches
            }
            $result.nodes += $node
            if ($item.simple) { continue }
            [void](Confirm-MsaaTreeIdentity $item.reference)
            $count = [CadrumoDesktopInput]::MsaaChildCount($item.reference)
            [void](Confirm-MsaaTreeIdentity $item.reference)
            if ($count -isnot [int] -or $count -lt 0) { throw 'unsupported child count' }
            $node['childCount'] = $count
            if ($count -eq 0) { continue }
            if ($item.depth -ge 3) { $result['limit'] = 'depth'; throw 'depth cap' }
            if ($count -gt (16 - $result.candidateCount)) { $result['limit'] = 'candidates'; throw 'candidate cap' }
            # Reserve every requested slot before crossing the enumeration boundary.
            $result.candidateCount += $count
            [void](Confirm-MsaaTreeIdentity $item.reference)
            $settlement.enumerationCleanupKnown = $null
            $children = @([CadrumoDesktopInput]::MsaaChildren($item.reference, $count))
            $settlement.enumerationCleanupKnown = $true
            foreach ($child in $children) {
                if ($child.Accessible -ne [IntPtr]::Zero) { $ownedReferences.Add($child.Accessible); $settlement.acquired++ }
            }
            [void](Confirm-MsaaTreeIdentity $item.reference)
            $afterCount = [CadrumoDesktopInput]::MsaaChildCount($item.reference)
            [void](Confirm-MsaaTreeIdentity $item.reference)
            if ($children.Count -ne $count -or $afterCount -ne $count) { throw 'child enumeration changed' }
            foreach ($child in $children) {
                if ($child.ChildId -gt 0 -and $child.Accessible -eq [IntPtr]::Zero) {
                    $pending.Enqueue(@{ reference = $item.reference; childId = $child.ChildId; simple = $true; depth = $item.depth + 1; parentIndex = $index })
                } elseif ($child.ChildId -eq 0 -and $child.Accessible -ne [IntPtr]::Zero) {
                    $pending.Enqueue(@{ reference = $child.Accessible; childId = 0; simple = $false; depth = $item.depth + 1; parentIndex = $index })
                } else { throw 'unsupported child representation' }
            }
        }
        $result.complete = $true
        $result['completionReason'] = 'bounded same HWND MSAA tree exhausted'
    } catch { $result['diagnosticError'] = 'MSAA tree incomplete, unsupported, changed or outside requested HWND ownership' }
    finally {
        for ($i = $ownedReferences.Count - 1; $i -ge 0; $i--) {
            try { [CadrumoDesktopInput]::ReleaseMsaaRoot($ownedReferences[$i]); $settlement.released++ }
            catch { $settlement.errors++; $result.complete = $false; $result['diagnosticError'] = 'MSAA tree reference release unavailable' }
        }
        $settlement.complete = $settlement.errors -eq 0 -and $settlement.released -eq $settlement.acquired -and $settlement.enumerationCleanupKnown -eq $true
    }
    return $result
}

function Get-WindowRoles([long]$Handle, [uint32[]]$Scope, $ExpectedTitle) {
    $result = @{ hwnd = $Handle; nodes = @(); complete = $false; maxNodes = 16; maxDepth = 3; candidateCount = 0; expectedTitleAvailable = $null -ne $ExpectedTitle }
    $result['rootMsaa'] = Get-RootMsaa $Handle $Scope $ExpectedTitle
    $result['msaaTree'] = Get-MsaaTree $Handle $Scope $ExpectedTitle
    try {
        # Validate the current Win32 ownership before loading or querying UIA.
        $owned = [CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, $Scope)
        $ownerProcess = [uint32]$owned['pid']
        Add-Type -AssemblyName UIAutomationClient
        Add-Type -AssemblyName UIAutomationTypes
        [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($ownerProcess))
        $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$Handle)
        if ($null -eq $root) { throw 'unavailable' }
        $walker = [System.Windows.Automation.TreeWalker]::RawViewWalker
        $pending = New-Object System.Collections.Queue
        $pending.Enqueue(@{ element = $root; depth = 0; ancestorAdmitted = $false })
        $result['candidateCount'] = 1
        $visited = 0
        while ($pending.Count -gt 0 -and $visited -lt 16) {
            $item = $pending.Dequeue()
            [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($ownerProcess))
            $visited++
            $identity = Get-RoleNodeScope $item.element $Handle $ownerProcess $item.depth $item.ancestorAdmitted
            if (-not $identity.admitted) {
                $result['scopeRejection'] = $identity
                $result['diagnosticError'] = $identity.diagnosticError
                return $result
            }
            $current = $item.element.Current
            $controlType = $current.ControlType
            $framework = [string]$current.FrameworkId
            $node = @{
                depth = $item.depth
                scope = $identity
                controlTypeId = $controlType.Id
                controlType = $controlType.ProgrammaticName
                frameworkId = $framework.Substring(0, [Math]::Min(128, $framework.Length))
                offscreen = $current.IsOffscreen
                hasKeyboardFocus = $current.HasKeyboardFocus
            }
            if ($controlType -eq [System.Windows.Automation.ControlType]::ToolTip -and $null -ne $ExpectedTitle) {
                [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($ownerProcess))
                $identity = Get-RoleNodeScope $item.element $Handle $ownerProcess $item.depth $item.ancestorAdmitted
                if (-not $identity.admitted) {
                    $result['scopeRejection'] = $identity
                    $result['diagnosticError'] = $identity.diagnosticError
                    return $result
                }
                $node['nameMatchesExpectedTitle'] = [string]::Equals($item.element.Current.Name, $ExpectedTitle, [StringComparison]::Ordinal)
            }
            $result['nodes'] += $node
            if ($controlType -eq [System.Windows.Automation.ControlType]::ToolTip -or
                $controlType -eq [System.Windows.Automation.ControlType]::Menu -or
                $controlType -eq [System.Windows.Automation.ControlType]::MenuItem) {
                $result['complete'] = -not $result.ContainsKey('diagnosticError')
                $result['completionReason'] = 'role found'
                return $result
            }
            if ($item.depth -ge 3) {
                $result['diagnosticError'] = 'UIA depth limit reached'
                continue
            }
            if (($visited + $pending.Count) -ge 16) {
                $result['diagnosticError'] = 'UIA node limit reached'
                continue
            }
            [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($ownerProcess))
            $child = $walker.GetFirstChild($item.element)
            while ($null -ne $child -and ($visited + $pending.Count) -lt 16) {
                $pending.Enqueue(@{ element = $child; depth = $item.depth + 1; ancestorAdmitted = $true })
                $result['candidateCount'] = $visited + $pending.Count
                if (($visited + $pending.Count) -ge 16) {
                    $result['diagnosticError'] = 'UIA node limit reached'
                    break
                }
                [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($ownerProcess))
                $identity = Get-RoleNodeScope $child $Handle $ownerProcess ($item.depth + 1) $true
                if (-not $identity.admitted) {
                    $result['scopeRejection'] = $identity
                    $result['diagnosticError'] = $identity.diagnosticError
                    return $result
                }
                [void][CadrumoDesktopInput]::WindowMetadata([IntPtr]$Handle, @($ownerProcess))
                $child = $walker.GetNextSibling($child)
            }
            if ($null -ne $child) { $result['diagnosticError'] = 'UIA node limit reached' }
        }
        if (-not $result.ContainsKey('diagnosticError') -and $pending.Count -eq 0) {
            $result['complete'] = $true
            $result['completionReason'] = 'subtree exhausted'
        }
    } catch { $result['diagnosticError'] = 'UIA role query unavailable or ownership changed' }
    return $result
}

function Invoke-Request($request) {
    switch ($request.op) {
        'clipboard-write' {
            try {
                if ($request.text -isnot [string]) { throw 'invalid text' }
                Add-Type -AssemblyName System.Windows.Forms
                if ($request.text.Length -eq 0) {
                    [System.Windows.Forms.Clipboard]::Clear()
                } else {
                    [System.Windows.Forms.Clipboard]::SetText($request.text, [System.Windows.Forms.TextDataFormat]::UnicodeText)
                }
                $actual = [System.Windows.Forms.Clipboard]::GetText([System.Windows.Forms.TextDataFormat]::UnicodeText)
                return @{ matches = [string]::Equals($actual, $request.text, [StringComparison]::Ordinal) }
            } catch {
                throw 'Clipboard text write failed'
            }
        }
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
        'window-metadata' {
            $scope = [uint32[]]@($request.pids)
            if ($scope.Count -gt 256 -or @($request.hwnds).Count -gt 256) { throw 'window metadata scope exceeds 256 entries' }
            return ,@($request.hwnds | ForEach-Object {
                $handle = [long]$_
                try {
                    $metadata = [CadrumoDesktopInput]::WindowMetadata([IntPtr]$handle, $scope)
                    try {
                        $process = [Diagnostics.Process]::GetProcessById([int]$metadata['pid'])
                        try { $metadata['executableName'] = $process.ProcessName } finally { $process.Dispose() }
                    } catch { $metadata['processIdentityError'] = 'process name unavailable' }
                    $metadata
                } catch { @{ hwnd = $handle; diagnosticError = $_.Exception.Message } }
            })
        }
        'window-roles' {
            try {
                $scope = [uint32[]]@($request.pids)
                $handles = @($request.hwnds)
                if ($scope.Count -eq 0 -or $scope.Count -gt 256 -or $scope -contains 0 -or
                    $handles.Count -gt 16 -or
                    ($null -ne $request.expectedTitle -and
                        ($request.expectedTitle -isnot [string] -or $request.expectedTitle.Length -gt 1024))) {
                    throw 'invalid scope'
                }
                return ,@($handles | ForEach-Object { Get-WindowRoles ([long]$_) $scope $request.expectedTitle })
            } catch { throw 'Window role request failed' }
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
        'accessible' {
            Add-Type -AssemblyName UIAutomationClient
            Add-Type -AssemblyName UIAutomationTypes
            $element = [System.Windows.Automation.AutomationElement]::FromHandle((Get-Window $request.pid))
            $elements = $element.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
            return ,@($elements | Select-Object -First 1024 | ForEach-Object {
                @{ name = $_.Current.Name; role = $_.Current.ControlType.ProgrammaticName }
            })
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

[Console]::InputEncoding = New-Object Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object Text.UTF8Encoding($false)
while ($true) {
    $line = [Console]::In.ReadLine()
    if ($null -eq $line) { break }
    if (-not $line.Trim()) { continue }
    $requestId = $null
    $requestOperation = $null
    try {
        $request = $line | ConvertFrom-Json
        $requestId = $request.id
        $requestOperation = $request.op
        $reply = @{ id = $request.id; ok = $true; result = (Invoke-Request $request) }
    } catch {
        $message = if ($requestOperation -eq 'clipboard-write') { 'Clipboard text write failed' } elseif ($requestOperation -eq 'window-roles') { 'Window role request failed' } else { $_.Exception.Message }
        $reply = @{ id = $requestId; ok = $false; error = $message }
    }
    [Console]::Out.WriteLine(($reply | ConvertTo-Json -Compress -Depth 6))
    [Console]::Out.Flush()
}
