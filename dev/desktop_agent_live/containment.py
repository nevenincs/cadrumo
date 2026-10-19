"""Hold the lane and every process it starts in one kill-on-close Windows Job.

The Job's only handle is this process's and is not inherited, so however the
lane ends, normally, by an exception, Ctrl-C or being killed, Windows ends
every process still in the Job with it. The product starts nothing with
breakaway, and the Job allows none. Closing that handle as the process exits
would end the process itself with code 0, so the lane ends through
:meth:`LaneJob.end`, which ends the Job with the lane's own exit code.
"""

from __future__ import annotations

import os
import sys
from typing import Any, NoReturn


class LaneJob:
    """The kill-on-close Job this process and all its later descendants belong to."""

    def __init__(self) -> None:
        """Create the Job and place this process in it."""
        import win32api
        import win32job

        self._job: Any = win32job.CreateJobObject(None, "")
        information = win32job.QueryInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation)
        information["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation, information)
        actual = win32job.QueryInformationJobObject(self._job, win32job.JobObjectExtendedLimitInformation)
        if actual["BasicLimitInformation"]["LimitFlags"] != win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE:
            raise OSError("the lane Job does not kill its processes on close")
        win32job.AssignProcessToJobObject(self._job, win32api.GetCurrentProcess())

    def others(self) -> tuple[int, ...]:
        """The process ids in the Job other than this process."""
        import win32job

        members = win32job.QueryInformationJobObject(self._job, win32job.JobObjectBasicProcessIdList)
        return tuple(int(pid) for pid in members if int(pid) != os.getpid())

    def end(self, code: int) -> NoReturn:
        """End this process, and anything still in the Job, with exit ``code``."""
        import win32job

        sys.stdout.flush()
        sys.stderr.flush()
        win32job.TerminateJobObject(self._job, code)
        raise SystemExit(code)
