"""Observe owned fixture process completion without an elapsed test cutoff."""

from pathlib import Path

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError

from ..windows_process import WindowsOwnedProcess


def wait_process(process: WindowsOwnedProcess) -> int:
    """Retain the native owner until its actual result is available."""
    while True:
        try:
            return process.wait(timeout=0.05)
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                raise


def wait_file(path: Path, process: WindowsOwnedProcess) -> None:
    """Wait for readiness, propagating an early owned-process exit."""
    while not path.exists():
        try:
            result = process.wait(timeout=0.01)
        except RuntimeRefusalError as error:
            if error.reason is not RuntimeRefusalCode.DEADLINE_EXCEEDED:
                raise
        else:
            assert path.exists(), (path.name, result)
