"""E2E vertical: real ledger → M130 1T-4T (computed) → M100 annual 0604.

This module closes the one joint the existing chain-spine tests leave unproven.
Three segments are each covered in isolation today:

* ledger transactions → M130 casilla 01 (``test_renta_income_aggregation``,
  repository-backed aggregation).
* M130 quarter-to-quarter carry via the ``previous_filing`` resolver
  (``test_modelo_130_carry_forward_continuity``, but with **manual** casilla
  01 inputs, not ledger-derived).
* M130 casilla 19 → M100 0604 fold-in
  (``test_modelo_100_pagos_fraccionados_fold_in_live``, but with **injected**
  c19 filed observations, not values the M130 calc actually computed).

None of them joins the three: no test drives *real persisted ledger
transactions* through the live bucket-aggregation calculate action
(:func:`calculate_modelo_revision_from_bucket_aggregation`) for four cumulative
quarters, files each quarter through the production observation-persistence path
(:func:`persist_filed_revision_observation`), and then proves the annual M100
0604 folds in the **engine-computed** quarterly casilla-19 values. That full
vertical — the autónomo's real yearly cadence — is what this test verifies.

Real-behaviour, real-adapter: real encrypted-SQLite secure store via
:class:`SecureObjectRepository` + ``isolated_runtime_profile``, the real registry
authority, the real calculation engine, the real ledger income aggregation
resolver, the real ``previous_filing`` carry resolver, and the real
``relation_prefill`` fold-in resolver. No mocks, stubs, skips, or xfail.

Non-tautology argument: the per-quarter casilla 19 values are **computed by the
engine** from the ledger-derived casilla 01 through the whole M130 formula chain
(01→03→04→07→12→14→17→19); the test never hand-recomputes any registry formula.
The two load-bearing assertions are *transport / wiring* invariants:

* each quarter's casilla 01 equals the cumulative-YTD sum of the **persisted
  ledger** income the operator never re-keyed (proving the full calculate action,
  not just the aggregator, draws c01 from the ledger); and
* the annual M100 0604 equals the **sum of the four engine-computed c19** the
  four M130 filings persisted (proving the cross-period fold transports those
  specific computed values, not coincidental ones — the four are distinct).

The 20% estimación-directa pago-fraccionado rate that drives c04 is fixed by RD
439/2007 art. 110.4 and grounded in the registry parameter; this test asserts
the *wiring*, leaving the rate's legal currency to the registry grounding gate.
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
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.invoices import InvoiceCatalogueRepository
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._calculation_revision import CalculationRevision
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations._observations_repository import CalculationObservationRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    calculate_modelo_revision_from_bucket_aggregation,
    create_work_unit,
    persist_filed_revision_observation,
    verify_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "bucket-e2e-ledger-130-100"
_YEAR = 2024
_T0 = datetime(2024, 1, 10, 10, 0, tzinfo=UTC)
_FILE_AT = datetime(2024, 4, 6, 12, 0, tzinfo=UTC)

_M130_REVISION = "2019-y-siguientes"
_M100_ANNUAL_PERIOD = "0A"
_M100_PAGOS_CASILLA = "0604"
_RELATION_PREFILL_SOURCE = "relation_prefill"

# Prior-year (2023) actividad-económica net income. M130's casilla-13 minoración
# reads ``irpf.previous_year_economic_activity_net_income`` — a previous_filing
# binding summing the prior annual M100's net-income casillas. The bucket
# previous_filing resolver HARD-RAISES once any prior observation exists and the
# prior-year M100 is absent, so the prior annual filing must be observed (the
# caller channel does not pre-empt the resolver). Set well above the minoración
# income ceiling so the minoración resolves to zero and each quarter's casilla 19
# is the clean incremental pago fraccionado — keeps the four computed c19 distinct
# and positive without this test depending on the minoración schedule.
_PRIOR_YEAR = _YEAR - 1
_PRIOR_YEAR_NET_INCOME = Decimal("50000")

# One coherent year of business income, booked one distinct transaction per
# quarter. Cumulative-YTD (RD 439/2007 art. 110.2) windows then make each
# quarter's casilla 01 the running sum: 1T=5000, 2T=8000, 3T=10000, 4T=14000.
_QUARTER_INCOME: dict[str, tuple[date, Decimal]] = {
    "1T": (date(_YEAR, 2, 15), Decimal("5000.00")),
    "2T": (date(_YEAR, 5, 20), Decimal("3000.00")),
    "3T": (date(_YEAR, 8, 10), Decimal("2000.00")),
    "4T": (date(_YEAR, 11, 5), Decimal("4000.00")),
}
_QUARTER_ORDER = ("1T", "2T", "3T", "4T")
_EXPECTED_CUMULATIVE_C01: dict[str, Decimal] = {
    "1T": Decimal("5000.00"),
    "2T": Decimal("8000.00"),
    "3T": Decimal("10000.00"),
    "4T": Decimal("14000.00"),
}

# M130 manual casillas (gastos / retenciones / agrarian / vivienda / prior
# autoliquidaciones). All zero for this pure-estimación-directa, no-retención
# persona so casilla 03 == casilla 01 and casilla 19 == casilla 12.
_M130_MANUAL_INPUTS: dict[str, Decimal] = {
    "02": Decimal("0"),
    "06": Decimal("0"),
    "08": Decimal("0"),
    "10": Decimal("0"),
    "16": Decimal("0"),
    "18": Decimal("0"),
}

# The M100 0604 formula sums BOTH the M130 and M131 pagos relations; this persona
# files no estimación-objetiva, so its four M131 c15 quarters are a true zero and
# fold as 0, leaving 0604 == the M130 sum.
_M131_SOURCE_OUTPUT = "15"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    """Yield the active profile's real encrypted-SQLite object repository."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _income_transaction(period: str) -> Transaction:
    value_date, amount = _QUARTER_INCOME[period]
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id=f"income-{period}",
                booked_date=value_date,
                value_date=value_date,
                amount=amount,
                currency="EUR",
                counterparty="Cliente SA",
                description=f"factura {period}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.CSV,
                    ingested_at=_T0,
                    provider_name="CSV provider",
                ),
                raw_fields={"Concepto": f"factura {period}"},
            ),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "purchase_invoice_evidence_id": None,
            "category_id": None,
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _T0,
            "classified_by": "manual",
        },
    )


