"""The shape of a record-design epoch tag.

An epoch names the filing period an official AEAT record design governs. It lives
in ``core`` rather than beside either of its users because it has two: the
registry declares it on a source reference, and a Modelo 303 calculation result
stamps it into filing evidence. One shape, two boundaries, and a duplicated
pattern would let the two drift apart -- which is the exact asymmetry that made a
value acceptable to the artefact that the registry would have refused.
"""

from __future__ import annotations

import re
from typing import Final

#: An epoch is a four-digit ejercicio, optionally with a lower-case sub-year
#: label where AEAT re-laid a form out mid-ejercicio ("2024-early", "2024-late").
#:
#: DERIVED from the tags that predate any enforcement rather than chosen: every
#: one is a bare ejercicio and none carries a document-version suffix. The label
#: excludes digits precisely so a version ("2019-v18") cannot pass as one --
#: v18 is which revision of the PDF AEAT published and says nothing about which
#: filings the design governs, so two designs differing only by version are the
#: SAME epoch.
#:
#: A SHAPE, not a member list. Enumerating the ejercicios the corpus holds today
#: would refuse the next one AEAT publishes and teach the next author to extend a
#: constant.
RECORD_DESIGN_EPOCH_PATTERN: Final = r"\d{4}(?:-[a-z]+)?"
RECORD_DESIGN_EPOCH_RE: Final = re.compile(RECORD_DESIGN_EPOCH_PATTERN)


def record_design_epoch_year(epoch: str) -> int:
    """Return the ejercicio an epoch tag names.

    Returns:
        The four-digit year the epoch opens with.

    Raises:
        ValueError: when the value is not a well-formed epoch tag.
    """
    if not RECORD_DESIGN_EPOCH_RE.fullmatch(epoch):
        raise ValueError(f"not a record-design epoch: {epoch!r}")
    return int(epoch[:4])


__all__ = [
    "RECORD_DESIGN_EPOCH_PATTERN",
    "RECORD_DESIGN_EPOCH_RE",
    "record_design_epoch_year",
]
