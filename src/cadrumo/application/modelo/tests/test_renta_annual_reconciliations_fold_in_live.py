"""M180/M190/M193 renta annual reconciliations fold LIVE.

Three cross-modelo annual reconciliations are proven end-to-end on the
LIVE operator calculate path
(:func:`calculate_modelo_revision_from_bucket_aggregation_with_diagnostics`).
Each annual summary modelo derives its declarante totals by folding the four
quarterly source filings (1T-4T) through the enrolled
:class:`RelationPrefillSourceResolver`:

* **Modelo 180** (revision ``2023-y-siguientes``) folds **Modelo 115** quarterly
  retención-de-alquileres monetary filings. Source casilla ids ``02`` (base)
  and ``03`` (retenciones) feed ``decl.base-total`` /
  ``decl.retenciones-total`` via ``copy``-from-relation formulas.
  ``decl.total-perceptores`` comes from the dedicated per-perceptor retención
  store, because quarterly perceptor counts double-count recurring perceptors.
* **Modelo 190** (revision ``2024-y-siguientes``) folds **Modelo 111** quarterly
  retención-rendimientos-del-trabajo monetary filings. Nine importe casilla ids
  sum into ``decl.percepciones-total``, output ``28`` copies into
  ``decl.retenciones-total``, and ``decl.total-percepciones`` comes from the
  withholding detalle source because quarterly perceptor counts double-count
  recurring percepciones.
* **Modelo 193** (revision ``2024-y-siguientes``) folds **Modelo 123** quarterly
  retención-capital-mobiliario monetary filings. Source casilla ids ``06``
  (base), ``09`` (retenciones) feed the monetary declarante casillas; the
  perceptor count comes from the dedicated per-perceptor retención store.

Each source quarter is seeded as a filed observation through the production
observation-persistence API
(:meth:`CalculationObservationRepository.save_observation`, the same write path
the local-file carry flow uses), stamped with the non-official ``app_filing``
source_kind, over a real encrypted-SQLite object store
(:class:`SecureObjectRepository` + :class:`EphemeralMasterKeyProvider` via
:func:`isolated_runtime_profile`). No mocks, stubs, skips, or xfail.

The relation aggregation assertions (annual monetary casilla == sum of the four
DISTINCT seeded quarterly inputs) are fold-WIRING invariants, not tautologies: the seeded
per-quarter values are distinct non-equal known Decimals, so an off-by-quarter,
a single-quarter copy, a silent blank, or a coincidental sum cannot satisfy the
assertion. The test does not recompute any registry IRPF formula — it proves
the enrolled relation resolver wires the four prior periodic filings through to
each annual monetary declarante casilla. Perceptor counts are asserted against
real persisted per-perceptor records instead.

Both M190 and M193 additionally declare ``source = "withholding"`` per-perceptor
detalle bindings (the tipo-2 row producers). The live withholding resolver is
enrolled; when the dedicated per-perceptor-clave store is empty, it materialises
an explicit zero and emits a ``source_issue`` diagnostic naming ``withholding``.
That diagnostic is EXPECTED and is asserted present alongside the clean relation
fold — M190/M193 are deliberately NOT the empty-diagnostics shape that M180 has
after its retenciones_aggregation and monetary relations are both satisfied.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from ....core.aggregation import AggregationCaptureKind, BindingSourceKind, RetencionClave
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.withholding_bindings import WithholdingObservation
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.env_scope import ready_clave_settings
from ....tests.profile_capsule import load_test_profile_record, replace_test_profile_record, seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import (
    PercepcionObservationRepository,
    RetencionObservation,
    RetencionObservationRepository,
    RetencionScheme,
)
from ...calculations.observations_repository import CalculationObservationRepository
from .._revision_persistence import persist_filed_revision
from ..calculation_actions import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ..filed_revision_observation import APP_FILING_SOURCE_KIND
from ..verification_actions import verify_modelo_revision
from ..work_lifecycle import create_work_unit
from ._fold_in_assertions_support import _assert_distinct_positive

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "00000000-0000-4000-8000-000000000190"
_PROFILE_LABEL = "Renta annual reconciliation profile"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_YEAR = 2024
_ANNUAL_PERIOD = "0A"
_QUARTERS: tuple[str, ...] = ("1T", "2T", "3T", "4T")
_RELATION_PREFILL_SOURCE = "relation_prefill"
_WITHHOLDING_SOURCE = "withholding"

# Declarante summary casilla ids shared by the M180 / M193 copy-from-relation
# reconciliations (M180 2023 and M193 2024 both expose these three).
_DECL_PERCEPTORES: CasillaId = validated_casilla_id("decl.total-perceptores", surface="_DECL_PERCEPTORES")
_DECL_BASE: CasillaId = validated_casilla_id("decl.base-total", surface="_DECL_BASE")
_DECL_RETENCIONES: CasillaId = validated_casilla_id("decl.retenciones-total", surface="_DECL_RETENCIONES")
# M190 declarante summary casilla ids (percepciones rather than perceptores).
_DECL_PERCEPCIONES_COUNT: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_DECL_PERCEPCIONES_COUNT",
)
_DECL_PERCEPCIONES_AMOUNT: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_DECL_PERCEPCIONES_AMOUNT",
)
_M115_PERCEPTORES_OUTPUT: CasillaId = validated_casilla_id("01", surface="_M115_PERCEPTORES_OUTPUT")
_M115_BASE_OUTPUT: CasillaId = validated_casilla_id("02", surface="_M115_BASE_OUTPUT")
_M115_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("03", surface="_M115_RETENCIONES_OUTPUT")
_M123_PERCEPTORES_OUTPUT: CasillaId = validated_casilla_id("03", surface="_M123_PERCEPTORES_OUTPUT")
_M123_BASE_OUTPUT: CasillaId = validated_casilla_id("06", surface="_M123_BASE_OUTPUT")
_M123_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("09", surface="_M123_RETENCIONES_OUTPUT")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_PROFILE_LABEL) as profile:
        _seed_ready_profile()
        yield profile.repository


def _seed_ready_profile() -> None:
    """Persist a filing-ready withholding-operator profile for annual summaries."""
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value="Test"),
                UserProfileFact(path="identity.surnames", value="Operator"),
                UserProfileFact(path="activities.description", value="withholding operator activity"),
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
                # Modelo 111 refuses a defaulted colegio-concertado declaration: the fichero
                # carries the row as filer data, so it must be stated rather than assumed.
                # False is the truthful value for this natural-person filer.
                UserProfileFact(path="withholding.colegio_concertado", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _seed_quarterly_filing(
    *,
    obs_repo: CalculationObservationRepository,
    source_modelo: str,
    period: str,
    casilla_values: dict[CasillaId, Decimal],
) -> None:
    """Persist one filed source-modelo quarter carrying every needed source casilla id.

    The relation resolver requires exactly ONE observation per
    ``(source_modelo, filing_year, period)`` carrying every source casilla id the
    annual relations consume, so each quarter is written as a single
    :class:`RegistryModeloObservation` whose ``observations`` tuple covers all
    outputs. Persisted through the production
    :meth:`CalculationObservationRepository.save_observation` write path with the
    non-official ``app_filing`` source_kind.
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
                    casilla_values=casilla_values,
                ),
            ),
            source_kind=APP_FILING_SOURCE_KIND,
            captured_at=_T0,
        )
    )


