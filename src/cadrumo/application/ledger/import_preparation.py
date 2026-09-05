"""Validate an operator-entered import path and build its canonical command.

The filesystem check lives HERE, not in the TUI. A presentation package that
opens files is doing adapter work, and the Ledger TUI's own boundary gate
refuses exactly that -- it caught an earlier draft of this function sitting in
`entrypoints/tui/ledger`, which is what moved it.

The refusal is raised BEFORE provider resolution, mirroring
`import_ledger_source`'s own guard: with `--provider auto` a missing path would
otherwise be opened through every candidate provider in turn, and the operator
would read a parse traceback instead of one plain sentence.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from .models import LedgerSourceImportCommand

if TYPE_CHECKING:
    from ...core.period import Period

_AUTO_PROVIDER: Final = "auto"


class LedgerImportPathRefusedError(ValueError):
    """The entered path cannot be prepared into an import command."""


def prepare_ledger_import_command(
    raw_path: str,
    *,
    bucket_id: str,
    period: Period | None = None,
) -> LedgerSourceImportCommand:
    """Resolve one entered path into a canonical import command, or refuse it.

    The refusal names WHICH condition failed -- blank, absent, not a file,
    unreadable -- and never the path itself. A caller renders it verbatim, and
    a path echoed into a status line would undo the sealing that keeps it out
    of frames and logs, at exactly the moment an operator is most likely to be
    sharing their screen.

    Raises:
        LedgerImportPathRefusedError: The entry names nothing usable.
    """
    entered = raw_path.strip()
    if not entered:
        raise LedgerImportPathRefusedError("no source path was entered")

    candidate = Path(entered).expanduser()
    if not candidate.exists():
        raise LedgerImportPathRefusedError("the entered source does not exist")
    if not candidate.is_file():
        raise LedgerImportPathRefusedError("the entered source is not a file")
    try:
        with candidate.open("rb") as handle:
            handle.read(1)
    except OSError as error:
        raise LedgerImportPathRefusedError("the entered source cannot be read") from error

    return LedgerSourceImportCommand(
        bucket_id=bucket_id,
        path=candidate,
        provider=_AUTO_PROVIDER,
        period=period,
    )


__all__ = ["LedgerImportPathRefusedError", "prepare_ledger_import_command"]
