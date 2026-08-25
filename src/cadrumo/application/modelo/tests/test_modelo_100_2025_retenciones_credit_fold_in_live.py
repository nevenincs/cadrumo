"""M100/2025 retenciones-credit casillas fold in periodic withholding filings (LIVE path).

The annual IRPF declaration (Modelo 100) credits the withholdings already
practised during the year against the cuota. Two of those credit casillas are
genuine cross-modelo *retenciones-credit* folds: each is a ``bound`` casilla
whose ``relation_prefill`` binding sums a periodic source modelo's retenciones
output through the enrolled :class:`RelationPrefillSourceResolver`:

* casilla ``0596`` ("Por rendimientos del trabajo") binds
  ``renta-2025-modelo-111-retenciones-periodicas`` — ``source_modelo='111'``,
  ``source_casilla_id='28'`` (M111 "retenciones e ingresos a cuenta"), summed over
  the four quarters.
* casilla ``0597`` ("Por rendimientos del capital mobiliario") binds
  ``renta-2025-modelo-123-retenciones-periodicas`` — ``source_modelo='123'``,
  ``source_casilla_id='09'`` (M123 retenciones), summed over the four quarters.

This module proves both folds work end-to-end on the LIVE operator calculate
path (:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`)
for the **2025** revision: four filed M111 quarters fold into ``0596`` and four
filed M123 quarters fold into ``0597``. This is the 2025 port of the 2024
proof in ``test_modelo_100_retenciones_credit_fold_in_live``.

The M100/2025 ``0604`` ("Pagos fraccionados ingresados") casilla is *computed*
by a formula that references the M130 and M131 pagos-fraccionados relations
DIRECTLY, so the engine raises ``RegistryValidationError`` for any of those
relations it cannot resolve. The full-snapshot live calculate therefore also
requires the M130/M131 pagos legs to be present; this persona seeds them
(M130 as four distinct quarters, M131 as a true zero) so the calculate reaches
the retenciones casillas. The pagos values are NOT what this module asserts —
they only keep the engine from raising before ``0596`` / ``0597`` resolve.

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

Legal grounding: LIRPF art. 99 + RIRPF art. 108 (withholding source filings) +
Orden HAC/277/2026 art. 3 (M100/2025 form approval, BOE-A-2026-7041).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import AggregationCaptureKind, BindingSourceKind, CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ...aggregation import (
    RetencionObservation,
    RetencionObservationRepository,
    RetencionScheme,
)
from ...calculations import CalculationObservationRepository
from .._calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from .._work_lifecycle import create_work_unit
from .._filed_revision_observation import APP_FILING_SOURCE_KIND
from ._fold_in_assertions_support import _assert_distinct_positive

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "2fa3285a-d72e-4f86-9a1c-75c98d1f2ede"
_T0 = datetime(2026, 6, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 6, 10, 11, 0, tzinfo=UTC)
_YEAR = 2025
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_RELATION_PREFILL_SOURCE = "relation_prefill"
_OPTIONAL_PAYEE_RETENCIONES_BINDINGS: frozenset[BindingId] = frozenset(
    {"renta-2025-certificado-trabajo-retenciones"},
)

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
# values for 2025. Distinctness makes the annual fold unmistakable: an
# off-by-one-quarter or coincidental sum cannot satisfy the assertion.
_M111_C28_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("155.00"),
    "2T": Decimal("320.75"),
    "3T": Decimal("88.50"),
    "4T": Decimal("445.25"),
}
# Four DISTINCT non-equal quarterly M123 c09 retenciones-capital-mobiliario
# values, deliberately disjoint from the M111 totals so a cross-wired fold
# (M111 summed into 0597, etc.) would red the per-casilla assertions.
_M123_C09_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("15.60"),
    "2T": Decimal("72.30"),
    "3T": Decimal("8.40"),
    "4T": Decimal("51.70"),
}

# The 0604 pagos formula references the M130 and M131 pagos relations DIRECTLY;
# seeding them prevents the engine raising before the retenciones casillas resolve.
# These values are NOT asserted here — they only let the engine reach 0596 / 0597.
_M130_C19_BY_PERIOD: dict[str, Decimal] = {
    "1T": Decimal("120.00"),
    "2T": Decimal("280.00"),
    "3T": Decimal("95.50"),
    "4T": Decimal("350.00"),
}
_M130_PAGOS_OUTPUT: CasillaId = validated_casilla_id("19", surface="_M130_PAGOS_OUTPUT")
_M131_PAGOS_OUTPUT: CasillaId = validated_casilla_id("15", surface="_M131_PAGOS_OUTPUT")


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
    obs_repo.save(
        obs_repo.prepare_observation_envelope(
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
    )


def _seed_pagos_quarters(*, obs_repo: CalculationObservationRepository) -> None:
    """Seed the M130 (four distinct quarters) and M131 (true zero) pagos legs.

    The M100/2025 0604 formula references both pagos relations directly; the
    engine raises for any it cannot resolve. Seeding them keeps the
    full-snapshot calculate from raising before the retenciones casillas
    0596 / 0597 resolve.  These values are not asserted by this module.
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
    CalculationObservationRepository(objects=secure_objects).save(
        CalculationObservationRepository(objects=secure_objects).prepare_observation_envelope(
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
    )


def _seed_taxpayer_unit_profile(secure_objects: SecureObjectRepository) -> None:
    """Seed a single-taxpayer ``UserProfileRecord`` covering M100/2025 profile bindings.

    The M100/2025 annual revision declares ``source = "profile"`` bindings (the
    taxpayer birth date, CCAA, declaration type, sex, marital status, marriage
    indicators, and the family/descendants counts). Without them the engine
    refuses the bound casillas that consume them before it ever reaches the
    retenciones casillas. The profile is the substrate of record, so the live
    source mesh's profile resolver auto-fills these — no profile fact is
    hand-fed through the caller channel.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="Test"),
            UserProfileFact(path="identity.surnames", value="Operator"),
            UserProfileFact(path="activities.description", value="economic activity"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
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
            UserProfileFact(path="renta_filing.declaration_type", value="1"),
            UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
            UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
        ),
        created_at=_T0,
        updated_at=_T0,
    )
    seed_test_profile_record(record)


def _non_relation_zero_bindings() -> dict[BindingId, Decimal]:
    """Zero-default M100/2025 bindings the caller must supply (manual_input and previous_filing).

    The annual M100/2025 revision binds casillas via several source kinds.
    ``profile`` and ``relation_prefill`` sources are resolved by the live mesh
    automatically and MUST NOT appear in ``binding_values`` (the lock rejects
    them, and ``relation_prefill`` must be left unset so the enrolled resolver
    folds from the seeded store).  Ledger sources (``ledger_renta_gastos_estimacion_directa_aggregation``,
    etc.) are bucket-aggregation-locked — the engine rejects caller overrides of
    those too.  What remains after excluding all resolved/locked sources is the
    set the caller must supply: ``manual_input`` (Anexo-C carry) and
    ``previous_filing`` (cross-period balance carry).  Both are zero here because
    this persona has no prior activity.
    """
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_ANNUAL_PERIOD)
    # Sources the live mesh resolves automatically or that are bucket-locked.
    # Passing any of these in binding_values triggers ModeloAggregationBindingError.
    _AUTO_RESOLVED = frozenset(
        {
            "profile",
            _RELATION_PREFILL_SOURCE,
            "ledger_renta_gastos_estimacion_directa_aggregation",
            "ledger_renta_income_aggregation",
            "ledger_iva_aggregation",
            "ledger_oss_aggregation",
            "collectible_invoice",
            "payable_invoice",
        },
    )
    return {
        binding.id: Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.id not in _OPTIONAL_PAYEE_RETENCIONES_BINDINGS
        if binding.source not in _AUTO_RESOLVED
    }


def _calculate_m100_annual(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    """Run the live M100/2025/0A calculate over the seeded bucket.

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


def test_m100_2025_retenciones_credits_fold_in_periodic_filings_on_live_calculate(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E/2025: four filed M111 quarters fold into 0596 and four M123 quarters into 0597.

    With four M111/2025 quarters recorded as filed observations (each carrying a
    DISTINCT c28) and four M123/2025 quarters (each carrying a DISTINCT c09), a
    live calculate of the M100/2025 annual draws both retenciones-credit relations
    through the enrolled ``RelationPrefillSourceResolver``: casilla 0596 equals the
    summed four M111 c28 quarters and casilla 0597 equals the summed four M123 c09
    quarters. The M130/M131 pagos legs are seeded only so the 0604 formula resolves
    and the calculate reaches the retenciones casillas.

    Legal grounding: LIRPF art. 99 + RIRPF art. 108 + Orden HAC/277/2026 art. 3.
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
        f"M100/2025 {_M100_TRABAJO_CASILLA} must fold the four M111/2025 c28 quarters "
        f"(sum {expected_trabajo}); got {casilla_0596}"
    )
    assert casilla_0597 == expected_capital_mobiliario, (
        f"M100/2025 {_M100_CAPITAL_MOBILIARIO_CASILLA} must fold the four M123/2025 c09 quarters "
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


# Four DISTINCT non-equal administrador (clave E, art. 101.2) quarters. Each
# withheld amount is the fixed 35 % general rate of a distinct base, so no
# rate-mismatch advisory fires and the produced M111 c28 equals the withheld
# amount. Distinctness makes the annual 0596 fold unmistakable.
_M111_ADMINISTRADOR_BY_PERIOD: dict[str, tuple[Decimal, Decimal]] = {
    "1T": (Decimal("2000.00"), Decimal("700.00")),  # 2000.00 * 0.35
    "2T": (Decimal("3200.00"), Decimal("1120.00")),  # 3200.00 * 0.35
    "3T": (Decimal("1500.00"), Decimal("525.00")),  # 1500.00 * 0.35
    "4T": (Decimal("4400.00"), Decimal("1540.00")),  # 4400.00 * 0.35
}


def _calculate_m111_administrador_quarter(
    secure_objects: SecureObjectRepository,
    *,
    period_code: str,
    taxable_base: Decimal,
    retencion_amount: Decimal,
) -> Decimal:
    """Aggregate one administrador retención into M111 and return its c28 total.

    Seeds a single ``WORK_INCOME_DIRECTOR`` (clave E) retención observation for the
    quarter and runs the LIVE M111 calculate. The administrador retención folds into
    the single trabajo block (casillas 01/02/03) via the art. 101.2 binding selector,
    so c03 (trabajo retenciones) carries the withheld amount and the
    total-retenciones formula rolls it into c28. Returns the produced c28.
    """
    period = Period.from_year_and_code(_YEAR, period_code)
    RetencionObservationRepository().replace_observations(
        modelo="111",
        filing_year=_YEAR,
        period=period,
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id=f"administrador-{period_code}",
                perceptor_nif="87654321X",
                perceptor_name="Administrador Ejemplo",
                scheme=RetencionScheme.WORK_INCOME_DIRECTOR,
                taxable_base=taxable_base,
                retencion_amount=retencion_amount,
                accrued_on="2025-03-15",
            ),
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("111", filing_year=_YEAR, period=period_code)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="111",
        filing_year=_YEAR,
        period=period,
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(objects=secure_objects),
        clock=_T1,
    )
    values = result.revision.casilla_values
    # The administrador retención lands in the trabajo block, not the actividades block.
    assert Decimal(values["03"]) == retencion_amount, (
        f"M111 c03 (trabajo retenciones) must carry the administrador withholding {retencion_amount}; "
        f"got {values['03']}"
    )
    # A correct art. 101.2 35 % withholding raises no rate-mismatch advisory.
    assert not any(d.reason == "administrador_retencion_rate_mismatch" for d in result.source_diagnostics)
    return Decimal(values["28"])


def test_m100_2025_director_administrador_retencion_credits_into_trabajo_casilla(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E/2025: a director's suffered administrador retención credits M100 casilla 0596.

    This proves the full cross-modelo director credit chain end to end on the
    LIVE calculate path:

      administrador retención (``WORK_INCOME_DIRECTOR``, clave E)
        -> M111 casilla 03 (trabajo retenciones, via the art. 101.2 binding selector)
        -> M111 casilla 28 (total-retenciones formula)
        -> M100 casilla 0596 (retenciones por rendimientos del trabajo soportadas,
           relation_prefill fold summed over the four quarters).

    Unlike ``test_m100_2025_retenciones_credits_fold_in_periodic_filings_on_live_calculate``
    (which seeds M111 c28 directly), each quarter's c28 here is PRODUCED by a real M111
    aggregation of an administrador retención, so the test exercises the full director
    path rather than the fold alone. Administrador/consejero income is rendimiento del
    trabajo (LIRPF art. 17.2.e), so crediting it to 0596 ("Por rendimientos del trabajo")
    is the correct casilla.

    Non-tautological: the four withheld amounts are distinct art. 101.2 (35 %) values, so
    a silent blank, a single-quarter copy, or an off-by-quarter fold cannot reproduce the
    summed credit. No registry IRPF formula is recomputed.

    Legal grounding: LIRPF art. 101.2 (administrador fixed rate) + art. 99 / RIRPF art. 108
    (withholding source filings) + Orden HAC/277/2026 art. 3 (M100/2025 form approval).
    """
    obs_repo = CalculationObservationRepository()
    _seed_taxpayer_unit_profile(secure_objects)

    produced_c28: dict[str, Decimal] = {}
    for period_code in _QUARTERS:
        base, amount = _M111_ADMINISTRADOR_BY_PERIOD[period_code]
        c28 = _calculate_m111_administrador_quarter(
            secure_objects,
            period_code=period_code,
            taxable_base=base,
            retencion_amount=amount,
        )
        assert c28 == amount, f"M111/{period_code} c28 must equal the administrador withholding {amount}; got {c28}"
        produced_c28[period_code] = c28
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="111",
            period=period_code,
            casilla_id=_M111_RETENCIONES_OUTPUT,
            value=c28,
        )
    _seed_pagos_quarters(obs_repo=obs_repo)

    expected_credit = _assert_distinct_positive(produced_c28)

    result = _calculate_m100_annual(secure_objects)

    casilla_0596 = Decimal(result.revision.casilla_values[_M100_TRABAJO_CASILLA])
    assert casilla_0596 == expected_credit, (
        f"M100/2025 {_M100_TRABAJO_CASILLA} must credit the director's four administrador "
        f"retención quarters (sum {expected_credit}); got {casilla_0596}"
    )