def _calculate_annual(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
) -> BucketAggregationCalculationResult:
    """Run the live annual calculate for ``modelo`` / ``_YEAR`` / ``0A``.

    These annual summary modelos declare no ``profile`` bindings and no caller
    inputs other than the relation-folded values; the only bindings are the
    ``relation_prefill`` reconciliations (folded by the enrolled resolver from
    the seeded source store) and, for M190/M193, the enrolled ``withholding``
    detalle bindings. No ``binding_values`` are supplied so the live mesh is the
    sole value source.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot(modelo, filing_year=_YEAR, period=_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def _calculate_periodic(
    secure_objects: SecureObjectRepository,
    *,
    modelo: str,
    period: str,
) -> BucketAggregationCalculationResult:
    """Run the live periodic calculate for ``modelo`` / ``_YEAR`` / ``period``."""
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = bundled_authority().snapshot(modelo, filing_year=_YEAR, period=period)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T1,
    )


def _assert_empty_withholding_store_source_issue(result: BucketAggregationCalculationResult, *, modelo: str) -> None:
    """Assert enrolled withholding resolver reports an empty detail store loudly."""
    assert not any(
        diag.source_kind == _WITHHOLDING_SOURCE and diag.reason == "unhandled_binding_source"
        for diag in result.source_diagnostics
    ), (
        f"M{modelo} withholding is enrolled and must not surface as unhandled; "
        f"source_diagnostics: {result.source_diagnostics}"
    )
    withholding_issues = [
        diag
        for diag in result.source_diagnostics
        if diag.source_kind == _WITHHOLDING_SOURCE and diag.reason == "source_issue"
    ]
    assert withholding_issues, (
        f"M{modelo} must surface a 'source_issue' advisory when the enrolled withholding "
        f"resolver finds no per-perceptor-clave observations; source_diagnostics: {result.source_diagnostics}"
    )
    assert all(diag.resolver_id == _WITHHOLDING_SOURCE for diag in withholding_issues)
    assert all(diag.binding_id is None for diag in withholding_issues)
    assert all("zero" in diag.message for diag in withholding_issues)


# ---------------------------------------------------------------------------
# Modelo 180 <- Modelo 115 monetary relations + retenciones distinct count.
# ---------------------------------------------------------------------------

# Four DISTINCT non-equal quarterly values per M115 monetary output. M115 c01 is
# still seeded as source evidence, but M180 no longer consumes it for the annual
# perceptor count.
_M115_C01_PERCEPTORES = {"1T": Decimal("1"), "2T": Decimal("2"), "3T": Decimal("3"), "4T": Decimal("4")}
_M115_C02_BASE = {
    "1T": Decimal("1000.00"),
    "2T": Decimal("2500.50"),
    "3T": Decimal("750.25"),
    "4T": Decimal("3000.00"),
}
_M115_C03_RETENCIONES = {
    "1T": Decimal("190.00"),
    "2T": Decimal("475.10"),
    "3T": Decimal("142.55"),
    "4T": Decimal("570.00"),
}
_M180_RETENCION_PERCEPTOR_NIFS: tuple[str, ...] = ("11111111H", "22222222J")


def _retencion_observation(nif: str, *, scheme: RetencionScheme, source_prefix: str) -> RetencionObservation:
    return RetencionObservation(
        source_kind=BindingSourceKind.LEDGER_TRANSACTION,
        source_object_id=f"{source_prefix}-{nif}",
        perceptor_nif=nif,
        perceptor_name="Perceptor Ejemplo",
        scheme=scheme,
        taxable_base=Decimal("1000.00"),
        retencion_amount=Decimal("190.00"),
        accrued_on=f"{_YEAR}-03-15",
    )


def _seed_retencion_perceptors(
    *,
    modelo: str,
    scheme: RetencionScheme,
    nifs: tuple[str, ...],
) -> Decimal:
    RetencionObservationRepository().replace_observations(
        modelo=modelo,
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        observations=[_retencion_observation(nif, scheme=scheme, source_prefix=f"retencion-{modelo}") for nif in nifs],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    return Decimal(len(set(nifs)))


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL)


def test_m180_folds_in_four_m115_quarters_on_live_calculate(secure_objects: SecureObjectRepository) -> None:
    """E2E: four filed M115 quarters fold into the M180 annual declarante totals.

    The M180 monetary declarante casillas are ``copy`` formulas over
    annual_summary relations whose ``sum`` aggregation folds the four seeded M115
    quarters. The perceptor count is resolved through ``retenciones_aggregation``.
    With both sources supplied, the live resolution is clean.
    """
    obs_repo = CalculationObservationRepository()
    expected_base = _assert_distinct_positive(_M115_C02_BASE)
    expected_retenciones = _assert_distinct_positive(_M115_C03_RETENCIONES)
    expected_perceptores = _seed_retencion_perceptors(
        modelo="180",
        scheme=RetencionScheme.URBAN_RENTAL,
        nifs=_M180_RETENCION_PERCEPTOR_NIFS,
    )
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="115",
            period=period,
            casilla_values={
                _M115_PERCEPTORES_OUTPUT: _M115_C01_PERCEPTORES[period],
                _M115_BASE_OUTPUT: _M115_C02_BASE[period],
                _M115_RETENCIONES_OUTPUT: _M115_C03_RETENCIONES[period],
            },
        )

    result = _calculate_annual(secure_objects, modelo="180")

    values = result.revision.casilla_values
    assert Decimal(values[_DECL_PERCEPTORES]) == expected_perceptores, (
        f"M180 {_DECL_PERCEPTORES} must use the persisted distinct perceptor count "
        f"({expected_perceptores}); got {values[_DECL_PERCEPTORES]}"
    )
    assert Decimal(values[_DECL_BASE]) == expected_base, (
        f"M180 {_DECL_BASE} must fold the four M115 c02 quarters (sum {expected_base}); got {values[_DECL_BASE]}"
    )
    assert Decimal(values[_DECL_RETENCIONES]) == expected_retenciones, (
        f"M180 {_DECL_RETENCIONES} must fold the four M115 c03 quarters "
        f"(sum {expected_retenciones}); got {values[_DECL_RETENCIONES]}"
    )

    # relation_prefill is a claimed source: no diagnostic names it.
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    # M180 has no withholding detalle bindings, so the whole resolution is clean.
    assert result.source_diagnostics == (), f"M180 source_diagnostics must be clean; got {result.source_diagnostics}"


# ---------------------------------------------------------------------------
# Modelo 190 <- Modelo 111 (importes / retenciones),
# relation fold + enrolled withholding detalle advisory.
# ---------------------------------------------------------------------------

# The nine importe source casilla ids (M111 c02,05,08,11,14,17,20,23,26) sum into
# decl.percepciones-total.
_M190_IMPORTE_OUTPUTS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(value, surface="_M190_IMPORTE_OUTPUTS")
    for value in ("02", "05", "08", "11", "14", "17", "20", "23", "26")
)
# Output 28 (M111 retenciones total) copies into decl.retenciones-total via the
# retenciones relation (still summed over the four quarters per the binding).
_M190_RETENCIONES_OUTPUT: CasillaId = validated_casilla_id("28", surface="_M190_RETENCIONES_OUTPUT")


def _m190_seed_value(output: CasillaId, period: str) -> Decimal:
    """Return a distinct seed for one M111 output in one quarter.

    Encodes the output index and the quarter index into the integer/decimal so
    every (output, quarter) pair carries a unique value — a wrong-output or
    wrong-quarter fold cannot reproduce the per-casilla expected sum.
    """
    quarter_index = _QUARTERS.index(period) + 1
    # Monetary relation inputs are distinct per (output, quarter); the leading
    # digit is the output index and the trailing the quarter index.
    base = (int(output) * 100) + quarter_index
    return Decimal(base) + Decimal("0.50")


def _seed_m190_withholding_detail() -> None:
    PercepcionObservationRepository().replace_observations(
        modelo="190",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _ANNUAL_PERIOD),
        observations=[
            WithholdingObservation(
                source_id="m190-professional-row-001",
                perceptor_tax_id="12345678Z",
                perceptor_legal_name="Profesional Ejemplo",
                transaction_date=date(_YEAR, 3, 15),
                clave=RetencionClave.G,
                subclave="01",
                percibido_dinerario=Decimal("1000.00"),
                retencion_practicada=Decimal("150.00"),
            ),
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )


def _seed_m111_quarterly_m190_evidence() -> None:
    obs_repo = CalculationObservationRepository()
    all_outputs = (*_M190_IMPORTE_OUTPUTS, _M190_RETENCIONES_OUTPUT)
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="111",
            period=period,
            casilla_values={output: _m190_seed_value(output, period) for output in all_outputs},
        )


def _attest_m111_no_retenciones_periods(
    secure_objects: SecureObjectRepository,
    *,
    periods: tuple[str, ...],
) -> None:
    record = load_test_profile_record(_BUCKET_ID)
    replace_test_profile_record(
        record.model_copy(
            update={
                "facts": (
                    *record.facts,
                    UserProfileFact(
                        path="withholding.modelo_111_no_retenciones_periods",
                        value=",".join(f"{_YEAR}:{period}" for period in periods),
                    ),
                ),
                "updated_at": _T1,
            },
        ),
    )


def _seed_and_file_m111_1t(secure_objects: SecureObjectRepository) -> BucketAggregationCalculationResult:
    RetencionObservationRepository().replace_observations(
        modelo="111",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "1T"),
        observations=[
            RetencionObservation(
                source_kind=BindingSourceKind.LEDGER_TRANSACTION,
                source_object_id="m111-1t-payroll-001",
                perceptor_nif="12345678Z",
                perceptor_name="Empleado Ejemplo",
                scheme=RetencionScheme.WORK_INCOME,
                taxable_base=Decimal("1000.00"),
                retencion_amount=Decimal("150.00"),
                accrued_on=f"{_YEAR}-03-15",
            ),
        ],
        source_kind=AggregationCaptureKind.AGGREGATE_PULL,
    )
    result = _calculate_periodic(secure_objects, modelo="111", period="1T")
    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="test-operator",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings("12345678Z"),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        filing_repository=ModeloRecordCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        verification_repository=VerificationReportCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        clock=_T1,
    )
    assert report.granted_verificado_completo is True, report.findings
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID)
    work_units = wu_repo.load()
    work_unit = work_units.get(result.revision.work_unit_id)
    assert work_unit is not None
    verified_revision = cr_repo.load().get(result.revision.calculation_revision_id)
    assert verified_revision is not None
    persist_filed_revision(
        target=verified_revision,
        work_unit=work_unit,
        work_units=work_units,
        notes=None,
        actor="test-operator",
        now=_T1,
        calculation_repository=cr_repo,
        filing_repository=ModeloRecordCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        work_unit_repository=wu_repo,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
        taxpayer_nif=_workflow_profile().tax_id,
    )
    return result


def test_m190_folds_in_four_m111_quarters_with_withholding_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: four filed M111 quarters fold into M190 monetary totals; withholding advisory present.

    The nine importe relations sum into ``decl.percepciones-total`` and the
    retenciones relation (output ``28``) into ``decl.retenciones-total``. The
    annual count ``decl.total-percepciones`` is withholding-backed; with an empty
    detail store the enrolled resolver materialises an explicit zero and emits a
    ``source_issue`` advisory.
    """
    obs_repo = CalculationObservationRepository()
    all_outputs = (*_M190_IMPORTE_OUTPUTS, _M190_RETENCIONES_OUTPUT)
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="111",
            period=period,
            casilla_values={output: _m190_seed_value(output, period) for output in all_outputs},
        )

    expected_percepciones_amount = sum(
        (_m190_seed_value(output, period) for output in _M190_IMPORTE_OUTPUTS for period in _QUARTERS),
        Decimal("0"),
    )
    expected_retenciones = sum(
        (_m190_seed_value(_M190_RETENCIONES_OUTPUT, period) for period in _QUARTERS),
        Decimal("0"),
    )
    # Sanity: the monetary expected totals are strictly positive and distinct, so
    # a cross-wired fold would red the per-casilla assertions below.
    assert expected_percepciones_amount > Decimal("0")
    assert expected_retenciones > Decimal("0")
    assert expected_percepciones_amount != expected_retenciones

    result = _calculate_annual(secure_objects, modelo="190")

    values = result.revision.casilla_values
    assert Decimal(values[_DECL_PERCEPCIONES_COUNT]) == Decimal("0"), (
        f"M190 {_DECL_PERCEPCIONES_COUNT} must come from withholding detalle and materialise zero "
        f"when the detail store is empty; got {values[_DECL_PERCEPCIONES_COUNT]}"
    )
    assert Decimal(values[_DECL_PERCEPCIONES_AMOUNT]) == expected_percepciones_amount, (
        f"M190 {_DECL_PERCEPCIONES_AMOUNT} must fold the nine importe outputs over four quarters "
        f"(sum {expected_percepciones_amount}); got {values[_DECL_PERCEPCIONES_AMOUNT]}"
    )
    assert Decimal(values[_DECL_RETENCIONES]) == expected_retenciones, (
        f"M190 {_DECL_RETENCIONES} must fold the retenciones output (28) over four quarters "
        f"(sum {expected_retenciones}); got {values[_DECL_RETENCIONES]}"
    )

    # The relation fold is clean (claimed source, no diagnostic names it)...
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    _assert_empty_withholding_store_source_issue(result, modelo="190")


