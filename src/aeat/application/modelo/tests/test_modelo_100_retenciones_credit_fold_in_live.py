"""M100 retenciones-credit casillas fold in periodic withholding filings (LIVE path).

The annual IRPF declaration (Modelo 100) credits the withholdings already
practised during the year against the cuota. Two of those credit casillas are
genuine cross-modelo *retenciones-credit* folds: each is a ``bound`` casilla
whose ``relation_prefill`` binding sums a periodic source modelo's retenciones
output through the enrolled :class:`RelationPrefillSourceResolver`:

* casilla ``0596`` ("Por rendimientos del trabajo") binds
  ``renta-2024-modelo-111-retenciones-periodicas`` — ``source_modelo='111'``,
  ``source_casilla_id='28'`` (M111 "retenciones e ingresos a cuenta"), summed over
  the four quarters.
* casilla ``0597`` ("Por rendimientos del capital mobiliario") binds
  ``renta-2024-modelo-123-retenciones-periodicas`` — ``source_modelo='123'``,
  ``source_casilla_id='09'`` (M123 retenciones), summed over the four quarters.

This module proves both folds work end-to-end on the LIVE operator calculate
path (:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`):
four filed M111 quarters fold into ``0596`` and four filed M123 quarters fold
into ``0597``.

The M100 ``0604`` ("Pagos fraccionados ingresados") casilla is *computed* by a
formula that references the M130 and M131 pagos-fraccionados relations DIRECTLY,
so the engine raises ``RegistryValidationError`` for any of those relations it
cannot resolve. The full-snapshot live calculate therefore also requires the
M130/M131 pagos legs to be present; this persona seeds them (M130 as four
distinct quarters, M131 as a true zero) so the calculate reaches the retenciones
casillas. The pagos values are NOT what this module asserts — they only keep the
engine from raising before ``0596`` / ``0597`` resolve. (The pagos fold itself is
proven by ``test_modelo_100_pagos_fraccionados_fold_in_live``.)

Real-behaviour, real-adapter (real encrypted-SQLite observation store via
:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider`, real
registry authority, real calculation engine, real relation resolver, real source
mesh — no mocks, stubs, skips, or xfail).

The aggregation assertions (``0596 == sum(four seeded M111 c28)`` and
``0597 == sum(four seeded M123 c09)``) are fold-WIRING invariants, not
tautologies: the four seeded per-quarter values are DISTINCT non-equal known
Decimals, so an off-by-quarter, a single-quarter copy, a silent blank, or a
coincidental sum cannot satisfy the assertion. The test does not recompute any
registry IRPF formula — it proves the enrolled relation resolver wires the four
prior periodic filings through to each annual credit casilla.

WIRING-GAP CARVE-OUT: the M100/2024 revision declares two further
``relation_prefill`` retenciones bindings whose relations fold a source modelo's
retenciones output, but NO casilla binds to either — they are ORPHANED bindings
(the same wiring-gap shape found in the M200 base-determination and M369 OSS paths):

* ``renta-2024-modelo-115-retenciones-periodicas`` (M115 ``source_casilla_id='03'``,
  arrendamientos retención): the only inmobiliario-retención casilla, ``0598``,
  is ``computed`` by formula ``renta-2024-retenciones-arrendamientos-urbanos``
  (= ``copy(0153)``), where ``0153`` is a per-inmueble MANUAL input
  (``irpf_inmueble_retenciones_ingresos_a_cuenta``), not the M115 binding. The
  M115 relation folds into a binding that no casilla consumes.
* ``renta-2024-modelo-193-retenciones-anuales`` (M193 ``source_casilla_id=
  'decl.retenciones-total'``, copy): no casilla binds it; the capital-mobiliario
  retención casilla ``0597`` consumes the M123 binding, not M193.

Both orphaned bindings are referenced only by their own definition, their
relation's ``target_binding``, and the ``dependent-modelos`` construct — never by
a casilla ``binding`` field nor a formula. They are NOT proven-live here; the gap
is reported precisely so the epic can decide whether to wire a consuming casilla
or retire the orphaned binding.
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
    BindingId,
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import TransactionCatalogueRepository
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
)
from .._filed_revision_observation import APP_FILING_SOURCE_KIND

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-m100-retenciones-fold"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2024
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_RELATION_PREFILL_SOURCE = "relation_prefill"

# The two genuine cross-modelo retenciones-credit casillas and their source casilla ids.
_M100_TRABAJO_CASILLA: CasillaId = validated_casilla_id("0596", surface="_M100_TRABAJO_CASILLA")
_M100_CAPITAL_MOBILIARIO_CASILLA: CasillaId = validated_casilla_id(
    "0597",
    surface="_M100_CAPITAL_MOBILIARIO_CASILLA",
)
_M111_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("28", surface="_M111_RETENCIONES_OUTPUT")
_M123_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("09", surface="_M123_RETENCIONES_OUTPUT")
_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "1391",
    surface="_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA",
)

# Four DISTINCT non-equal quarterly M111 c28 retenciones-rendimientos-del-trabajo
# values. Distinctness makes the annual fold unmistakable: an off-by-one-quarter
# or coincidental sum cannot satisfy the assertion.
_M111_C28_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("110.00"),
    "2T": Decimal("275.50"),
    "3T": Decimal("90.25"),
    "4T": Decimal("330.00"),
}
# Four DISTINCT non-equal quarterly M123 c09 retenciones-capital-mobiliario
# values, deliberately disjoint from the M111 totals so a cross-wired fold
# (M111 summed into 0597, etc.) would red the per-casilla assertions.
_M123_C09_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("12.34"),
    "2T": Decimal("56.78"),
    "3T": Decimal("9.10"),
    "4T": Decimal("43.21"),
}

# The 0604 pagos formula references the M130 and M131 pagos relations DIRECTLY,
# so both legs must resolve for the full-snapshot calculate not to raise before
# the retenciones casillas. M130 is seeded as four distinct quarters; M131 as a
# true zero (this persona has no estimación-objetiva activity). These values are
# NOT asserted here — they merely let the engine reach 0596 / 0597.
_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("100.00"),
    "2T": Decimal("250.50"),
    "3T": Decimal("75.25"),
    "4T": Decimal("300.00"),
}
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _seed_quarterly_filing(
    *,
    obs_repo: CalculationObservationRepository,
    source_modelo: str,
    period: str,
    casilla_id: CasillaId,
    value: Decimal,
) -> None:
    """Persist one filed source-modelo quarter carrying a single source casilla id.

    Persisted through the production observation-persistence API
    (:meth:`CalculationObservationRepository.save_observation`) — the same write
    path the local-file carry flow uses — stamped with the non-official
    ``app_filing`` source_kind.
    """
    obs_repo.save_observation(
        RegistryModeloObservation(
            modelo=source_modelo,
            filing_year=_YEAR,
            period=period,
            observations=registry_grounded_observations(
                modelo=source_modelo,
                filing_year=_YEAR,
                period=period,
                casilla_values={casilla_id: value},
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _seed_pagos_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Seed the M130 (four distinct quarters) and M131 (true zero) pagos legs.

    The M100 0604 formula references both pagos relations directly; the engine
    raises for any it cannot resolve. Seeding them keeps the full-snapshot
    calculate from raising before the retenciones casillas 0596 / 0597 resolve.
    These values are not asserted by this module.
    """
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="130",
            period=period,
            casilla_id=_M130_PAGOS_OUTPUT,
            value=_M130_C19_BY_PERIOD[period],
        )
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="131",
            period=period,
            casilla_id=_M131_PAGOS_OUTPUT,
            value=Decimal("0"),
        )


