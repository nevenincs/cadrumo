"""Plain wording for the refusals of a file that only a model can read."""

from __future__ import annotations

from ..core.i18n.render import tr

__all__ = ["column_reader_refusal_reason", "statement_reader_refusal_reason"]


def column_reader_refusal_reason(*, locale: str | None = None) -> str:
    """Word why a file whose column names only a model reads was not read.

    Every import lane that needs the column-naming model gives this one reason,
    so the person reads the same sentence whichever lane refused.
    """
    return tr("application.reader.refusal.column_names_unavailable", locale=locale)


def statement_reader_refusal_reason(*, locale: str | None = None) -> str:
    """Word why a PDF statement that only a model reads was not read.

    One reason whether the text or the scanned-page reader could not be asked,
    because the person meets one statement, not two readers.
    """
    return tr("application.reader.refusal.statement_unavailable", locale=locale)
