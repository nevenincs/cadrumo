"""Print-convention tripwire: an AEAT annex specimen never prints a zero amount.

An unused box on a filed AEAT form is left BLANK. The form does not print
``0,00``. That is the convention every specimen in this corpus follows, and it
is the reason a casilla the engine computes to zero can be absent from an
extraction without either side being wrong: the fichero record zero-fills a
required slot, the printed form omits it, and both are correct in their own
representation.

WHY THIS IS A GATE RATHER THAN A NOTE. The convention was established by
measurement over the specimens bundled today. A counterexample -- some future
modelo whose published form does render ``0,00`` -- would not break anything
loudly; it would quietly make the reasoning above false while every test stayed
green. Gating it converts a silent assumption into a red test naming the
document and the value.

WHAT THIS GATE DOES **NOT** CLAIM. It covers the specimens committed under
``manual_annexes/`` and nothing else. That is a FLOOR on the population, never a
census: two modelo families are represented here out of the registry's many, so
a green run means "no counterexample among the bundled forms", not "AEAT never
prints zeros". The gate grows as forms are bundled, which is why it asserts a
property per document rather than any total.

NOR IS IT A DEPENDENCY of the divergence-layer reasoning it protects. A rule
that skips a computed-zero casilla absent from an extraction is conditioned on
the COMPUTED value being zero, not on the print convention -- and where a form
did print ``0,00`` and the value were extracted, the existing tolerance branch
resolves it before such a rule is reached. So this is a tripwire on an
assumption, not a load-bearing input: if it ever reds, the finding is that the
convention has exceptions, not that some rule is broken.

Scope note inherited from the sibling provenance gate: these are AEAT's own
worked-example figures rendered by AEAT's publication toolchain. They are
authoritative for how AEAT PRINTS a completed form; they are not a sample of
taxpayer filings.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pdfplumber
import pytest

from .test_manual_annex_provenance import _annex_pdfs

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

#: A printed euro amount in the Spanish convention: thousands separated by ".",
#: two decimals after ",". Matches "0,00", "624,00" and "21.420,00"; the sign of
#: a negative amount sits outside the match and does not affect the zero test.
_MONEY = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")

_PDFS = _annex_pdfs()
_IDS = [f"{p.parent.name}-{p.stem}" for p in _PDFS]


def _printed_amounts(pdf_path: Path) -> list[str]:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join((page.extract_text() or "") for page in pdf.pages)
    return _MONEY.findall(text)


def _as_decimal(printed: str) -> Decimal:
    return Decimal(printed.replace(".", "").replace(",", "."))


@pytest.mark.parametrize("pdf_path", _PDFS, ids=_IDS)
def test_specimen_prints_no_zero_amount(pdf_path: Path) -> None:
    """No printed amount on a specimen is zero.

    Asserted on the PARSED value rather than the literal ``"0,00"`` so a
    thousands-separated zero, or any other spelling of nought, cannot slip past
    a substring match.
    """
    zeros = [printed for printed in _printed_amounts(pdf_path) if _as_decimal(printed) == 0]

    assert not zeros, (
        f"{pdf_path.relative_to(pdf_path.parents[2])} prints zero amount(s) {zeros}. "
        "The blank-not-zero convention has an exception; the divergence-layer reasoning "
        "that treats an absent extracted casilla as 'no activity' needs re-reading against "
        "this document before it is trusted for this modelo."
    )


@pytest.mark.parametrize("pdf_path", _PDFS, ids=_IDS)
def test_specimen_yields_printed_amounts_at_all(pdf_path: Path) -> None:
    """Every specimen must yield at least one amount, or the zero test is vacuous.

    Without this, a specimen whose text extraction returned nothing -- a scanned
    render, a broken bundle, a pdfplumber regression -- would satisfy the gate
    above by having no amounts to find. A gate that passes because it looked at
    an empty document is the shape this corpus's provenance gate already guards
    against with its own non-empty check; this is the per-document counterpart.
    """
    assert _printed_amounts(pdf_path), (
        f"{pdf_path.name} yielded no printed amounts, so the zero-amount gate is vacuous for it"
    )