def _seed_prior_year_m100_zero_carry(secure_objects: SecureObjectRepository) -> None:
    CalculationObservationRepository(objects=secure_objects).save_observation(
        RegistryModeloObservation(
            modelo="100",
            filing_year=_YEAR - 1,
            period=_ANNUAL_PERIOD,
            observations=registry_grounded_observations(
                modelo="100",
                filing_year=_YEAR - 1,
                period=_ANNUAL_PERIOD,
                casilla_values={_M100_BASE_LIQUIDABLE_NEGATIVA_GENERAL_CASILLA: Decimal("0")},
            ),
        ),
        source_kind=APP_FILING_SOURCE_KIND,
        captured_at=_T0,
    )


def _seed_taxpayer_unit_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed a single-taxpayer ``UserProfileRecord`` covering M100's profile bindings.

    The M100/2024 annual revision declares ``source = "profile"`` bindings (the
    taxpayer birth date for ``age_at_year_end``, CCAA, declaration type, marital
    status, minor-children counts). Without them the engine refuses the bound
    casillas that consume them before it ever reaches the retenciones casillas.
    The profile is the substrate of record, so the live source mesh's profile
    resolver auto-fills these — no profile fact is hand-fed through the caller
    channel. Mirrors
    ``test_modelo_100_pagos_fraccionados_fold_in_live._seed_taxpayer_unit_profile``.
    """
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
            UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
            UserProfileFact(path="censo.activity_start_date", value=date(2020, 1, 1)),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="H"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
            UserProfileFact(path="renta_taxpayer.marriage_full_year", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
            UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
            UserProfileFact(path="filing_export.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_minimos_aggregate_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.gastos_guarderia_reales_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendientes_menores_3_2024", value=Decimal("0")),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=Decimal("0")),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID, objects=secure_objects).save(record)


def _non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default every M100/2024 binding that is neither profile- nor relation-sourced.

    The annual M100 revision binds many casillas (the Anexo-C base-liquidable
    carry, etc.) whose values an empty bucket does not supply; the engine refuses
    the consuming casilla before reaching the retenciones casillas. These are
    supplied as zero through the caller channel (this retenciones-fold persona
    declares no other prior activity), leaving every ``relation_prefill`` binding
    UNSET so the enrolled relation resolver folds them from the seeded source
    store on the live path. Mirrors the non-profile zero-default in
    ``test_modelo_100_pagos_fraccionados_fold_in_live._non_relation_zero_bindings``.
    """
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source
        not in (
            "profile",
            _RELATION_PREFILL_SOURCE,
            "ledger_renta_income_aggregation",
            "ledger_renta_expense_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
        )
    }