def _persist_year_of_income(secure_objects: SecureObjectRepository) -> None:
    """Persist the four quarterly business-income transactions into the bucket."""
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    tx_repo.save(
        TransactionCatalogue.from_transactions(tuple(_income_transaction(period) for period in _QUARTER_ORDER)),
    )


def _calculate_and_file_m130_quarter(
    secure_objects: SecureObjectRepository,
    *,
    period: str,
) -> CalculationRevision:
    """Run the live bucket-aggregation M130 calc for one quarter and file it.

    Casilla 01 is drawn from the persisted ledger (cumulative YTD); casillas 05
    (pagos anteriores) and 15 (resultados negativos anteriores) auto-resolve from
    the prior filed quarters via the ``previous_filing`` resolver; the prior-year
    net-income minoración input is supplied through the caller channel. The
    computed revision is then persisted through the production filing-observation
    path so the next quarter (and the annual fold-in) can carry it.
    """
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="130",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period),
        revision_id=_M130_REVISION,
        repository=wu_repo,
        clock=_T0,
    )
    revision = calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        casilla_inputs=_M130_MANUAL_INPUTS,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T0,
    )
    persist_filed_revision_observation(
        revision=revision,
        work_unit=work_unit,
        repository=CalculationObservationRepository(objects=secure_objects),
        captured_at=_FILE_AT,
    )
    return revision


def _seed_m131_zero_quarters(secure_objects: SecureObjectRepository) -> None:
    """File the four M131/2024 c15 quarters as a true zero (no módulos activity)."""
    from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation

    obs_repo = CalculationObservationRepository(objects=secure_objects)
    for period in _QUARTER_ORDER:
        obs_repo.save_observation(
            RegistryModeloObservation(
                modelo="131",
                filing_year=_YEAR,
                period=period,
                observations=(CasillaObservation(casilla_id=_M131_SOURCE_OUTPUT, value=Decimal("0")),),
            ),
            source_kind="app_filing",
            captured_at=_FILE_AT,
        )


