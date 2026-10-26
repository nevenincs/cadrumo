"""Resolve and run isolated LibreOffice workbook operations."""

from __future__ import annotations

import shutil
import subprocess
import sys
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.external_constants import XLSX_EXTENSION as _XLSX_EXTENSION
from cadrumo.core.storage_environment import prepare_temporary_directory
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.ids import (
    WorkbookOutputId,
)
from dev.packaging.command_execution import CommandResult, run_command

from .workbook_parity_models import (
    WorkbookCellRef,
)
from .workbook_parity_output_ids import _workbook_output_id_set
from .workbook_parity_runner_resolution import _resolve_libreoffice_runner
from .workbook_parity_values import _coerce_excel_result, _excel_value

if TYPE_CHECKING:
    # Annotation-only: ``from __future__ import annotations`` above makes every
    # annotation a string, so these need not exist at runtime. openpyxl is one of
    # the heaviest third-party imports in the tree and this module is imported
    # eagerly by the registry facade, so the symbols that ARE needed at runtime
    # (``load_workbook``, ``Tokenizer``, and the ``TokenizerError`` /
    # ``InvalidFileException`` handler types) are imported inside the functions
    # that use them -- a taxpayer calculation must not load a spreadsheet engine.
    pass


# Every LibreOffice call starts from a fresh, private user installation, so its
# first-run registration of the bundled extensions into that profile dominates
# the call: a single conversion was measured at 10-63 s and six concurrent ones
# at about 135 s each on a loaded 24-thread Windows host. The budget covers that
# initialisation under load; it is a hang guard, not a performance expectation.
_LIBREOFFICE_TIMEOUT_SECONDS = 300.0


# On Windows LibreOffice abandons that first-run registration part-way once the
# user-installation root is too deep -- and still exits 0 without writing any
# output. Measured against LibreOffice 26.8 with long paths enabled in the OS: a
# 147-character root converted, a 149-character root did not. The limit keeps a
# margin below that, and the conversion refuses up front instead of running a
# process that would report success and produce nothing.
_LIBREOFFICE_PROFILE_ROOT_MAX_CHARS: int | None = 140 if sys.platform == "win32" else None


LIBREOFFICE_FAILURE_CONTEXT_KEY = "libreoffice_failure"
"""Error ``context`` key carrying the :class:`LibreOfficeFailureCause` of a refusal."""


class LibreOfficeFailureCause(StrEnum):
    """Why a LibreOffice headless conversion yielded no workbook."""

    PROFILE_PATH_TOO_LONG = "profile_path_too_long"
    TIMED_OUT = "timed_out"
    EXITED_NONZERO = "exited_nonzero"
    NO_OUTPUT = "no_output"


class _LibreOfficeConversionError(RuntimeError):
    """Failure raised once a resolved LibreOffice runner is asked to convert a workbook."""

    def __init__(self, cause: LibreOfficeFailureCause, message: str) -> None:
        super().__init__(message)
        self.cause = cause

    def as_registry_error(self) -> RegistryValidationError:
        return RegistryValidationError(str(self), context={LIBREOFFICE_FAILURE_CONTEXT_KEY: self.cause.value})


@dataclass(frozen=True)
class _LibreOfficeWorkspace:
    """Private scratch tree for one LibreOffice call, with every name kept short."""

    root: Path
    profile: Path
    output: Path


def _run_libreoffice(command: Sequence[str], *, timeout_seconds: float) -> CommandResult:
    """Run a resolved LibreOffice command and expose subprocess-like failures."""
    completed = run_command(command, cwd=Path.cwd(), timeout_seconds=timeout_seconds)
    if completed.returncode != 0:
        raise subprocess.CalledProcessError(
            completed.returncode,
            list(command),
            output=completed.stdout,
            stderr=completed.stderr,
        )
    return completed


def _subprocess_failure_detail(completed: subprocess.CalledProcessError | CommandResult) -> str:
    """Summarize a failed LibreOffice invocation from fields this project owns.

    ``completed.stdout``/``completed.stderr`` are text the external LibreOffice
    process chose to emit -- arbitrary, locale-dependent, and able to echo
    workbook content this project has no license to interpolate wholesale into
    a raised message (confirmed empirically: a crafted subprocess exit wrote
    an unrelated local path and an unrelated secret-shaped string to
    stdout/stderr, and the previous newline-joined composition rendered both
    verbatim). The exit code and captured byte lengths are this project's
    own observation of the failure and are safe to show; the raw text is
    discarded rather than rendered.
    """
    stdout_len = len(completed.stdout) if completed.stdout else 0
    stderr_len = len(completed.stderr) if completed.stderr else 0
    return f"exit code {completed.returncode} ({stdout_len} stdout chars, {stderr_len} stderr chars captured)"