def test_m190_verify_accepts_observation_backed_m111_cross_period_evidence(
    secure_objects: SecureObjectRepository,
) -> None:
    """M190 verify recognizes observed M111 values and names the missing filing-grade quarterly evidence."""
    _seed_m111_quarterly_m190_evidence()
    _seed_m190_withholding_detail()

    result = _calculate_annual(secure_objects, modelo="190")
    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="test-operator",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings("12345678Z"),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        filing_repository=ModeloRecordCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        verification_repository=VerificationReportCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        clock=_T1,
    )

    assert Decimal(result.revision.casilla_values[_DECL_PERCEPCIONES_COUNT]) == Decimal("1")
    assert report.granted_verificado_completo is False
    cross_period_findings = tuple(
        finding
        for finding in report.findings
        if finding.kind.value == "cross_period_dependency_unclean" and finding.severity.value == "blocking"
    )
    assert cross_period_findings, report.findings
    m111_findings = tuple(
        finding
        for finding in cross_period_findings
        if finding.message_facts.get("source_modelo") == "111"
        and finding.message_facts.get("source_filing_year") == 2024
    )
    assert m111_findings, cross_period_findings
    assert all(
        "missing_current_filing_record" in str(finding.message_facts["blocker_codes"]).split("|")
        for finding in m111_findings
    )
    assert not any(
        "missing_observation" in str(finding.message_facts["blocker_codes"]).split("|") for finding in m111_findings
    )
    assert not any(
        "missing_observed_casilla" in str(finding.message_facts["blocker_codes"]).split("|")
        for finding in m111_findings
    )


