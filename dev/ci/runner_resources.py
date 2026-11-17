"""Print a Linux runner's memory, disk and load while a long step runs.

A hosted runner that runs out of memory or disk fails no test. The runner
itself stops, the job ends with "the runner has received a shutdown signal" or
"lost communication with the server", and nothing in the log says why. This
sampler runs beside the tests and prints one line per interval. A job log is
streamed as it is written, so the last lines before a runner stops show what
the machine had left and which processes held it.

Only numbers, process ids and process names are printed. Command lines are
never read: the log of a public run is public.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dev.paths import REPO_ROOT, UTF_8

__all__ = [
    "MemoryReading",
    "ProcessReading",
    "largest_processes",
    "main",
    "memory_reading",
    "sample_line",
]

_KIB_PER_MIB: Final = 1024
_BYTES_PER_MIB: Final = 1024 * 1024
_MEMORY_FIELDS: Final = ("MemTotal", "MemAvailable", "SwapTotal", "SwapFree")
_LARGEST_SHOWN: Final = 4
_LINUX_PROC: Final = Path("/proc")


@dataclass(frozen=True, slots=True)
class MemoryReading:
    """The machine's memory and swap, in MiB."""

    total: int
    available: int
    swap_total: int
    swap_free: int


@dataclass(frozen=True, slots=True)
class ProcessReading:
    """One process's resident memory, in MiB."""

    pid: int
    name: str
    resident: int


def _kib_fields(text: str) -> Mapping[str, int]:
    """Read the ``Name:  <n> kB`` lines of a ``/proc`` status file; other lines are left out."""
    fields: dict[str, int] = {}
    for line in text.splitlines():
        name, separator, rest = line.partition(":")
        tokens = rest.split()
        if separator and len(tokens) == 2 and tokens[1] == "kB" and tokens[0].isascii() and tokens[0].isdigit():
            fields[name] = int(tokens[0])
    return fields


def memory_reading(meminfo: str) -> MemoryReading:
    """Read total and available memory and swap from the text of ``/proc/meminfo``.

    Raises:
        ValueError: When a field is absent, so a changed layout is not read as zero.
    """
    fields = _kib_fields(meminfo)
    missing = [name for name in _MEMORY_FIELDS if name not in fields]
    if missing:
        raise ValueError(f"meminfo holds no {', '.join(missing)}")
    total, available, swap_total, swap_free = (fields[name] // _KIB_PER_MIB for name in _MEMORY_FIELDS)
    return MemoryReading(total=total, available=available, swap_total=swap_total, swap_free=swap_free)


def largest_processes(proc_root: Path, count: int = _LARGEST_SHOWN) -> tuple[ProcessReading, ...]:
    """Return the ``count`` processes holding the most resident memory, largest first.

    A process that ends between the listing and the read is left out, and so is
    one with no resident set (a kernel thread).
    """
    found: list[ProcessReading] = []
    for entry in proc_root.iterdir():
        if not (entry.name.isascii() and entry.name.isdigit()):
            continue
        try:
            status = (entry / "status").read_text(encoding=UTF_8, errors="replace")
        except OSError:
            continue
        resident = _kib_fields(status).get("VmRSS")
        if resident is None:
            continue
        name = next((line.partition(":")[2].strip() for line in status.splitlines() if line.startswith("Name:")), "?")
        found.append(ProcessReading(pid=int(entry.name), name=name, resident=resident // _KIB_PER_MIB))
    return tuple(sorted(found, key=lambda process: (-process.resident, process.pid))[:count])


def sample_line(
    *,
    clock: str,
    memory: MemoryReading,
    disk_free: int,
    load: str,
    processes: Sequence[ProcessReading],
) -> str:
    """Return one sample as the single line the job log receives."""
    used = memory.total - memory.available
    swap_used = memory.swap_total - memory.swap_free
    largest = ", ".join(f"{process.name} {process.pid} {process.resident} MiB" for process in processes) or "none read"
    return (
        f"runner resources {clock} | memory {used} of {memory.total} MiB used, {memory.available} available"
        f" | swap {swap_used} of {memory.swap_total} MiB used | disk {disk_free} MiB free | load {load}"
        f" | largest: {largest}"
    )


def _sample(proc_root: Path, disk: Path) -> str:
    load = " ".join((proc_root / "loadavg").read_text(encoding=UTF_8).split()[:3])
    return sample_line(
        clock=time.strftime("%H:%M:%SZ", time.gmtime()),
        memory=memory_reading((proc_root / "meminfo").read_text(encoding=UTF_8)),
        disk_free=shutil.disk_usage(disk).free // _BYTES_PER_MIB,
        load=load,
        processes=largest_processes(proc_root),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Print one sample now and one per interval until the process is stopped."""
    parser = argparse.ArgumentParser(prog="python -m dev.ci.runner_resources", description=__doc__)
    parser.add_argument("--every", type=int, required=True, help="seconds between samples")
    arguments = parser.parse_args(argv)
    if arguments.every < 1:
        parser.error("--every takes a positive number of seconds")
    if not (_LINUX_PROC / "meminfo").is_file():
        parser.error("this sampler reads Linux /proc, which this machine does not have")
    while True:
        try:
            line = _sample(_LINUX_PROC, REPO_ROOT)
        except (OSError, ValueError) as error:
            # A sample that cannot be read is reported and the next one still runs:
            # the sampler stops only with the step it sits beside.
            line = f"runner resources unread: {error}"
        print(line, flush=True)
        time.sleep(arguments.every)


if __name__ == "__main__":
    sys.exit(main())
