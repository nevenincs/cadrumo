"""Every official box number a Modelo 390 casilla declares exists in the design.

This is the REGISTRY -> DESIGN direction of the cross-check, and only that one.

The opposite direction -- "every box in the design has a casilla" -- is
deliberately NOT built. Measured at the 2024 design: 343 of its 375 distinct box
numbers have no casilla, an 8.5 % coverage. A gate emitting 343 findings on one
modelo trains its reader to ignore it, which is worse than no gate. That
direction becomes viable only when the annual form is substantially modelled,
and it is tracked rather than half-built here.

This direction is cheap and catches the class that actually ships: a fabricated
or mistyped box number. Two real defects of exactly that shape landed and were
repaired by hand -- a rate box whose export offsets were swapped between the 2 %
and 4 % rungs, and three rate-blind casillas claiming rate-SPECIFIC box numbers
that belonged to their rate-specific siblings.

SCOPE, stated so the gate is not over-read:

* Modelo 390 only. The other bundled modelos are UNMEASURED here; nothing about
  their box vocabulary is asserted or implied.
* An earlier survey reported "15 of 23 designs yield box numbers". That figure
  was measured against the pre-source-first design reader and has NOT been
  re-derived; treat it as stale rather than as standing.
* Box numbers are compared, descriptions are not. Nine numbers in the 2024
  design repeat, and all nine name more than one concept (``[114]``-``[117]``
  are Prorratas 1 versus Prorratas 2 -- same number, different column). This
  direction only asks whether a declared number EXISTS, so a set of numbers is
  sufficient; a consumer asking what a number MEANS must carry
  ``(number, description)`` pairs and must never key a dict by number alone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ..authority import bundled_authority
from ..record_design_coverage import _CASILLA_TAG_RE
from .test_revision_span_matches_published_designs import _designs_by_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


_MODELO = "390"
_FILING_YEAR = 2024
_PERIOD = "0A"

#: A bracketed official box number as the extracted designs render it. Matching
#: the NUMBER rather than surrounding prose is deliberate: the descriptions carry
#: accents, and an accent that does not survive a round trip would yield a bare
#: zero that reads as "this box is not in the design" -- a false finding in the
#: direction that gets believed.
#: IMPORTED from the registry's canonical definition rather than re-declared. This
#: module held its own copy capped at four digits while production used five, and
#: Modelo 200 numbers its boxes with five. This gate is scoped to Modelo 390, whose
#: boxes are two and three digits, so the cap changed no verdict here -- but a third
#: definition of one concept is how the four-digit reading survived long enough to
#: read 23 of Modelo 200's 3,440 boxes elsewhere.
_BOX_MARKER = _CASILLA_TAG_RE

#: Fields that can carry an official box number today. Derived, never assumed:
#: see ``_declared_box_numbers``. Kept as its own pattern because it matches a BARE
#: registry number rather than a bracketed one in design text, so the canonical marker
#: cannot be reused directly -- and pinned to agree with it by the assertion below,
#: which is what stops the two drifting apart the way the four-digit copies did.
_BOX_SHAPED = re.compile(r"^\d{1,5}$")


def _revision() -> ModeloRevision:
    return bundled_authority().snapshot(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD).revision


def _normalise(number: str) -> str:
    """Compare ``01`` and ``1`` as the same box."""
    return number.lstrip("0") or "0"


def _declared_box_numbers(revision: ModeloRevision) -> dict[str, str]:
    """``{normalised box number: the casilla id declaring it}``.

    The carrier set is DERIVED from the casilla rather than hardcoded, because it
    is tree-dependent: a count taken against one working tree found three
    carriers where another found four, and the difference was uncommitted work.
    Both ``number`` and ``form_number`` carry boxes today and both must be read
    -- a ``number``-only sweep produces false absences, which is the direction
    that inflates a finding rather than deflating it.
    """
    declared: dict[str, str] = {}
    for casilla in revision.casillas:
        for field in ("number", "form_number", "continuidad_id"):
            value = getattr(casilla, field, None)
            if value is not None and _BOX_SHAPED.match(str(value)):
                declared.setdefault(_normalise(str(value)), casilla.id)
    return declared


def _design_for_filing_year(modelo_id: str, filing_year: int) -> Path:
    """The design bundled FOR this year, never merely a design for this modelo.

    Resolving by year rather than by modelo is what keeps this gate meaningful
    after the annual revision is split into epochs. Box identity is epoch-scoped:
    ``[700]``/``[701]`` appear only from ejercicio-2022, ``[664]`` only from
    2023, and one byte offset already carries four different boxes across the
    current span. A modelo-keyed lookup would compare against SOME design, still
    pass, and quietly stop meaning anything -- so the year resolution is asserted
    here rather than assumed.
    """
    by_year = _designs_by_year(modelo_id)
    assert by_year, f"no design was enumerated for modelo {modelo_id}; every assertion below would be vacuous"
    candidates = by_year.get(filing_year, ())
    assert candidates, (
        f"no bundled design is attributed to {modelo_id} filing year {filing_year}; "
        "this gate must resolve the design for the revision's OWN year, never pick one for the modelo"
    )
    return candidates[0]


def _design_box_numbers(path: Path) -> set[str]:
    text = path.with_suffix(path.suffix + ".extracted.md").read_text(encoding="utf-8", errors="replace")
    return {_normalise(match.group(1)) for match in _BOX_MARKER.finditer(text)}


def test_the_gate_resolves_a_design_for_the_revisions_own_year() -> None:
    """Pin the year resolution itself, so it cannot decay into a modelo lookup."""
    path = _design_for_filing_year(_MODELO, _FILING_YEAR)
    assert str(_FILING_YEAR) in path.name, (
        f"resolved {path.name} for filing year {_FILING_YEAR}; the design must be the one bundled FOR that year"
    )


def test_every_declared_box_number_exists_in_the_design() -> None:
    """A casilla must not claim an official box the AEAT design does not carry.

    Both halves are guarded against vacuity: a revision that declared no box
    numbers, or a design that parsed to none, would otherwise satisfy the
    comparison while proving nothing.
    """
    declared = _declared_box_numbers(_revision())
    assert declared, "no casilla declares an official box number; the comparison below would be vacuous"

    design = _design_box_numbers(_design_for_filing_year(_MODELO, _FILING_YEAR))
    assert design, "the bundled design parsed to no box numbers; the comparison below would be vacuous"

    invented = {number: casilla_id for number, casilla_id in declared.items() if number not in design}
    assert not invented, (
        "casillas declare official box numbers absent from the "
        f"{_FILING_YEAR} design: {sorted((number, casilla_id) for number, casilla_id in invented.items())}"
    )


def test_a_box_number_absent_from_the_design_is_detected() -> None:
    """Negative control: the comparison can fail, and does, on a fabricated box.

    Without this, a design set that silently swallowed everything -- or a
    normaliser that mapped every input onto a member -- would leave the gate
    above green for the wrong reason.
    """
    design = _design_box_numbers(_design_for_filing_year(_MODELO, _FILING_YEAR))
    assert design, "empty design set"
    for fabricated in ("9999", "8888"):
        assert _normalise(fabricated) not in design, f"[{fabricated}] should not be a real 2024 Modelo 390 box"
    assert _normalise("670") in design, "[670] is a real 2024 box; a control that cannot find it proves nothing"


def test_both_box_number_carriers_are_read() -> None:
    """``form_number`` carries boxes no ``number`` does, and must not be dropped.

    Reading ``number`` alone would silently under-report the declared set, and an
    under-reported set makes the gate above pass more easily -- the failure
    direction that looks like success.
    """
    revision = _revision()
    numbers = {_normalise(str(c.number)) for c in revision.casillas if c.number and _BOX_SHAPED.match(str(c.number))}
    form_numbers = {
        _normalise(str(c.form_number))
        for c in revision.casillas
        if c.form_number and _BOX_SHAPED.match(str(c.form_number))
    }
    assert numbers and form_numbers, "both carriers must be populated for this assertion to mean anything"
    assert form_numbers - numbers, (
        "form_number currently carries at least one box that number does not; "
        "if that stops being true the carrier derivation still stands, but this assertion is stale"
    )
    assert _declared_box_numbers(revision).keys() >= (numbers | form_numbers)


def test_the_bare_number_shape_agrees_with_the_canonical_bracketed_marker() -> None:
    """The two patterns in this module must accept the same numbers.

    ``_BOX_MARKER`` matches a bracketed box in design text and is the registry's
    canonical definition; ``_BOX_SHAPED`` matches a bare registry number and cannot reuse
    it directly. Two patterns for one notion of "a box number" is exactly the shape that
    let a four-digit cap read 23 of Modelo 200's 3,440 boxes, so their agreement is
    asserted rather than maintained by habit.

    Gated on agreement, not on a digit count: it takes whatever width the canonical
    marker accepts and requires the bare-number pattern to accept the same, so widening
    the canonical one later cannot silently leave this module behind.
    """
    for width in range(1, 9):
        number = "1" * width
        bracketed = _BOX_MARKER.fullmatch(f"[{number}]") is not None
        bare = _BOX_SHAPED.fullmatch(number) is not None
        assert bracketed == bare, (
            f"a {width}-digit number is "
            f"{'accepted' if bracketed else 'rejected'} by the canonical bracketed marker but "
            f"{'accepted' if bare else 'rejected'} by this module's bare-number shape, so the two "
            "disagree about what a box number is"
        )