def test_m190_verify_accepts_filed_1t_m111_and_attested_no_obligation_zero_quarters(
    secure_objects: SecureObjectRepository,
) -> None:
    """M190 verify accepts a clean filed M111 1T plus explicit 2T-4T no-obligation evidence."""
    m111_result = _seed_and_file_m111_1t(secure_objects)
    _attest_m111_no_retenciones_periods(secure_objects, periods=("2T", "3T", "4T"))
    _seed_m190_withholding_detail()

    result = _calculate_annual(secure_objects, modelo="190")
    expected_percepciones_amount = sum(
        (Decimal(m111_result.revision.casilla_values[output]) for output in _M190_IMPORTE_OUTPUTS),
        Decimal("0"),
    )
    expected_retenciones = Decimal(m111_result.revision.casilla_values[_M190_RETENCIONES_OUTPUT])
    assert Decimal(result.revision.casilla_values[_DECL_PERCEPCIONES_AMOUNT]) == expected_percepciones_amount
    assert Decimal(result.revision.casilla_values[_DECL_RETENCIONES]) == expected_retenciones
    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)

    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="test-operator",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings("12345678Z"),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        filing_repository=ModeloRecordCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        verification_repository=VerificationReportCatalogueRepository(objects=secure_objects, bucket_id=_BUCKET_ID),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        clock=_T1,
    )

    assert report.granted_verificado_completo is True, report.findings
    blocking_cross_period = tuple(
        finding
        for finding in report.findings
        if finding.kind.value == "cross_period_dependency_unclean" and finding.severity.value == "blocking"
    )
    assert not blocking_cross_period
    m111_advisories = tuple(
        finding
        for finding in report.findings
        if finding.message_locale_key == "application.modelo.findings.cross_period_m111_no_retenciones"
    )
    assert {finding.message_facts["source_period"] for finding in m111_advisories} == {"2T", "3T", "4T"}
    assert not any(
        finding.message_facts.get("source_modelo") == "111"
        and "missing_current_filing_record" in str(finding.message_facts.get("blocker_codes", "")).split("|")
        for finding in report.findings
    )