def _seed_prior_year_m100(secure_objects: SecureObjectRepository) -> None:
    """Observe the prior-year annual Renta (M100 2023) net-income casillas.

    Carries every prior-year casilla a 2024 ``previous_filing`` binding reads:
    M130's casilla-13 minoración sums M100 0224/1479/1553/1577 (net income in
    0224, the rest zero for a pure actividad-económica filer), and M100/2024's
    base-liquidable-negativa-general carry copies casilla 1391 (no prior BIN, so
    zero). Net income is set above the minoración ceiling so the minoración
    resolves to zero.
    """
    from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation

    CalculationObservationRepository(objects=secure_objects).save_observation(
        RegistryModeloObservation(
            modelo="100",
            filing_year=_PRIOR_YEAR,
            period=_M100_ANNUAL_PERIOD,
            observations=(
                CasillaObservation(casilla_id="0224", value=_PRIOR_YEAR_NET_INCOME),
                CasillaObservation(casilla_id="1479", value=Decimal("0")),
                CasillaObservation(casilla_id="1553", value=Decimal("0")),
                CasillaObservation(casilla_id="1577", value=Decimal("0")),
                CasillaObservation(casilla_id="1391", value=Decimal("0")),
            ),
        ),
        source_kind="app_filing",
        captured_at=_FILE_AT,
    )


def _seed_taxpayer_profile() -> None:
    """Seed the single-taxpayer profile M100's profile-sourced bindings consume."""
    # display_name MUST equal the manifest label isolated_runtime_profile created
    # ("Test runtime profile") — ProfileAggregate._validate_cross_store_agreement
    # rejects a label/display_name mismatch as a torn-rename inconsistency.
    record = UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Test runtime profile",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
            UserProfileFact(path="renta_taxpayer.sex", value="varon"),
            UserProfileFact(path="renta_taxpayer.marital_status", value="soltero"),
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
    UserProfileLifecycleRepository(bucket_id=_BUCKET_ID).save(record)


def _m100_non_relation_zero_bindings() -> dict[str, Decimal]:
    """Zero-default every M100/2024 binding that is neither profile- nor relation-sourced."""
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    return {
        str(binding.id): Decimal("0")
        for binding in snapshot.revision.bindings
        if binding.source not in ("profile", _RELATION_PREFILL_SOURCE)
    }


