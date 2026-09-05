"""Turn an operator-entered source path into one sealed prepared import.

The import area is entered WITH a prepared command, and nothing in the TUI
produced one: `LedgerPreparedImportV1` was constructed only in tests, so the
area was permanently refused in a real session. This is the missing producer.

The path never leaves the sealed command. `LedgerPreparedImportV1` keeps it in
a weak-keyed vault with no attribute, repr or serialization surface, so a
filesystem path the operator typed cannot reach a rendered frame, a log line or
a crash report through this object -- which is why the screen holds one of
these rather than a path of its own.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

from ....application.ledger.models import LedgerSourceImportCommand
from .models import LedgerPreparedImportV1

if TYPE_CHECKING:
    from ....core.period import Period

_PROVIDER_LABEL_KEY: Final = "tui.ledger.import.provider.bank"
_SOURCE_LABEL_KEY: Final = "tui.ledger.import.source.prepared"
_AUTO_PROVIDER: Final = "auto"


class LedgerImportPathRefusedError(ValueError):
    """The entered path cannot be prepared into an import."""


def prepare_ledger_import(
    raw_path: str,
    *,
    bucket_id: str,
    choice_id: str,
    period: Period | None = None,
) -> LedgerPreparedImportV1:
    """Seal one operator-entered path into a prepared import, or refuse it.

    Refuses BEFORE any provider work, and names the condition rather than the
    path: a blank entry, something that is not a file, or a file that cannot be
    read. `import_ledger_source` would refuse an unreadable source too, but it
    does so after the operator has left this screen, so the refusal would
    surface detached from the entry that caused it.

    The provider is resolved as `auto`, which is the detection the import
    service already performs. Asking an operator to name the bank format of a
    file they just selected is asking them to do the parser's job.

    Raises:
        LedgerImportPathRefusedError: The entry is blank, absent, not a file,
            or unreadable. The message names WHICH, never the path itself.
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

    return LedgerPreparedImportV1(
        choice_id=choice_id,
        provider_label_key=_PROVIDER_LABEL_KEY,
        source_label_key=_SOURCE_LABEL_KEY,
        command=LedgerSourceImportCommand(
            bucket_id=bucket_id,
            path=candidate,
            provider=_AUTO_PROVIDER,
            period=period,
        ),
    )


__all__ = ["LedgerImportPathRefusedError", "prepare_ledger_import"]
