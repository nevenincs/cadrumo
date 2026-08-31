"""A casilla exported to a rate-specific official box must pin that rate.

``rate_kinds`` and ``applied_rates`` are independent axes. A tier is not a rate:
on 2024 dates the reducido tier legitimately carries 10 %, 7,5 % and 5 %, and the
super-reducido tier carries 4 % and 2 %. So a binding that constrains only the
TIER, feeding a casilla whose official AEAT box names a RATE, sums several rates
into one box and leaves its siblings empty. That is wrong mechanically, without
needing to know what the taxpayer filed.

This is the third shape of one defect found in a single campaign -- the Reg.
ordinario tier merge, a cuota over-declaration on the 2024 temporary rates, and
the recargo de equivalencia block -- so it is a property of the binding
vocabulary rather than three incidents, and worth a gate rather than a fourth
fix.

WHICH BOXES ARE RATE-SPECIFIC IS READ FROM THE DESIGN, NOT LISTED HERE. AEAT
labels those rows itself: a box whose description declares ``Tipo N%`` is
rate-keyed by its own text. Deriving the set that way means a new rung in a
future design is covered the day the corpus is updated, and no roster of
casillas can go stale. A hardcoded list would encode today and detect nothing
tomorrow.

The set is a UNION over every bundled design year, which carries one assumption
worth stating: that a box number's rate-keyed-ness is stable across years. It
has to be a union, because the ``Tipo N%`` column does not exist in the older
designs at all -- Modelo 390's 2018 sheet says only "Recargo de equivalencia -
Cuota [36]", and the rate label first appears in 2022. So a box is recognised
here from whichever years label it, and applied to casillas regardless of year.
Measured support for the assumption: that modelo's recargo box SET is unchanged
across 2016-2022, so [36] means the same rung throughout. If a future design
ever reused a number for a differently-keyed box, this union would mis-classify
it, and that is the shape of error to look for first if this gate ever fires on
something that looks correct.

WHAT THIS DOES NOT CHECK, so its silence is not read as coverage:

Casillas carrying no official box number are invisible to it. That is not an
oversight but the same vocabulary mismatch this modelo has billed for repeatedly
-- casillas are addressed semantically, the design numerically. The export
layout can in principle decide it by offset, but not while one revision spans
several designs: page 03 offset 234 resolves to [606], [610], [727] or [49]
depending on the design year, all inside the single revision this modelo
declares. So the blindness is caused by the span, and lifts when the span is
split -- it is not an absence of any means of identification. Six such fields
exist on Modelo 390's export layout alone.

It also cannot see a box whose narrowing axis does not exist. Where the design
splits a quantity on a dimension the domain has no field for -- bienes de
inversión is the measured case -- the binding cannot pin it and no
selector-shaped rule can detect the merge. That is a taxonomy gap, and this gate
is blind to it by construction.

And it says nothing about rate-BLIND casillas, which are correct and necessary:
the total layer must catch every row including those whose rate was never
recorded. A blind binding on a TOTAL box is the design, not a defect.

See :func:`~domain.calculations.registry.derive_rate_box_partitions` for the
runtime counterpart, which derives the same two-layer shape from a revision to
compute the coverage shortfall the calculate advisory and the export refusal
share. This module asserts the structural precondition that shape assumes.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....core.resources.bundled_data import bundled_path
from ..authority import ValidatedRegistryAuthority
from ..record_design_coverage import _CASILLA_TAG_RE

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# "... - Tipo 7,5% - Cuota [670]" -- AEAT's own label declares the rate.
#
# The bracketed box shape is COMPOSED from the registry's canonical marker rather than
# re-declared here. This module held its own copy capped at four digits while production
# used five, and Modelo 200 numbers its boxes with five -- so a rate-labelled box on that
# modelo would have been invisible to a gate that iterates every modelo in the authority.
# Measured, widening changes no verdict today: Modelo 200 declares no rate-keyed row at
# either width and Modelo 390's 210 are identical. The value is removing a second
# definition of one concept before it silently under-reads, not a boundary recovered.
_RATE_KEYED_ROW = re.compile(r"Tipo\s+[\d,]+\s*%.*?" + _CASILLA_TAG_RE.pattern)


def _authority() -> ValidatedRegistryAuthority:
    return ValidatedRegistryAuthority.load(bundled_path("registry", "aeat"), source_root=bundled_path())


def _design_files(modelo_id: str) -> tuple[Path, ...]:
    # Recursive, not the fixed-depth "files/*.extracted.md": the same
    # directory-shape assumption already dropped Modelo 210's dr210_2011.pdf from
    # other design enumerations in this module family. No sidecar sits outside
    # files/ today (converged pre-emptively, dormant when converged, not a bug fix).
    directory = bundled_path("corpus", "aeat_official", "disenos_registro", f"modelo_{modelo_id}")
    return scan_directory(directory, pattern="*.extracted.md", recursive=True)


def _rate_specific_boxes(modelo_id: str) -> set[str]:
    """Box numbers the design itself labels with a rate, across every bundled year."""
    boxes: set[str] = set()
    for path in _design_files(modelo_id):
        text = path.read_text(encoding="utf-8", errors="replace")
        boxes.update(_RATE_KEYED_ROW.findall(text))
    return boxes


def _pinned_rates(binding) -> tuple[object, ...] | None:
    """The binding's ``applied_rates`` narrowing, or None when it has no such axis."""
    selector = getattr(binding, "selector", None)
    raw_rates = getattr(selector, "applied_rates", None) if selector is not None else None
    if raw_rates is None:
        return None
    return tuple(item for item in raw_rates)


