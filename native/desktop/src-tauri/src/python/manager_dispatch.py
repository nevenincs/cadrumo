"""Request launch through the existing Explorer desktop, never through this process."""

from __future__ import annotations

import json
import sys


def dispatch(executable: str) -> None:
    """Use Explorer's desktop-view automation object, not an in-process Shell object."""
    import pythoncom
    import pywintypes
    import win32api
    import win32con
    import win32security
    from win32com.client import dynamic
    from win32com.shell import shell, shellcon

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        if (
            win32security.GetTokenInformation(token, win32security.TokenElevationType)
            == win32security.TokenElevationTypeFull
        ):
            raise PermissionError("elevated_desktop")
    finally:
        win32api.CloseHandle(token)
    windows = dynamic.Dispatch(
        pythoncom.CoCreateInstance(
            pywintypes.IID("{9BA05972-F6A8-11CF-A442-00A0C90A8F39}"),
            None,
            pythoncom.CLSCTX_LOCAL_SERVER,
            pythoncom.IID_IDispatch,
        )
    )
    desktop = windows.FindWindowSW(0, 0, shellcon.SWC_DESKTOP, 0, shellcon.SWFO_NEEDDISPATCH)
    service = desktop._oleobj_.QueryInterface(pythoncom.IID_IServiceProvider)
    browser = service.QueryService(shell.SID_STopLevelBrowser, shell.IID_IShellBrowser)
    view = browser.QueryActiveShellView()
    background = view.GetItemObject(shellcon.SVGIO_BACKGROUND, pythoncom.IID_IDispatch)
    application = dynamic.Dispatch(background).Application
    # No arguments, inherited overrides, or runtime handle cross this boundary.
    application.ShellExecute(executable, "", "", "open", 0)


def main() -> int:
    """Emit a bounded launch acknowledgement without COM exception text."""
    import pythoncom

    pythoncom.CoInitialize()
    try:
        if len(sys.argv) != 2:
            return 2
        try:
            dispatch(sys.argv[1])
        except Exception as error:
            # COM messages may contain paths; only the numeric failure escapes.
            code = getattr(error, "hresult", None) or getattr(error, "winerror", None)
            sys.stdout.write(
                json.dumps({"dispatched": False, "os_code": code if isinstance(code, int) else None}) + "\n"
            )
            return 1
        sys.stdout.write(json.dumps({"dispatched": True, "os_code": None}) + "\n")
        return 0
    finally:
        # dispatch's COM references have already left scope.
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
