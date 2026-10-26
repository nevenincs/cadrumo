"""The one process spawn behind every authority publication.

A publication compiles its candidate in a fresh interpreter running a fixed
module, so the compile never depends on what the launching tool had already
loaded. The spawn is kept in this module
alone so that it is the only place a subprocess starts on the publication path.

The child is bound to the parent's lifetime through its standard input: the
parent opens a pipe it never writes to and closes it only after the child has
finished. If the parent dies first, the operating system closes the pipe, the
child sees it broken, and the child exits instead of compiling for nobody.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.storage_environment import prepare_temporary_directory

__all__ = [
    "CANDIDATE_COMPILER_MODULE",
    "PARENT_EXITED_EXIT_CODE",
    "CandidateCompileResult",
    "exit_when_parent_exits",
    "run_candidate_compiler",
]

CANDIDATE_COMPILER_MODULE: Final = "dev.registry.pipeline.compile_authority_candidate"
PARENT_EXITED_EXIT_CODE: Final = 86
"""Exit status of a candidate compiler whose parent went away before it finished."""

_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[3]
_LIFETIME_POLL_SECONDS: Final = 0.5


@dataclass(frozen=True, slots=True)
class CandidateCompileResult:
    """How the candidate compiler process ended and what it reported on stderr."""

    returncode: int
    diagnostics: str

    @property
    def succeeded(self) -> bool:
        """Whether the child staged a candidate."""
        return self.returncode == 0


def run_candidate_compiler(
    *,
    registry_root: Path,
    source_root: Path,
    profile_schema_path: Path,
    output: Path,
    eager_baseline_path: Path | None = None,
) -> CandidateCompileResult:
    """Run the candidate compiler module in a fresh interpreter over this checkout's sources.

    The argv is ``sys.executable``, the literal compiler module name and the
    caller's resolved paths. The lifetime pipe on stdin is closed only after
    the child has exited.
    """
    command = [
        sys.executable,
        "-s",
        "-m",
        CANDIDATE_COMPILER_MODULE,
        "--registry-root",
        str(registry_root),
        "--source-root",
        str(source_root),
        "--profile-schema",
        str(profile_schema_path),
        "--output",
        str(output),
    ]
    if eager_baseline_path is not None:
        command.extend(("--eager-baseline", str(eager_baseline_path)))
    with tempfile.TemporaryFile(dir=prepare_temporary_directory()) as diagnostics:
        with subprocess.Popen(
            command,
            cwd=_REPOSITORY_ROOT,
            env=_compiler_environment(),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=diagnostics,
        ) as process:
            # Popen's context exit closes the lifetime pipe only after the
            # child has been waited for, so a live parent never signals its
            # own death. communicate() would close it at once.
            returncode = process.wait()
        diagnostics.seek(0)
        text = diagnostics.read().decode("utf-8", errors="replace").strip()
    return CandidateCompileResult(returncode=returncode, diagnostics=text)


def exit_when_parent_exits() -> None:
    """End this process once the parent's lifetime pipe on stdin closes."""
    stdin = sys.stdin
    if stdin is None:
        return
    if sys.platform == "win32":
        _watch_windows_lifetime_pipe(stdin.fileno())
        return

    def watch() -> None:
        stdin.buffer.read()
        os._exit(PARENT_EXITED_EXIT_CODE)

    threading.Thread(target=watch, name="parent-lifetime", daemon=True).start()


def _watch_windows_lifetime_pipe(fd: int) -> None:
    """Poll the lifetime pipe instead of blocking a read on it.

    Windows serialises synchronous I/O on one file object, so a read left pending
    on stdin stalls anything else that touches that handle. The C runtime does
    exactly that when a DLL initialises it under the loader lock -- importing
    numpy through openpyxl's record-design reader deadlocked the compiler. A
    non-blocking peek never leaves an operation pending, and it fails once the
    parent's end of the pipe is closed. A stdin that is not a pipe carries no
    lifetime contract and is left unwatched.
    """
    if sys.platform != "win32":
        raise RuntimeError("Windows lifetime pipes require Windows")

    import _winapi
    import msvcrt

    handle = msvcrt.get_osfhandle(fd)
    if _winapi.GetFileType(handle) != _winapi.FILE_TYPE_PIPE:
        return

    def watch() -> None:
        try:
            while True:
                _winapi.PeekNamedPipe(handle, 0)
                time.sleep(_LIFETIME_POLL_SECONDS)
        except OSError:
            os._exit(PARENT_EXITED_EXIT_CODE)

    threading.Thread(target=watch, name="parent-lifetime", daemon=True).start()


def _compiler_environment() -> dict[str, str]:
    """Return the launcher's environment with only this checkout's sources on the import path.

    Interpreter configuration the launcher inherited -- an import path, a
    startup file, a home -- is dropped, so the child imports the compiler from
    the same checkout whichever tool started it.
    """
    environment = {name: value for name, value in os.environ.items() if not name.upper().startswith("PYTHON")}
    environment["PYTHONPATH"] = os.pathsep.join((str(_REPOSITORY_ROOT), str(_REPOSITORY_ROOT / "src")))
    return environment
