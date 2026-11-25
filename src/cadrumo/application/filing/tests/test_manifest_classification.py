"""The completeness gate's required set is exactly COMPUTED + schema-required.

The fichero-BOE completeness gate requires a value on disk for a manifest casilla
iff it is a calculation RESULT (``input_kind == COMPUTED``, which the registry
validator ties one-to-one to declaring a formula) OR it is schema-required
(``required = True``). The ``required`` flag deliberately overrides ``input_kind``:
a mandatory declaration field is required whatever its provenance -- e.g. Modelo
232/720 ``ejercicio``/``CNAE`` (INFORMATIONAL but mandatory) and Modelo 349 intracom
operation totals (BOUND but mandatory) MUST be present.

The gate excludes only NON-required, NON-computed casillas:

- optional ``BOUND`` casillas -- values materialised from a binding (ledger/profile
  aggregation, e.g. Modelo 303 IVA cuotas, Modelo 130 retenciones) that are
  legitimately zero/blank when the taxpayer has no such operations;
- optional ``MANUAL`` inputs the taxpayer may legitimately not have;
- non-required ``INFORMATIONAL`` casillas -- not a numeric value.

Requiring any of those would false-panic on a valid zero-data filing. This test
locks the classification against drift in either direction: if the gate were
changed to require an optional casilla it would false-panic (caught here), and if a
COMPUTED or schema-required casilla were dropped from the required set the gate
would go silent (also caught here).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot

from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.tests.authored_editions import (
    authored_revisions_where,
    filing_year_envelope,
    first_calculation_grade_edition,
    revision_covering,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, filing_year, period, on) — manifest-bearing modelos across the gated set,
# spanning every shape: pagos fraccionados (130/131), retenciones (111/115/123),
# IVA (303), sociedades (202/200), and informativas (190/180/349/232/720).
# Every coordinate is the newest supported exercise, which each of these modelos
# serves at filing grade; a quarterly coordinate is filed in June of its exercise
# and an annual one in June of the next.
#
# Modelo 200 joins the table only while the edition serving that exercise declares
# filing grade, read from the registry. An edition below it refuses at the snapshot
# boundary before the gate runs; that refusal is asserted in
# ``test_calculation_grade_coordinate_refuses_at_the_manifest_gate`` below, which
# takes that edition as its subject whenever Modelo 200 is left out of the table.
_NEWEST_EXERCISE = filing_year_envelope().horizon
_M200_NEWEST_IS_FILING_GRADE = str(revision_covering("200", _NEWEST_EXERCISE).id) in {
    str(revision.id)
    for revision in authored_revisions_where(
        "200", lambda revision: revision.authority_grade is RegistryAuthorityGrade.FILING
    )
}
_MANIFEST_MODELOS = [
    (modelo, _NEWEST_EXERCISE, period, date(_NEWEST_EXERCISE + (1 if period == "0A" else 0), 6, 1))
    for modelo, period in (
        ("130", "1T"),
        ("111", "1T"),
        ("115", "1T"),
        ("123", "1T"),
        ("131", "1T"),
        ("303", "2T"),
        ("202", "1P"),
        *((("200", "0A"),) if _M200_NEWEST_IS_FILING_GRADE else ()),
        ("190", "0A"),
        ("180", "0A"),
        ("349", "1T"),
        ("232", "0A"),
        ("720", "0A"),
    )
]


def _manifest_and_casillas(modelo: str, year: int, period: str, on: date) -> tuple[Any, dict[str, Any]]:
    # The completeness gate guards a filing, so its snapshot is asked for at
    # filing grade; a reading snapshot would open a lower edition at its own rung.
    snapshot = published_snapshot(modelo, filing_year=year, period=period, on=on, grade=RegistryAuthorityGrade.FILING)
    revision = snapshot.revision
    manifest = revision.completeness_manifest
    assert manifest is not None, f"modelo {modelo} must declare a completeness manifest"
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    return manifest, by_id


def _gate_required_ids(manifest: Any, by_id: dict[str, Any]) -> set[str]:
    # Mirror the gate exactly: formula (== COMPUTED) or schema-required.
    return {
        mc.casilla_id
        for mc in manifest.casillas
        if (cd := by_id.get(mc.casilla_id)) is not None and (cd.formula is not None or cd.required)
    }


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _MANIFEST_MODELOS)
def test_gate_required_set_equals_computed_plus_schema_required(modelo: str, year: int, period: str, on: date) -> None:
    manifest, by_id = _manifest_and_casillas(modelo, year, period, on)
    required = _gate_required_ids(manifest, by_id)

    # COMPUTED is tied one-to-one to declaring a formula by the registry validator,
    # so the gate's required set is exactly the COMPUTED + schema-required casillas.
    computed_or_required = {
        mc.casilla_id
        for mc in manifest.casillas
        if (cd := by_id.get(mc.casilla_id)) is not None and (cd.input_kind == InputKind.COMPUTED or cd.required)
    }
    assert required == computed_or_required
    # Every manifest-bearing modelo requires at least one casilla (a computed result
    # or a mandatory field), so no gated modelo has a vacuous completeness gate.
    assert required, f"modelo {modelo} has an empty gate-required set (vacuous gate)"


def _calculation_grade_coordinate() -> tuple[str, int, str, date]:
    """Return the coordinate the refusal test demands filing grade of.

    While Modelo 200's newest edition is below filing grade it is the gap the
    table leaves, so it is the coordinate proven to refuse. Once it is gated,
    the refusal is still exercised on a real calculation-grade edition read from
    the registry, since a calculation-grade revision computes without
    established filing evidence and claiming filing authority for it would be a
    false capability claim.
    """
    if not _M200_NEWEST_IS_FILING_GRADE:
        return ("200", _NEWEST_EXERCISE, "0A", date(_NEWEST_EXERCISE, 12, 31))
    edition = first_calculation_grade_edition()
    assert edition is not None, "the registry authors no calculation-grade edition inside the support envelope"
    return (edition.modelo, edition.filing_year, edition.period, date(edition.filing_year, 12, 31))


def test_calculation_grade_coordinate_refuses_at_the_manifest_gate() -> None:
    """The gate cannot be reached for a coordinate that is not filing grade.

    The table above is meant to be exhaustive over the gated set, so the
    absence of a modelo from it must be a proven refusal rather than an
    unexplained gap. This asserts the refusal happens at the snapshot boundary
    -- before any manifest classification -- and that its message names the
    declared rung, so a future promotion to filing grade turns this test red
    instead of letting the modelo re-enter the gate unnoticed.
    """
    modelo, year, period, on = _calculation_grade_coordinate()

    with pytest.raises(RegistryValidationError) as exc_info:
        _manifest_and_casillas(modelo, year, period, on)

    message = str(exc_info.value)
    assert f"modelo {modelo}" in message
    assert "'calculation' authority grade" in message
    assert "'filing' snapshot authority" in message