def run_workbook_with_libreoffice(
    workbook_path: Path,
    *,
    inputs: Mapping[WorkbookCellRef, Decimal | int | str | bool],
    outputs: Mapping[WorkbookOutputId, WorkbookCellRef],
    executable: str | None = None,
) -> Mapping[WorkbookOutputId, Decimal | int | str | bool | None]:
    """Run a local XLSX workbook with LibreOffice headless and return outputs."""
    from openpyxl import load_workbook

    _workbook_output_id_set("workbook output cells", outputs)
    runner = _resolve_libreoffice_runner(executable)
    resolved = workbook_path.resolve()
    if not resolved.is_file():
        raise RegistryValidationError(f"workbook does not exist: {workbook_path}")
    if resolved.suffix.lower() != _XLSX_EXTENSION:
        raise RegistryValidationError("LibreOffice runner currently accepts only XLSX workbooks")

    with _libreoffice_workspace() as workspace:
        working_copy = workspace.root / f"in{_XLSX_EXTENSION}"
        shutil.copy2(resolved, working_copy)
        workbook = load_workbook(working_copy)
        try:
            for cell, value in inputs.items():
                workbook[cell.sheet][cell.coordinate] = _excel_value(value)
            workbook.save(working_copy)
        finally:
            workbook.close()
        try:
            recalculated_path = _convert_with_libreoffice(
                runner,
                working_copy,
                workspace=workspace,
                operation="workbook recalculation",
            )
        except _LibreOfficeConversionError as exc:
            raise exc.as_registry_error() from exc
        recalculated = load_workbook(recalculated_path, data_only=True, read_only=True)
        try:
            return {
                output_id: _coerce_excel_result(recalculated[cell.sheet][cell.coordinate].value)
                for output_id, cell in outputs.items()
            }
        finally:
            recalculated.close()


@contextmanager
def _libreoffice_workspace() -> Generator[_LibreOfficeWorkspace]:
    """Yield a private scratch tree holding the input copy, profile and output of one call.

    The tree uses the controlled temporary root with one-letter member names
    because LibreOffice's user installation beneath it is path-length sensitive
    (see ``_LIBREOFFICE_PROFILE_ROOT_MAX_CHARS``). Operators with a long checkout
    path can point ``CADRUMO_TEMP_DIR`` at a shorter controlled location.
    """
    with TemporaryDirectory(prefix="lo-", dir=prepare_temporary_directory()) as tmp:
        root = Path(tmp).resolve()
        output = root / "o"
        output.mkdir()
        yield _LibreOfficeWorkspace(root=root, profile=root / "p", output=output)


def _convert_with_libreoffice(
    runner: Path,
    source: Path,
    *,
    workspace: _LibreOfficeWorkspace,
    operation: str,
) -> Path:
    """Convert ``source`` to XLSX in ``workspace`` and return the one workbook LibreOffice wrote.

    The user installation is private to this call: soffice forwards a request
    to any running instance that shares its profile and then exits 0 itself,
    so a shared profile lets a concurrent call absorb this conversion.
    """
    profile_chars = len(str(workspace.profile))
    if _LIBREOFFICE_PROFILE_ROOT_MAX_CHARS is not None and profile_chars > _LIBREOFFICE_PROFILE_ROOT_MAX_CHARS:
        raise _LibreOfficeConversionError(
            LibreOfficeFailureCause.PROFILE_PATH_TOO_LONG,
            f"LibreOffice {operation} refused: its user profile root would be {profile_chars} characters "
            f"long, above the {_LIBREOFFICE_PROFILE_ROOT_MAX_CHARS} LibreOffice can initialise on this "
            "platform without silently producing no output; set CADRUMO_TEMP_DIR to a shorter directory",
        )
    try:
        completed = _run_libreoffice(
            [
                str(runner),
                "--headless",
                "--nologo",
                "--nodefault",
                "--nofirststartwizard",
                f"-env:UserInstallation={workspace.profile.as_uri()}",
                "--convert-to",
                "xlsx",
                "--outdir",
                str(workspace.output),
                str(source),
            ],
            timeout_seconds=_LIBREOFFICE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise _LibreOfficeConversionError(
            LibreOfficeFailureCause.TIMED_OUT,
            f"LibreOffice {operation} timed out after {_LIBREOFFICE_TIMEOUT_SECONDS:.0f}s",
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise _LibreOfficeConversionError(
            LibreOfficeFailureCause.EXITED_NONZERO,
            f"LibreOffice {operation} failed: {_subprocess_failure_detail(exc)}",
        ) from exc
    outputs = scan_directory(workspace.output, pattern=f"*{_XLSX_EXTENSION}")
    if len(outputs) != 1:
        raise _LibreOfficeConversionError(
            LibreOfficeFailureCause.NO_OUTPUT,
            f"LibreOffice {operation} produced {len(outputs)} XLSX workbooks instead of one "
            f"({_subprocess_failure_detail(completed)}); soffice reports success without converting "
            "when its user profile cannot be initialised or another instance took the request",
        )
    return outputs[0]
