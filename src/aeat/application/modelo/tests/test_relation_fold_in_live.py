"""Relation cross-modelo fold-in fires on the LIVE calculate path.

Previously the registry relations were dead on the live operator calculate
path: ``RelationPrefillSourceResolver`` was not enrolled in the
``merge_source_resolutions`` mesh, so a cross-modelo fold-in (M180 annual ←
M115 quarterly, M100 pagos-fraccionados ← M130, the M180/M190/M193
reconciliations, the M200/M202 carries) resolved to a silent blank. The relation
became canonical for cross-modelo fold-in (aggregation-taxonomy rulings 2-4):
the resolver is enrolled, it folds prior filed observations through each declared
relation's aggregation op, and it materialises the result into the relation's
``target_binding`` slot (re-stamped from ``previous_filing`` to
``relation_prefill``). The materialised binding rides in the resolution's
``binding_values`` so the mesh ``_claim_binding`` exclusive-ownership guard
adjudicates any collision loudly.

These are real-behaviour tests against the REAL backend (real encrypted-SQLite
observation store, real registry authority, real calculation engine, real
relation resolver, real source mesh — no mocks/skips/xfail):

* ``test_modelo_180_115_fold_in_fires_on_live_calculate`` proves the fold-in now
  populates the M180 annual output casillas from the four filed M115 quarters,
  and asserts the values equal the summed quarters (wiring invariant grounded in
  the AEAT resumen instructions, not a reproduction of the formula under test).

* ``test_relation_target_collision_refused_by_mesh_guard`` proves a second
  resolver claiming the same relation-materialised target binding is refused
  loudly by the mesh ``_claim_binding`` guard (an ``AggregationValidationError``)
  rather than silently overridden — the double-write closure.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import (
    CasillaId,
    RegistryModeloObservation,
    calculate_registry_snapshot,
    resolve_bound_inputs_by_casilla_id,
    validated_casilla_id,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation._errors import AggregationValidationError
from ...aggregation._source_mesh import (
    CalculationSourceContext,
    CalculationSourceResolution,
    merge_source_resolutions,
)
from ...calculations import RelationPrefillSourceResolver
from ...calculations._observations_repository import CalculationObservationRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-fold-in"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2025


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"relation fold-in fixture casilla key {value!r} is not a CasillaId") from exc


_M115_PERCEPTORES_CASILLA: CasillaId = _casilla_id("01")
_M115_BASE_CASILLA: CasillaId = _casilla_id("02")
_M115_RETENCIONES_CASILLA: CasillaId = _casilla_id("03")
_M115_ANTERIORES_CASILLA: CasillaId = _casilla_id("04")
_M180_TOTAL_PERCEPTORES_CASILLA: CasillaId = _casilla_id("decl.total-perceptores")
_M180_BASE_TOTAL_CASILLA: CasillaId = _casilla_id("decl.base-total")
_M180_RETENCIONES_TOTAL_CASILLA: CasillaId = _casilla_id("decl.retenciones-total")

# Distinct per-quarter bases so a cross-quarter contamination surfaces as a
# mismatch. Casilla 01 = perceptores (manual int), 02 = base (manual money),
# 03 = retenciones (computed 19% of 02), 04 = anteriores (manual zero).
_QUARTERS: dict[str, dict[CasillaId, Decimal]] = {
    "1T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1200.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "2T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1350.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "3T": {
        _M115_PERCEPTORES_CASILLA: Decimal("3"),
        _M115_BASE_CASILLA: Decimal("900.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
    "4T": {
        _M115_PERCEPTORES_CASILLA: Decimal("2"),
        _M115_BASE_CASILLA: Decimal("1100.00"),
        _M115_ANTERIORES_CASILLA: Decimal("0"),
    },
}


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_115_quarters(*, obs_repo: CalculationObservationRepository) -> dict[CasillaId, Decimal]:
    """Calculate + persist the four 115 quarters; return the summed 01/02/03 totals."""
    auth = resources().modelos.authority
    totals: dict[CasillaId, Decimal] = {
        _M115_PERCEPTORES_CASILLA: Decimal("0"),
        _M115_BASE_CASILLA: Decimal("0"),
        _M115_RETENCIONES_CASILLA: Decimal("0"),
    }
    for period, casilla_inputs in _QUARTERS.items():
        snapshot = auth.snapshot("115", filing_year=_YEAR, period=period)
        inputs = {**resolve_bound_inputs_by_casilla_id(snapshot.revision, {}), **casilla_inputs}
        result = calculate_registry_snapshot(
            snapshot,
            inputs=inputs,
            binding_values={},
            date_context={"filing_period": date(_YEAR, 12, 31)},
        )
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="115",
                filing_year=_YEAR,
                period=period,
                observations=result.observations,
            ),
            source_kind="app_filing",
            captured_at=_T0,
        )
        for cid in totals:
            totals[cid] += result.values[cid]
    return totals


def test_modelo_180_115_fold_in_fires_on_live_calculate(secure_objects: SecureObjectRepository) -> None:
    """The M180 annual ← M115 quarterly fold-in populates on the live calculate path.

    With four 115 quarters recorded as filed observations, a live calculate of
    the M180 annual draws the relation values through the enrolled
    ``RelationPrefillSourceResolver`` and the three M180 output casillas equal
    the summed 115 quarters. Before relation enrollment these casillas were a
    silent blank.
    """
    obs_repo = CalculationObservationRepository()
    expected = _seed_115_quarters(obs_repo=obs_repo)

    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot_180 = resources().modelos.authority.snapshot("180", filing_year=_YEAR, period="0A")
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision_id=snapshot_180.revision.id,
        repository=wu_repo,
        clock=_T0,
    )

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )

    casilla_values = result.revision.casilla_values
    # Fold-in fires: each output equals the summed 115 quarters (was blank before).
    assert casilla_values[_M180_TOTAL_PERCEPTORES_CASILLA] == expected[_M115_PERCEPTORES_CASILLA]
    assert casilla_values[_M180_BASE_TOTAL_CASILLA] == expected[_M115_BASE_CASILLA]
    assert casilla_values[_M180_RETENCIONES_TOTAL_CASILLA] == expected[_M115_RETENCIONES_CASILLA]
    # Non-vacuous: the summed base must be strictly positive so a silent blank
    # (0) would fail the assertion above.
    assert expected[_M115_BASE_CASILLA] > Decimal("0")


def test_relation_target_collision_refused_by_mesh_guard(secure_objects: SecureObjectRepository) -> None:
    """A second resolver claiming a relation-materialised target binding is refused loudly.

    The relation resolver materialises its resolved relation values into the
    relation's ``target_binding`` slot and emits them in ``binding_values``. If
    another resolver in the mesh also claims that binding id, the mesh
    ``_claim_binding`` exclusive-ownership guard raises rather than silently
    out-ranking one of the two (the double-write closure, aggregation-taxonomy ruling 4).
    """
    obs_repo = CalculationObservationRepository()
    _seed_115_quarters(obs_repo=obs_repo)

    snapshot_180 = resources().modelos.authority.snapshot("180", filing_year=_YEAR, period="0A")
    context = CalculationSourceContext(
        bucket_id=_BUCKET_ID,
        modelo="180",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "0A"),
        revision=snapshot_180.revision,
        calculated_at=_T1,
    )
    relation_resolution = RelationPrefillSourceResolver(
        repository=obs_repo,
        registry_snapshot=snapshot_180,
    ).resolve(context)
    # Non-vacuous: the relation resolution must have materialised at least one
    # target binding for the collision to be possible.
    assert relation_resolution.binding_values, "relation resolver materialised no target bindings"

    colliding_binding_id = next(iter(relation_resolution.binding_values))
    rival = CalculationSourceResolution(
        resolver_id="rival_resolver",
        owned_sources=("manual_input",),
        binding_values={colliding_binding_id: Decimal("99999.99")},
    )

    with pytest.raises(AggregationValidationError):
        merge_source_resolutions((relation_resolution, rival))
