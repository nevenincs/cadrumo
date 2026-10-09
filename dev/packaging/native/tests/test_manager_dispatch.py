"""Exercise the adapter's CLI and Explorer call without a desktop mutation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[4] / "native/desktop/src-tauri/src/python/manager_dispatch.py"
SPEC = importlib.util.spec_from_file_location("manager_dispatch", SOURCE)
assert SPEC is not None and SPEC.loader is not None
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)
pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


class _NativeRefusalError(RuntimeError):
    winerror = 5


def native_modules(
    failure: Exception | None = None,
) -> tuple[dict[str, object], list[tuple[object, ...]]]:
    """Replace native automation only; keep the actual adapter path intact."""
    calls: list[tuple[object, ...]] = []

    def execute(*arguments: object) -> None:
        calls.append(("execute", *arguments))
        if failure is not None:
            raise failure

    background = SimpleNamespace(Application=SimpleNamespace(ShellExecute=execute))
    view = SimpleNamespace(GetItemObject=lambda *_: background)
    browser = SimpleNamespace(QueryActiveShellView=lambda: view)
    service = SimpleNamespace(QueryService=lambda *_: browser)
    desktop = SimpleNamespace(_oleobj_=SimpleNamespace(QueryInterface=lambda _: service))
    windows = SimpleNamespace(FindWindowSW=lambda *_: desktop)
    modules = {
        "pythoncom": SimpleNamespace(
            CoInitialize=lambda: calls.append(("initialize",)),
            CoUninitialize=lambda: calls.append(("uninitialize",)),
            CoCreateInstance=lambda *_: windows,
            CLSCTX_LOCAL_SERVER=4,
            IID_IDispatch="dispatch",
            IID_IServiceProvider="service",
        ),
        "pywintypes": SimpleNamespace(IID=lambda value: value),
        "win32api": SimpleNamespace(GetCurrentProcess=lambda: 1, CloseHandle=lambda _: None),
        "win32con": SimpleNamespace(TOKEN_QUERY=8),
        "win32security": SimpleNamespace(
            OpenProcessToken=lambda *_: 2,
            TokenElevationType=18,
            TokenElevationTypeFull=2,
            GetTokenInformation=lambda *_: 1,
        ),
        "win32com": SimpleNamespace(),
        "win32com.client": SimpleNamespace(dynamic=SimpleNamespace(Dispatch=lambda value: value)),
        "win32com.shell": SimpleNamespace(
            shell=SimpleNamespace(SID_STopLevelBrowser="browser", IID_IShellBrowser="shell-browser"),
            shellcon=SimpleNamespace(SWC_DESKTOP=8, SWFO_NEEDDISPATCH=1, SVGIO_BACKGROUND=0),
        ),
    }
    return modules, calls


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["manager.exe", "--sign-in"],
        ["manager.exe", "--retry --sign-in"],
        ["manager.exe", "--retry", "--retry"],
        ["manager.exe", "--retry", "foreign"],
    ],
)
def test_closed_arguments_are_rejected_before_com_initialization(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], arguments: list[str]
) -> None:
    """Invalid activation refuses before importing or initializing COM."""
    monkeypatch.setattr(sys, "argv", ["dispatch", *arguments])
    monkeypatch.setitem(sys.modules, "pythoncom", None)
    assert ADAPTER.main() == 2
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("arguments,expected", [([], ""), (["--retry"], "--retry")])
def test_real_main_sends_only_fixed_recovery_argument_to_explorer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    expected: str,
) -> None:
    """The actual CLI and dispatch preserve the executable and fixed argument."""
    executable = 'C:/package with spaces/manager "literal".exe'
    modules, calls = native_modules()
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "argv", ["dispatch", executable, *arguments])
    assert ADAPTER.main() == 0
    assert calls == [
        ("initialize",),
        ("execute", executable, expected, "", "open", 0),
        ("uninitialize",),
    ]
    assert json.loads(capsys.readouterr().out) == {"dispatched": True, "os_code": None}


def test_explorer_failure_stays_numeric_and_uninitializes_com(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Native refusal releases COM and does not disclose exception text."""
    failure = _NativeRefusalError("private path or command text")
    modules, calls = native_modules(failure)
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(sys, "argv", ["dispatch", "manager.exe", "--retry"])
    assert ADAPTER.main() == 1
    assert json.loads(capsys.readouterr().out) == {"dispatched": False, "os_code": 5}
    assert calls[-1] == ("uninitialize",)