def _selector_supports_rates(binding) -> bool:
    selector = getattr(binding, "selector", None)
    return selector is not None and hasattr(selector, "applied_rates")


def _offenders() -> list[str]:
    """Every casilla on a rate-labelled box whose binding constrains no rate."""
    offenders: list[str] = []
    for modelo in _authority().modelos:
        rate_boxes = _rate_specific_boxes(modelo.id)
        if not rate_boxes:
            continue
        for revision_id, revision in modelo.revisions.items():
            bindings = {binding.id: binding for binding in revision.bindings}
            for casilla in revision.casillas:
                number = (casilla.number or "").strip()
                if number not in rate_boxes or casilla.binding is None:
                    continue
                binding = bindings.get(casilla.binding)
                # A binding whose selector has no rate axis at all is a different
                # source kind entirely; it is out of scope rather than passing.
                if binding is None or not _selector_supports_rates(binding):
                    continue
                if not _pinned_rates(binding):
                    offenders.append(
                        f"modelo {modelo.id} revision {revision_id!r}: casilla {casilla.id!r} is "
                        f"exported to box [{number}], which the design labels with a rate, but its "
                        f"binding {binding.id!r} pins no applied_rates -- it sums every rate in its "
                        "tier into one rate's box"
                    )
    return offenders


def _guarded_casillas() -> list[str]:
    """Every casilla this module can actually see: it declares a rate-keyed box."""
    seen: list[str] = []
    for modelo in _authority().modelos:
        rate_boxes = _rate_specific_boxes(modelo.id)
        if not rate_boxes:
            continue
        for revision in modelo.revisions.values():
            seen.extend(casilla.id for casilla in revision.casillas if (casilla.number or "").strip() in rate_boxes)
    return seen


def test_the_parser_reads_rate_keyed_boxes_from_the_design() -> None:
    """Anti-vacuity: if nothing parses, every check below agrees with everything.

    Scoped to "at least one modelo", not "every modelo", because a design that
    declares no rate-keyed box is a real and legitimate shape rather than a parse
    failure -- Modelo 303 carries its rate as a design constant in a column
    instead of labelling boxes with it, so it is genuinely out of scope here. A
    per-modelo assertion would report that correct difference as a broken parser.
    """
    parsed = {modelo.id: len(_rate_specific_boxes(modelo.id)) for modelo in _authority().modelos}
    assert any(parsed.values()), (
        "no rate-labelled box parsed for ANY modelo; the design label shape or the corpus path has "
        f"moved and this module now checks nothing. Per-modelo counts: {parsed}"
    )


def test_the_gate_can_see_something_to_guard() -> None:
    """The second anti-vacuity half, and the one that states this gate's real reach.

    A casilla is visible here only if it declares a rate-keyed box NUMBER. That
    is a narrow population, and narrower than the defect: the three Modelo 390
    recargo casillas that demonstrably merge rates carry no number at all, so
    this module cannot see them. **Its blind spot and the defect's cause are the
    same fact** -- a casilla nobody gave a box number is a casilla nobody checked
    against the box's own label, which is how the merge survived.

    So read this gate as a REGRESSION LOCK on boxes already identified, not as a
    detector of the existing class. It fails if that population empties, which
    would mean the numbers were removed and the lock silently released.
    """
    guarded = _guarded_casillas()
    assert guarded, (
        "no casilla declares a rate-keyed official box number, so this gate guards nothing; "
        "either the box numbers were removed or the design parse has broken"
    )


def test_a_casilla_on_a_rate_keyed_box_pins_its_rate() -> None:
    """A rate-keyed box must be fed by a binding that admits exactly that rate.

    A tier is not a rate. Constraining only the tier while writing to a box the
    design labels with a rate merges several rates into one official figure and
    leaves the sibling boxes empty -- a false breakdown on a filed artefact,
    detectable from the registry and the corpus alone.
    """
    offenders = _offenders()
    assert not offenders, (
        "these casillas write a rate-labelled official box from a binding that constrains only "
        "the tier, so several rates are summed into one box:\n  " + "\n  ".join(offenders)
    )