def _calculate_m100_annual(secure_objects: SecureObjectRepository) -> CalculationRevision:
    """Run the live M100/2024/0A annual calc, leaving the pagos relations to fold."""
    _seed_taxpayer_profile()
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)
    snapshot = resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_M100_ANNUAL_PERIOD)
    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo="100",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, _M100_ANNUAL_PERIOD),
        revision_id=snapshot.revision.id,
        repository=wu_repo,
        clock=_T0,
    )
    return calculate_modelo_revision_from_bucket_aggregation(
        work_unit.work_unit_id,
        binding_values=_m100_non_relation_zero_bindings(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        transaction_repository=tx_repo,
        invoice_repository=invoice_repo,
        clock=_T0,
    )


def test_ledger_drives_m130_quarters_and_folds_into_m100_annual(
    secure_objects: SecureObjectRepository,
) -> None:
    """The full yearly cadence: persisted ledger → 4×M130 → M100 0604 fold-in."""
    _persist_year_of_income(secure_objects)
    _seed_prior_year_m100(secure_objects)
    _seed_m131_zero_quarters(secure_objects)

    computed_c19: dict[str, Decimal] = {}
    for period in _QUARTER_ORDER:
        revision = _calculate_and_file_m130_quarter(secure_objects, period=period)

        # Transport invariant #1: the FULL bucket-aggregation calc action draws
        # casilla 01 from the persisted ledger (cumulative YTD), not from any
        # manual input — the operator never re-keyed income.
        assert Decimal(revision.casilla_values["01"]) == _EXPECTED_CUMULATIVE_C01[period], (
            f"{period}: casilla 01 must equal cumulative ledger income "
            f"{_EXPECTED_CUMULATIVE_C01[period]}; got {revision.casilla_values.get('01')}"
        )
        computed_c19[period] = Decimal(revision.casilla_values["19"])

    # The four engine-computed quarterly resultado-final values are distinct and
    # strictly positive — a coincidental sum or a single-quarter copy cannot then
    # satisfy the annual fold assertion below.
    assert len(set(computed_c19.values())) == 4, f"quarterly c19 must be distinct: {computed_c19}"
    assert all(value > Decimal("0") for value in computed_c19.values()), computed_c19

    annual = _calculate_m100_annual(secure_objects)

    # Transport invariant #2: the annual M100 0604 folds in the SUM of the four
    # engine-computed M130 casilla-19 values (M131 c15 folds as zero). This wires
    # the quarterly calculations the ledger produced through to the annual renta.
    expected_total = sum(computed_c19.values(), Decimal("0"))
    casilla_0604 = Decimal(annual.casilla_values[_M100_PAGOS_CASILLA])
    assert casilla_0604 == expected_total, (
        f"M100 0604 must fold in the four computed M130 c19 (sum {expected_total}); got {casilla_0604}"
    )


def test_verify_gate_blocks_chain_carrying_non_official_prior_year(
    secure_objects: SecureObjectRepository,
) -> None:
    """The operator verify gate refuses verificado-completo on the ledger chain.

    Completes the operator flow calculate → VERIFY on the same vertical, and
    proves the cross-period clean-state safety invariant fires end-to-end: the
    M130 quarters and the prior-year M100/2023 carry were filed locally through
    ``persist_filed_revision_observation`` with the NON-official ``app_filing``
    source_kind. Filing a dependent period (M100/2024) whose upstream evidence is
    local-only — not an external AEAT justificante / CSV register / live capture —
    must NOT be granted verificado-completo. The verify gate therefore returns a
    BLOCKING ``cross_period_dependency_unclean`` finding naming the non-official
    prior-year filing (modelo 100 / 2023), per
    ``local-filed-observations-are-non-official-evidence`` and
    ``aeat-safety-legal-gates``. This is the correct refusal, not a defect: it
    proves the chain reaches the verify gate and the safety guard engages on a
    real ledger-derived multi-period chain.
    """
    _persist_year_of_income(secure_objects)
    _seed_prior_year_m100(secure_objects)
    _seed_m131_zero_quarters(secure_objects)
    for period in _QUARTER_ORDER:
        _calculate_and_file_m130_quarter(secure_objects, period=period)
    annual = _calculate_m100_annual(secure_objects)

    report = verify_modelo_revision(
        annual.calculation_revision_id,
        actor="system",
        workflow_profile=TaxpayerProfile(tax_id="X1234567L", iva_regime=IVARegime.GENERAL),
        work_unit_repository=WorkUnitCatalogueRepository(objects=secure_objects),
        calculation_repository=CalculationRevisionCatalogueRepository(objects=secure_objects),
        transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=secure_objects),
        calculation_observation_repository=CalculationObservationRepository(objects=secure_objects),
    )

    assert report.calculation_revision_id == annual.calculation_revision_id
    # The chain carries non-official (app_filing) upstream evidence, so the gate
    # must NOT grant verificado-completo.
    assert report.granted_verificado_completo is False
    unclean = [
        finding
        for finding in report.findings
        if finding.kind.value == "cross_period_dependency_unclean" and finding.severity.value == "blocking"
    ]
    assert unclean, (
        f"verify gate must raise a BLOCKING cross_period_dependency_unclean finding "
        f"for the non-official prior-year carry; got {report.findings}"
    )
    # The blocking finding names the non-official prior-year M100/2023 carry.
    assert any("100" in finding.message and "2023" in finding.message for finding in unclean), (
        f"the unclean finding must name the non-official prior-year filing; got {unclean}"
    )
