"""A static inspection's export exposure and continuity equal the revision's own.

``RegistryRevisionInspection`` carries two projections a static consumer
cannot otherwise reach without being handed the whole revision:
``casilla_export_refs``, which says which official record fields carry a
casilla, and ``casilla_continuity``, which says which cross-revision concept a
casilla continues. Both are copies, and a copy is only worth carrying while it
still equals its source.

The export half is checked against ``derive_casilla_export_refs`` run here over
the revision's own layouts and bindings -- the same derivation the registry
compiler runs when it fills ``CasillaDefinition.export_refs`` -- rather than
against the stored ``export_refs`` alone. Comparing the inspection's copy with
the definition it was copied from would agree by construction; re-deriving from
the layout proves both the copy AND the value it copied still describe the
official record design.

Modelo 390 is the subject because its layout addresses casillas: a modelo whose
export layout resolves to no casilla would let both sides be empty and the
comparison would assert nothing.
"""

from __future__ import annotations

import pytest

from ..export_field_casilla import derive_casilla_export_refs
from .published_authority import published_inspection, published_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]

_MODELO = "390"
_FILING_YEAR = 2024
_PERIOD = "0A"


def test_the_subject_modelo_really_addresses_casillas_through_its_export_layout() -> None:
    """Without this, both sides of the parity check could be empty and still agree."""
    inspection = published_inspection(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)
    revision = published_revision(_MODELO, str(inspection.revision_id))

    derived = derive_casilla_export_refs(revision.export_layouts, revision.bindings)

    assert derived, (
        f"modelo {_MODELO} revision {inspection.revision_id} resolves no casilla through its export layout, "
        "so the parity assertion below would compare two empty mappings and prove nothing"
    )


def test_inspection_export_exposure_equals_the_layout_derivation() -> None:
    """The projected exposure is the compiler's derivation, key for key and in order."""
    inspection = published_inspection(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)
    revision = published_revision(_MODELO, str(inspection.revision_id))

    derived = derive_casilla_export_refs(revision.export_layouts, revision.bindings)

    assert dict(inspection.casilla_export_refs) == derived, (
        "the static inspection's casilla_export_refs no longer equals the derivation the compiler "
        "fills CasillaDefinition.export_refs from, so a workspace reading it would name the wrong "
        "record fields for a casilla"
    )


def test_an_unaddressed_casilla_is_absent_rather_than_present_and_empty() -> None:
    """Absence and an empty tuple must not both be reachable for one casilla.

    The mapping's contract is that a casilla appears exactly when some export
    field resolves to it. A key carrying an empty tuple would read as "the
    record addresses this casilla with no fields", which is not a state the
    derivation can produce and not a claim the registry makes.
    """
    inspection = published_inspection(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)

    assert all(inspection.casilla_export_refs.values()), (
        "a casilla is carried with an empty export-field tuple, which collapses 'no export field "
        "addresses this casilla' into 'the record addresses it with nothing'"
    )
    assert set(inspection.casilla_export_refs) <= set(inspection.casilla_ids)


def test_inspection_continuity_equals_the_revision_declarations() -> None:
    """Continuity is the casillas' own declared keys, with undeclared rows absent."""
    inspection = published_inspection(_MODELO, filing_year=_FILING_YEAR, period=_PERIOD)
    revision = published_revision(_MODELO, str(inspection.revision_id))

    declared = {
        casilla.id: casilla.continuidad_id for casilla in revision.casillas if casilla.continuidad_id is not None
    }

    assert dict(inspection.casilla_continuity) == declared
    assert set(inspection.casilla_continuity) <= set(inspection.casilla_ids)