# ---------------------------------------------------------------------------
# Modelo 193 <- Modelo 123 (perceptores / base / retenciones),
# relation fold + enrolled withholding detalle advisory.
# ---------------------------------------------------------------------------

# Four DISTINCT non-equal quarterly values per M123 monetary output. M123 c03 is
# still seeded as source evidence, but M193 no longer consumes it for the annual
# perceptor count.
_M123_C03_PERCEPTORES = {"1T": Decimal("5"), "2T": Decimal("7"), "3T": Decimal("11"), "4T": Decimal("13")}
_M123_C06_BASE = {
    "1T": Decimal("4000.00"),
    "2T": Decimal("1250.75"),
    "3T": Decimal("9000.20"),
    "4T": Decimal("333.05"),
}
_M123_C09_RETENCIONES = {
    "1T": Decimal("760.00"),
    "2T": Decimal("237.64"),
    "3T": Decimal("1710.04"),
    "4T": Decimal("63.28"),
}
_M193_RETENCION_PERCEPTOR_NIFS: tuple[str, ...] = ("33333333P", "44444444A", "55555555K")


def test_m193_folds_in_four_m123_quarters_with_withholding_advisory(
    secure_objects: SecureObjectRepository,
) -> None:
    """E2E: four filed M123 quarters fold into M193 annual totals; withholding advisory present.

    M193 monetary declarante casillas are ``copy`` formulas over annual_summary
    relations whose ``sum`` aggregation folds the four seeded M123 quarters
    (outputs ``06`` base and ``09`` retenciones). The perceptor count is resolved
    through ``retenciones_aggregation``. Because M193 also declares
    ``withholding`` tipo-2 detalle bindings, the enrolled withholding resolver
    emits a ``source_issue`` advisory when the detail store is empty.
    """
    obs_repo = CalculationObservationRepository()
    expected_base = _assert_distinct_positive(_M123_C06_BASE)
    expected_retenciones = _assert_distinct_positive(_M123_C09_RETENCIONES)
    expected_perceptores = _seed_retencion_perceptors(
        modelo="193",
        scheme=RetencionScheme.CAPITAL_INTEREST,
        nifs=_M193_RETENCION_PERCEPTOR_NIFS,
    )
    for period in _QUARTERS:
        _seed_quarterly_filing(
            obs_repo=obs_repo,
            source_modelo="123",
            period=period,
            casilla_values={
                _M123_PERCEPTORES_OUTPUT: _M123_C03_PERCEPTORES[period],
                _M123_BASE_OUTPUT: _M123_C06_BASE[period],
                _M123_RETENCIONES_OUTPUT: _M123_C09_RETENCIONES[period],
            },
        )

    result = _calculate_annual(secure_objects, modelo="193")

    values = result.revision.casilla_values
    assert Decimal(values[_DECL_PERCEPTORES]) == expected_perceptores, (
        f"M193 {_DECL_PERCEPTORES} must use the persisted distinct perceptor count "
        f"({expected_perceptores}); got {values[_DECL_PERCEPTORES]}"
    )
    assert Decimal(values[_DECL_BASE]) == expected_base, (
        f"M193 {_DECL_BASE} must fold the four M123 c06 quarters (sum {expected_base}); got {values[_DECL_BASE]}"
    )
    assert Decimal(values[_DECL_RETENCIONES]) == expected_retenciones, (
        f"M193 {_DECL_RETENCIONES} must fold the four M123 c09 quarters "
        f"(sum {expected_retenciones}); got {values[_DECL_RETENCIONES]}"
    )

    assert not any(diag.source_kind == _RELATION_PREFILL_SOURCE for diag in result.source_diagnostics)
    _assert_empty_withholding_store_source_issue(result, modelo="193")
