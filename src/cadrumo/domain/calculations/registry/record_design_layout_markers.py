"""Shared record-layout marker parsing for record-design extractors."""

from __future__ import annotations

import re

from .record_design_schema import RecordDesignRelativeSuffixMarker

_RECORD_TERMINATOR_PHRASE = r"fin de registro|salto de l[íi]nea|\bCRLF\b"
#: Matched on the declared MEANING rather than on width: a two-byte relative
#: suffix that is not a line terminator is part of the closing identifier and
#: must not be mistaken for one.
_RECORD_TERMINATOR = re.compile(_RECORD_TERMINATOR_PHRASE, re.IGNORECASE)


def _split_record_terminator(
    suffixes: list[RecordDesignRelativeSuffixMarker],
) -> tuple[list[RecordDesignRelativeSuffixMarker], RecordDesignRelativeSuffixMarker | None]:
    """Separate a trailing physical end-of-record row from the closing identifier.

    The closing identifies the record; the terminator ends the line. AEAT declares
    them as adjacent relative-offset rows, and the closing recogniser below reads
    only the first kind, so a design declaring both was refused outright -- thirty
    of them, across eight modelos, every one well formed.

    Split rather than skipped. The terminator is returned to the caller and stored
    on the envelope, because its two bytes are part of the record: discarding it
    would let all thirty parse while every emitted record came out two bytes short,
    which is a clean-looking wrong answer rather than a refusal.
    """
    if not suffixes:
        return suffixes, None
    last = suffixes[-1]
    if last.length == 2 and _RECORD_TERMINATOR.search(last.description):
        return suffixes[:-1], last
    return suffixes, None
