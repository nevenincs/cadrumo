"""Seal a validated import command behind the TUI's safe display identities.

The path validation lives in the application layer, which is where filesystem
access belongs; this module only wraps the result. That split is not
bookkeeping: the Ledger TUI's boundary gate refuses I/O imports outright, and
it caught an earlier draft of the validation sitting here.

The path never escapes the sealed object. `LedgerPreparedImportV1` keeps the
command in a weak-keyed vault with no attribute, repr or serialization surface,
so a path the operator typed cannot reach a rendered frame, a log line or a
crash report through the value the screen holds.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from ....application.ledger.import_preparation import (
    LedgerImportPathRefusedError,
    prepare_ledger_import_command,
)
from .models import LedgerPreparedImportV1

if TYPE_CHECKING:
    from ....core.period import Period

_PROVIDER_LABEL_KEY: Final = "tui.ledger.import.provider.bank"
_SOURCE_LABEL_KEY: Final = "tui.ledger.import.source.prepared"


def prepare_ledger_import(
    raw_path: str,
    *,
    bucket_id: str,
    choice_id: str,
    period: Period | None = None,
) -> LedgerPreparedImportV1:
    """Seal one operator-entered path into a prepared import, or refuse it.

    Raises:
        LedgerImportPathRefusedError: Raised by the application validator when
            the entry is blank, absent, not a file, or unreadable. Propagated
            unchanged so the screen renders one authored sentence rather than
            re-deriving the reason.
    """
    command = prepare_ledger_import_command(raw_path, bucket_id=bucket_id, period=period)
    return LedgerPreparedImportV1(
        choice_id=choice_id,
        provider_label_key=_PROVIDER_LABEL_KEY,
        source_label_key=_SOURCE_LABEL_KEY,
        command=command,
    )


__all__ = ["LedgerImportPathRefusedError", "prepare_ledger_import"]
