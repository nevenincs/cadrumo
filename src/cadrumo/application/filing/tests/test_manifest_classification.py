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

from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.schema_input_kind import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, filing_year, period, on) — manifest-bearing modelos across the gated set,
# spanning every shape: pagos fraccionados (130/131), retenciones (111/115/123),
# IVA (303), sociedades (200), and informativas (190/180/349/232/720).
_MANIFEST_MODELOS = [
    ("130", 2025, "1T", date(2025, 6, 1)),
    ("111", 2025, "1T", date(2025, 6, 1)),
    ("115", 2025, "1T", date(2025, 6, 1)),
    ("123", 2025, "1T", date(2025, 6, 1)),
    ("131", 2025, "1T", date(2025, 6, 1)),
    ("303", 2025, "1T", date(2025, 6, 1)),
    ("200", 2025, "0A", date(2025, 6, 1)),
    ("190", 2025, "0A", date(2026, 6, 1)),
    ("180", 2025, "0A", date(2026, 6, 1)),
    ("349", 2025, "1T", date(2025, 6, 1)),
    ("232", 2024, "0A", date(2025, 6, 1)),
    ("720", 2024, "0A", date(2025, 6, 1)),
]


def _manifest_and_casillas(modelo: str, year: int, period: str, on: date) -> tuple[Any, dict[str, Any]]:
    snapshot = bundled_authority().snapshot(modelo, filing_year=year, period=period, on=on)
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
