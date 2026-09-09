"""The Dise�o casilla tag is not five digits wide outside Sociedades.

The full-Dise�o coverage report is the only instrument that compares the
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
it yields an empty Dise�o set, from which the report computes zero total, zero
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

from .....core.resources.bundled_data import bundled_path
from ._revision_span_design_support import _CASILLA_TAG_RE

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DISENOS: Final[Path] = Path(bundled_path("corpus/aeat_official/disenos_registro"))

_M303_2025: Final[str] = "modelo_303/files/06-303-ejercicio-2025-actualizado-04-12-2025-380-kb-xlsx.xlsx"
"""A real bundled Modelo 303 Dise�o, chosen because M303 is the highest-traffic
quarterly form in the tree and its tags are two and three digits wide."""

_M303_KNOWN_BOXES: Final[frozenset[str]] = frozenset({"01", "03", "59", "60", "150"})
"""Boxes the 2025 Modelo 303 record design certainly declares.

``01``/``03`` are the r�gimen general base and cuota, ``59`` and ``60`` the
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
