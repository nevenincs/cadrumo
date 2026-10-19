"""The Windows Job Object extended-limit layout, declared once.

Every process tree this product contains on Windows is held by a kill-on-close
Job Object configured through ``JOBOBJECT_EXTENDED_LIMIT_INFORMATION``. The
browser installer and the profile KDF worker both set that structure; each owner
still decides which limits it requires and how it reacts when the job cannot be
created or assigned.

The structures are laid out with :mod:`ctypes.wintypes`, which raises on import
outside Windows, so they sit behind the module-level ``sys.platform == "win32"``
block every checker this project runs narrows on. The information-class and
limit-flag numbers are plain integers and are declared on every platform.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Final

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS: Final = 9
"""``JobObjectExtendedLimitInformation`` for ``Set``/``QueryInformationJobObject``."""

JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x00002000
"""Terminate every process in the job when its last handle closes."""

if sys.platform == "win32":
    from ctypes import wintypes

    class JobObjectBasicLimitInformation(ctypes.Structure):
        """``JOBOBJECT_BASIC_LIMIT_INFORMATION``."""

        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_uint64)
            for name in (
                "ReadOperationCount",
                "WriteOperationCount",
                "OtherOperationCount",
                "ReadTransferCount",
                "WriteTransferCount",
                "OtherTransferCount",
            )
        ]

    class JobObjectExtendedLimitInformation(ctypes.Structure):
        """``JOBOBJECT_EXTENDED_LIMIT_INFORMATION``."""

        _fields_ = [
            ("BasicLimitInformation", JobObjectBasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    __all__ = [
        "JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS",
        "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE",
        "JobObjectBasicLimitInformation",
        "JobObjectExtendedLimitInformation",
    ]
else:
    __all__ = ["JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS", "JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE"]
