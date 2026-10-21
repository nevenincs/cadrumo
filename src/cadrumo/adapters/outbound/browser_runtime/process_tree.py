"""Stopping the browser installer together with every process it started.

The installer is a Node driver that forks a download child per archive, so
stopping only the driver would leave a download running. On Windows the driver
is placed in a kill-on-close Job Object right after it starts; the driver forks
its first child only after reading the browser manifest, well after that. On
other platforms the driver leads a new session, so its process group holds the
children.

The Job Object layout comes from :mod:`cadrumo.core.windows_job_object`. It
uses :mod:`ctypes.wintypes`, which raises on import outside Windows, so it is
imported behind the module-level platform block every checker this project runs
narrows on.
"""

from __future__ import annotations

import contextlib
import ctypes
import os
import signal
import subprocess
import sys
from typing import Any, cast

__all__ = ["InstallerProcessTree"]


if sys.platform == "win32":
    from ctypes import wintypes

    from ....core.windows_job_object import (
        JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
        JobObjectExtendedLimitInformation,
    )

    class InstallerProcessTree:
        """A kill-on-close Job Object holding the installer and its children."""

        def __init__(self, process: subprocess.Popen[bytes]) -> None:
            """Place ``process`` in a new job; without one, only the process itself can be stopped."""
            self._process = process
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            handle = self._kernel32.CreateJobObjectW(None, None)
            self._job = int(handle) if handle else 0
            if not self._job:
                return
            information = JobObjectExtendedLimitInformation()
            information.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            configured = self._kernel32.SetInformationJobObject(
                wintypes.HANDLE(self._job),
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(information),
                ctypes.sizeof(information),
            )
            process_handle = int(cast(Any, process)._handle)
            assigned = configured and self._kernel32.AssignProcessToJobObject(
                wintypes.HANDLE(self._job), wintypes.HANDLE(process_handle)
            )
            if not assigned:
                self._close_job()

        @property
        def contained(self) -> bool:
            """Whether the children are held by the job, so a stop reaches them too."""
            return bool(self._job)

        def stop(self) -> None:
            """Stop the installer and every process it started."""
            if self._job:
                self._kernel32.TerminateJobObject(wintypes.HANDLE(self._job), 1)
            with contextlib.suppress(OSError):
                self._process.kill()

        def close(self) -> None:
            """Release the job; any process still in it ends with it."""
            self._close_job()

        def _close_job(self) -> None:
            if self._job:
                self._kernel32.CloseHandle(wintypes.HANDLE(self._job))
                self._job = 0

else:

    class InstallerProcessTree:
        """The installer's process group, led by the installer itself."""

        def __init__(self, process: subprocess.Popen[bytes]) -> None:
            """Track ``process``, started as the leader of a new session."""
            self._process = process

        @property
        def contained(self) -> bool:
            """Whether the children are held by the group, so a stop reaches them too."""
            return True

        def stop(self) -> None:
            """Stop the installer and every process in its group."""
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self._process.pid, signal.SIGKILL)
            with contextlib.suppress(OSError):
                self._process.kill()

        def close(self) -> None:
            """Stop anything the installer left running in its group."""
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(self._process.pid, signal.SIGKILL)
