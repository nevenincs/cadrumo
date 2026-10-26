"""Canonical shape contract for the AEAT Código Seguro de Verificación.

A CSV is the identifier AEAT prints on a justificante and accepts at its
public cotejo endpoint to re-serve that document. Its documented and observed
shape is one complete run of 8 to 32 uppercase alphanumeric characters.

The contract lives in :mod:`cadrumo.core` because every layer meets a CSV and
none of them owns it: the inbound justificante adapter lifts one out of PDF
text, the outbound sede adapters read one out of a cotejo URL, and the public
verifier round-trips one back to AEAT. A narrower local copy is not a
conservative choice -- it silently rejects identifiers AEAT really issues, and
the artefact it refuses is filing evidence.
"""

from __future__ import annotations

import re
from typing import Final

AEAT_CSV_MIN_LENGTH: Final[int] = 8
AEAT_CSV_MAX_LENGTH: Final[int] = 32

AEAT_CSV_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"[A-Z0-9]{{{AEAT_CSV_MIN_LENGTH},{AEAT_CSV_MAX_LENGTH}}}",
)
"""One complete AEAT CSV identifier: 8-32 uppercase alphanumeric characters."""


def is_aeat_csv(value: str) -> bool:
    """Return whether ``value`` is one complete AEAT CSV identifier.

    The match is anchored at both ends, so a longer run containing a
    well-shaped substring is refused rather than silently truncated.
    Callers keep their own error translation; this helper owns only the shape.
    """
    return bool(AEAT_CSV_PATTERN.fullmatch(value))


def normalise_aeat_csv(value: str) -> str:
    """Return the canonical comparison form of an AEAT CSV.

    A normal form has to satisfy the contract it normalises toward, and this
    one is uppercase alphanumeric, so the normal form is uppercase. That rules
    out :meth:`str.casefold`, which call sites in the calendar-evidence and
    cross-period clean-state surfaces reached for independently: it produces
    lowercase, which fails :data:`AEAT_CSV_PATTERN` outright, and it
    TRANSLITERATES — fatal for a value that must round-trip to AEAT's cotejo
    endpoint byte-for-byte to re-serve a document.

    This is the one comparison form. A call site that lowercases, casefolds or
    strips differently is not being lenient, it is minting a second key for one
    identifier, which is how the same receipt fails to match itself across two
    surfaces.

    Singularity is the load-bearing claim here, not the transform, so it is
    enforced rather than asserted in prose: this concept re-fragmented twice
    after being consolidated once, because a prose claim cannot notice the next
    inline copy. ``cadrumo.tests.test_aeat_csv_normalisation_singularity`` scans
    production sources for a case transform applied to a CSV-bearing expression
    and fails on any site that restates the transform instead of calling here.
    """
    return value.strip().upper()


__all__ = [
    "AEAT_CSV_MAX_LENGTH",
    "AEAT_CSV_MIN_LENGTH",
    "AEAT_CSV_PATTERN",
    "is_aeat_csv",
    "normalise_aeat_csv",
]
