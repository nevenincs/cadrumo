"""Caveats the harness attaches for the reader, rather than trusting them to.

A caveat that depends on a human remembering is not a caveat. Each one here is
derived from a fact the harness can see in the key -- a document's language, the
shape of the twin link -- and is stamped onto the row automatically, so a figure
cannot be quoted stripped of the condition that makes it honest.

The optimism-bias text is held VERBATIM from the corpus's own gap register. A
paraphrase would drift from the source and, worse, would let the harness soften
the finding over time without anyone reviewing the softening; the accompanying
test reads the corpus file and asserts this string still occurs in it, so a
corpus rewording fails a gate instead of silently outdating the caveat.
"""

from __future__ import annotations

import re
from typing import Final

from ._key import TWIN_LINK_IS_PROSE, CorpusDocument

__all__ = [
    "SPANISH_OPTIMISM_BIAS_CAVEAT",
    "TWIN_LINK_IS_PROSE",
    "caveats_for_document",
    "normalise_whitespace",
]


SPANISH_OPTIMISM_BIAS_CAVEAT: Final = (
    "Spanish-language OCR performance is measured entirely on synthetic renderings. "
    "Those renderings use a real layout vocabulary (Base imponible / IVA / Retención IRPF / "
    "Total factura, Spanish decimal commas, day-first dates, checksum-valid NIF/CIF) and real "
    "degradation (skew, uneven phone lighting, blur, sensor noise, JPEG loss), but they are "
    "**cleaner and more uniform than real Spanish invoices**: one renderer, one font family, "
    "one layout grammar. A model may score better here than on genuine Spanish paper, and the "
    "gap is not quantifiable from this corpus. Do not report Spanish OCR accuracy without this "
    "caveat attached."
)
"""The corpus gap register's section 1, verbatim, whitespace-normalised.

The single most important caveat on the whole measurement: every Spanish
document a reading model must actually look at is synthetic, so every Spanish
figure is optimistically biased by an amount this corpus cannot quantify.
"""


def normalise_whitespace(text: str) -> str:
    """Collapse runs of whitespace so a hard-wrapped source can be compared.

    The gap register is hard-wrapped markdown prose, so a verbatim comparison
    has to be insensitive to where the source happens to break its lines --
    otherwise 'verbatim' would mean 'verbatim including the column width', which
    is not a property worth pinning.
    """
    return re.sub(r"\s+", " ", text).strip()


def caveats_for_document(document: CorpusDocument) -> tuple[str, ...]:
    """Return every caveat this document's own properties require.

    Derived rather than supplied. A caller cannot forget to pass one, and a
    caller cannot suppress one either: the row builder calls this, so the only
    way to emit a Spanish figure without the optimism-bias caveat is to change
    this function, which is a reviewable act rather than an omission.
    """
    caveats: list[str] = []
    if document.is_spanish:
        caveats.append(SPANISH_OPTIMISM_BIAS_CAVEAT)
    return tuple(caveats)
