"""Grounding travels with every data-inventory checklist entry.

A ``modelo requires`` entry tells an operator which casilla to supply data for.
An entry that cannot name the provision establishing the casilla, or the source
the figure comes from, is an instruction with no legal basis attached, so the
checklist type refuses to build one at all rather than leaving the refusal to
whichever consumer happens to render it.

The refusal is deliberately redundant with the registry: a
:class:`~domain.calculations.registry.schema_surfaces.CasillaDefinition`
already declares both ref tuples ``min_length=1``, so the sole producer copies
grounding that cannot be empty. The type still states the guarantee itself,
because the producer's correctness is a property of today's producer while the
invariant is a property of the record.
"""

from __future__ import annotations

import pytest

from ....core.casilla_id import CasillaId
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.ids import LegalRefId, SourceRefId
from ..data_inventory import DataInventoryCasilla

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_GROUNDED_CASILLA_ID: CasillaId = "iva.devengado.base"
_GROUNDED_LEGAL_REFS: tuple[LegalRefId, ...] = ("liva-art-78",)
_GROUNDED_SOURCE_REFS: tuple[SourceRefId, ...] = ("aeat-modelo-303-instrucciones",)


def _a_grounded_entry(
    *,
    casilla_id: CasillaId = _GROUNDED_CASILLA_ID,
    number: str = "01",
    label: str = "Base imponible",
    legal_refs: tuple[LegalRefId, ...] = _GROUNDED_LEGAL_REFS,
    source_refs: tuple[SourceRefId, ...] = _GROUNDED_SOURCE_REFS,
) -> DataInventoryCasilla:
    """Build one checklist entry, grounded unless an override empties it."""
    return DataInventoryCasilla(
        casilla_id=casilla_id,
        number=number,
        label=label,
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def test_a_grounded_entry_builds() -> None:
    """The positive control: the refusal below is not refusing everything."""
    entry = _a_grounded_entry()

    assert entry.legal_refs == ("liva-art-78",)
    assert entry.source_refs == ("aeat-modelo-303-instrucciones",)


def test_an_entry_without_legal_refs_is_refused() -> None:
    """A casilla with no establishing provision cannot reach the operator."""
    with pytest.raises(ValueError, match="legal_refs") as excinfo:
        _a_grounded_entry(legal_refs=())

    assert "iva.devengado.base" in str(excinfo.value)


def test_an_entry_without_source_refs_is_refused() -> None:
    """Source grounding is enforced independently of legal grounding."""
    with pytest.raises(ValueError, match="source_refs") as excinfo:
        _a_grounded_entry(source_refs=())

    assert "iva.devengado.base" in str(excinfo.value)


def test_an_entry_missing_both_names_both_in_the_refusal() -> None:
    """The operator is told everything that is missing, not just the first."""
    with pytest.raises(ValueError) as excinfo:
        _a_grounded_entry(legal_refs=(), source_refs=())

    message = str(excinfo.value)
    assert "legal_refs" in message
    assert "source_refs" in message


def test_grounding_cannot_be_omitted_at_construction() -> None:
    """Neither ref tuple carries a default, so an entry cannot skip them.

    A defaulted empty tuple would be a value the invariant can never accept,
    which is precisely how an ungrounded entry would be built by accident.
    """
    with pytest.raises(TypeError, match="legal_refs"):
        DataInventoryCasilla(  # type: ignore[call-arg]  # ty: ignore[missing-argument]  # reason: omitting the grounding IS the refusal under test
            casilla_id="iva.devengado.base",
            number="01",
            label="Base imponible",
        )


def test_every_committed_casilla_can_ground_a_checklist_entry() -> None:
    """The real registry satisfies the invariant, so no producer is broken.

    Walks every casilla the bundled registry declares and asserts each carries
    the grounding an entry needs. This is what makes the refusal safe to add:
    were any committed casilla ungrounded, the sole producer would now raise on
    a real ``modelo requires`` call rather than emitting a blank.
    """
    scanned = 0
    for model in bundled_authority().modelos:
        for revision in model.revisions.values():
            for casilla in revision.casillas:
                scanned += 1
                assert casilla.legal_refs, f"{model.id}/{revision.id}/{casilla.id} has no legal_refs"
                assert casilla.source_refs, f"{model.id}/{revision.id}/{casilla.id} has no source_refs"

    assert scanned, "the bundled registry declared no casillas; this test would pass vacuously"
