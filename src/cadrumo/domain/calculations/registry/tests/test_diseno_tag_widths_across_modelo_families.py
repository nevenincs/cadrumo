"""The Diseño casilla tag is not five digits wide outside Sociedades.

The full-Diseño coverage report is the only instrument that compares the
registry against the official AEAT form. Everything else -- the
calculation-completeness manifest, the export completeness gate, the closure
derivation -- measures the registry against a set derived from the registry,
so none of them can see a casilla that exists on the real modelo and was
never authored.

That instrument extracted casilla numbers with ``\\[(\\d{5})\\]``: exactly five
digits in square brackets. Modelo 200 and Modelo 220 do write their tags that
way, and they were the only two revisions ever driven through the report.
Every other modelo family brackets its box number at its natural width --
Modelo 303 writes ``[01]`` and ``[150]``, Modelo 390 ``[01]``, Modelo 036 two
and three digits.

So the pattern matched nothing on them. And a matchless sweep does not raise:
it yields an empty Diseño set, from which the report computes zero total, zero
covered and **zero gap**. Across the 38 revisions that bundle an official
record design, 36 reported no coverage gap because their form had not been
read at all -- the failure presenting as the good news.

These tests drive the real bundled AEAT sources by path. They deliberately do
NOT load the registry authority: the thing under test is whether an official
form can be read, which is upstream of anything the registry declares, and
binding this module to a whole-tree load would make it red for reasons that
have nothing to do with tag widths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from .....core.resources._boundary import bundled_path
from ..record_design_coverage import _CASILLA_TAG_RE, DisenoCoverageReport, derive_diseno_coverage_casillas

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DISENOS: Final[Path] = Path(bundled_path("corpus/aeat_official/disenos_registro"))

_M303_2025: Final[str] = "modelo_303/files/06-303-ejercicio-2025-actualizado-04-12-2025-380-kb-xlsx.xlsx"
"""A real bundled Modelo 303 Diseño, chosen because M303 is the highest-traffic
quarterly form in the tree and its tags are two and three digits wide."""

_M303_KNOWN_BOXES: Final[frozenset[str]] = frozenset({"01", "03", "59", "60", "150"})
"""Boxes the 2025 Modelo 303 record design certainly declares.

``01``/``03`` are the régimen general base and cuota, ``59`` and ``60`` the
entregas intracomunitarias and exportaciones exentas bases, and ``150`` a
transitional-rate base. Two-digit and three-digit together, so a pattern that
handled only one width still fails this.
"""


def test_the_tag_pattern_accepts_every_width_aeat_actually_uses() -> None:
    """Two, three and five digits are all real AEAT tag widths.

    Asserted on the pattern directly because this single constant is what
    silenced the instrument across 36 revisions. The upper bound is asserted
    too: an unbounded pattern would admit amounts and position offsets that
    appear bracketed in the same columns, so widening must not become
    "match any digits".
    """
    assert _CASILLA_TAG_RE.findall("Base imponible [01]") == ["01"]
    assert _CASILLA_TAG_RE.findall("Base imponible [150]") == ["150"]
    assert _CASILLA_TAG_RE.findall("Base imponible [00552]") == ["00552"]

    assert _CASILLA_TAG_RE.findall("importe [123456]") == [], "six digits is not a casilla tag"
    assert _CASILLA_TAG_RE.findall("nota (3) y [X1]") == [], "only digits inside the brackets"


def test_a_real_modelo_303_diseno_yields_its_casillas() -> None:
    """The end-to-end proof, on a real bundled AEAT form.

    The unit test above pins the pattern; this pins that the pattern reaching
    the real corpus actually produces casillas. Both are needed: a correct
    regex wired to nothing would pass the first alone, which is the shape of
    the original defect one level up.
    """
    source = _DISENOS / _M303_2025
    assert source.is_file(), "the bundled Modelo 303 Diseño this gate reads has moved"

    casillas = derive_diseno_coverage_casillas(source, multi_segment=False)

    numbers = {casilla.number for casilla in casillas}
    assert numbers >= _M303_KNOWN_BOXES, (
        "the Modelo 303 record design must yield its own box numbers; missing "
        f"{sorted(_M303_KNOWN_BOXES - numbers)}. A five-digit-only tag pattern yields none of them "
        "and the coverage report then reports a zero gap for a form it never read"
    )
    assert len(numbers) > 100, (
        f"only {len(numbers)} casillas extracted from the Modelo 303 Diseño; the form declares "
        "well over a hundred, so a number this low means extraction is partially blind again"
    )


def test_an_unread_diseno_is_reported_as_unread_not_as_full_coverage() -> None:
    """An empty gap must not be readable as coverage.

    Two states produce an identical report: a registry that covers the whole
    form, and a form that could not be read at all. Only the first is good
    news, and for 36 of 38 revisions it was the second one being reported.
    The flag is what separates them, so it is asserted in BOTH directions --
    a one-directional assertion is satisfied by a property that is always
    true.

    CORRECTION, kept here because the first version of this test asserted it:
    an empty extraction is not always a failure. The 16 revisions in that state
    are informative declarations (111, 115, 180, 184, 190, 193, 232, 347, 349,
    360, 369, 720) whose Diseño describes positional records with NAMED fields
    and no numbered boxes -- zero bracketed numbers across all 16, at any digit
    width. For them an empty casilla set is correct. The flag still earns its
    place: it marks "casilla coverage does not apply or could not be computed",
    and either way the empty gap is not evidence of coverage.
    """
    unread = DisenoCoverageReport(
        modelo_id="303",
        revision_id="2025",
        diseno_casillas=(),
        covered_casillas=(),
        coverage_gap_casillas=(),
    )
    assert unread.extraction_found_no_casillas is True
    assert not unread.coverage_gap_casillas, (
        "the point of this state is that an unread form and a covered form present the same "
        "empty gap; if the gap were non-empty here the flag would be redundant"
    )

    source = _DISENOS / _M303_2025
    read = derive_diseno_coverage_casillas(source, multi_segment=False)
    genuinely_read = DisenoCoverageReport(
        modelo_id="303",
        revision_id="2025",
        diseno_casillas=read,
        covered_casillas=(),
        coverage_gap_casillas=read,
    )
    assert genuinely_read.extraction_found_no_casillas is False