def _calculate_m100_annual(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    """Run the live M100/2024/0A calculate over the seeded bucket.

    Seeds the taxpayer profile and zero-defaults non-profile/non-relation
    bindings so the engine reaches the retenciones casillas; the
    ``relation_prefill`` bindings are deliberately left UNSET so the enrolled
    relation resolver folds them from the seeded observation store.
    """
    _seed_taxpayer_unit_profile(secure_objects)
    _seed_prior_year_m100_zero_carry(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        binding_values=_non_relation_zero_bindings(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def _assert_distinct_positive(values: dict[str, Decimal]) -> Decimal:
    """Return the sum of ``values`` after asserting they are distinct and positive.

    Distinct non-equal positive values make the downstream fold assertion
    non-tautological: a silent blank (0), a single-quarter copy, or an
    off-by-quarter wiring cannot reproduce the strictly-positive sum of four
    distinct quarters.
    """
    assert len(set(values.values())) == len(values), f"seeded quarters must be distinct; got {values}"
    total = sum(values.values(), Decimal("0"))
    assert total > Decimal("0")
    return total


def test_m100_retenciones_credits_fold_in_periodic_filings_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: four filed M111 quarters fold into 0596 and four M123 quarters into 0597.

    With four M111/2024 quarters recorded as filed observations (each carrying a
    DISTINCT c28) and four M123/2024 quarters (each carrying a DISTINCT c09), a
    live calculate of the M100/2024 annual draws both retenciones-credit relations
    through the enrolled ``RelationPrefillSourceResolver``: casilla 0596 equals the
    summed four M111 c28 quarters and casilla 0597 equals the summed four M123 c09
    quarters. The M130/M131 pagos legs are seeded only so the 0604 formula resolves
    and the calculate reaches the retenciones casillas.
    """
    obs_repo = CalculationObservationRepository()
    expected_trabajo = _assert_distinct_positive(_M111_C28_BY_PERIOD)
    expected_capital_mobiliario = _assert_distinct_positive(_M123_C09_BY_PERIOD)
    # The two expected totals are mutually distinct, so a cross-wired fold
    # (M111 summed into 0597, or vice versa) would red the per-casilla checks.
    assert expected_trabajo != expected_capital_mobiliario

    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="111",
            period=period,
            casilla_id=_M111_RETENCIONES_OUTPUT,
            value=_M111_C28_BY_PERIOD[period],
        )
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="123",
            period=period,
            casilla_id=_M123_RETENCIONES_OUTPUT,
            value=_M123_C09_BY_PERIOD[period],
        )
    _seed_pagos_quarters(obs_repo=obs_repo)

    result = _calculate_m100_annual(secure_objects)

    values = result.revision.casilla_values
    casilla_0596 = Decimal(values[_M100_TRABAJO_CASILLA])
    casilla_0597 = Decimal(values[_M100_CAPITAL_MOBILIARIO_CASILLA])
    assert casilla_0596 == expected_trabajo, (
        f"M100 {_M100_TRABAJO_CASILLA} must fold the four M111 c28 quarters "
        f"(sum {expected_trabajo}); got {casilla_0596}"
    )
    assert casilla_0597 == expected_capital_mobiliario, (
        f"M100 {_M100_CAPITAL_MOBILIARIO_CASILLA} must fold the four M123 c09 quarters "
        f"(sum {expected_capital_mobiliario}); got {casilla_0597}"
    )

    # relation_prefill is a CLAIMED source (resolver enrolled): no
    # unhandled_binding_source advisory names it.
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics), (
        f"relation_prefill must be a claimed source with no diagnostics; got {result.source_diagnostics}"
    )
    assert not any(
        diag.reason == "unhandled_binding_source" and diag.source_kind == _RELATION_PREFILL_SOURCE
        for diag in result.source_diagnostics
    )
