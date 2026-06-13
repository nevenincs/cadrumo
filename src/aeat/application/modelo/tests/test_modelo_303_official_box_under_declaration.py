"""Modelo 303 official Diseño-de-Registros under-declaration safeguards.

The M303 2023-y-siguientes revision carries two casilla layers: the semantic
aggregate cuota casillas (``iva.repercutido.general``, ``iva.soportado.interiores``,
...) that the ledger source mesh populates and that feed the resultado chain, and
the official numbered Diseño-de-Registros boxes (``input_kind = "manual"``, ids
"01".."77") that carry the official ``export_refs`` the operator transcribes to the
AEAT sede. A ledger-driven calculate folds real cuota into the semantic layer while
EVERY official numbered box stays zero — a silent under-declaration: the human files
the numbered boxes (all zero) outside the application.

Stage 1a (this module): the live calculate path emits a non-blocking
``CalculationSourceDiagnostic`` (reason ``official_box_unpopulated``) naming the
positive computed total and the zero official boxes, and does NOT emit it when the
official boxes carry the cuota.

Stage 1b (this module): the verify gate surfaces at least one ADVISORY finding for
the same total-vs-constituents contradiction, and none when the official boxes are
consistent.

Real adapters (encrypted SQLite via ``isolated_runtime_profile`` →
``SecureObjectRepository`` + ``EphemeralMasterKeyProvider``), real catalogue
repositories, real registry authority, real calculation engine and verify gate. No
mocks/stubs/skips/xfail. The two seeded transactions carry DISTINCT non-equal cuotas
so a copy/contamination cannot satisfy the wiring assertions; the advisory/finding
assertions are structural (presence + named boxes), not hand-summed Decimals.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.iva_compensation._reconciliation import IvaCompensationReconciliationDecision
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_report import ModeloVerificationFindingKind
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
)
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import IvaWalletDecisionRepository
from ...user_profile import UserProfileLifecycleRepository
from .. import (
    BucketAggregationCalculationResult,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
    verify_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)
_BUCKET = "bucket-303-official-box"

# DISTINCT non-equal cuotas so the wiring is unmistakable: one INCOMING general-21
# sale (cuota → semantic iva.repercutido.general → official box 09) and one
# OUTGOING general-21 purchase (cuota → semantic iva.soportado.interiores →
# official box 29). The bases/cuotas are distinct across the two rows.
_SALE_BASE = Decimal("800.00")
_SALE_CUOTA = Decimal("168.00")
_PURCHASE_BASE = Decimal("200.00")
_PURCHASE_CUOTA = Decimal("42.00")

# The official numbered boxes that must stay populated for a consistent filing.
_OFFICIAL_DEVENGADO_GENERAL_CUOTA = "09"
_OFFICIAL_DEDUCIBLE_INTERIORES_CUOTA = "29"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET) as profile:
        yield profile.repository


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="12345678Z",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _store_profile(objects: SecureObjectRepository) -> None:
    UserProfileLifecycleRepository(bucket_id=_BUCKET, objects=objects).save(
        UserProfileRecord(
            profile_id=_BUCKET,
            display_name="Test runtime profile",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _iva_transaction(
    provider_id: str,
    *,
    direction: TransactionDirection,
    amount: Decimal,
    taxable_base: Decimal,
    iva_amount: Decimal,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                transaction_id=provider_id,
                booked_date=date(2026, 2, 10),
                value_date=date(2026, 2, 10),
                amount=amount,
                currency="EUR",
                counterparty="Cliente o proveedor",
                description=f"iva row {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(2026, 2, 11, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "test_iva_operation",
            "taxable_base": taxable_base,
            "iva_rate": Decimal("0.21"),
            "iva_amount": iva_amount,
            "classified_at": datetime(2026, 2, 11, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _wallet_decision() -> IvaCompensationReconciliationDecision:
    return IvaCompensationReconciliationDecision(
        taxpayer_nif="12345678Z",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        selected_authority="aeat_wallet",
        selected_amount=Decimal("0.00"),
        wallet_amount=Decimal("0.00"),
        local_recurrence_amount=Decimal("0.00"),
        override_amount=None,
        divergence="match",
        blocked=False,
        stale_wallet=False,
        reason="official-box advisory fixture",
        wallet_captured_at=_T1,
        decided_at=_T1,
    )


def _seed_work_unit(wu_repo: WorkUnitCatalogueRepository):
    return create_work_unit(
        bucket_id=_BUCKET,
        modelo="303",
        filing_year=2026,
        period=Period.from_year_and_code(2026, "1T"),
        revision_id="2023-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )


def _seeded_calculation(
    secure_objects: SecureObjectRepository,
) -> BucketAggregationCalculationResult:
    _store_profile(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(_wallet_decision())

    sale = _iva_transaction(
        "general-sale",
        direction=TransactionDirection.INCOMING,
        amount=_SALE_BASE + _SALE_CUOTA,
        taxable_base=_SALE_BASE,
        iva_amount=_SALE_CUOTA,
    )
    purchase = _iva_transaction(
        "general-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=_PURCHASE_BASE + _PURCHASE_CUOTA,
        taxable_base=_PURCHASE_BASE,
        iva_amount=_PURCHASE_CUOTA,
    )
    # Non-vacuity: the two seeded cuotas are distinct, so the semantic-layer fold is
    # unmistakable (no copy/contamination can satisfy both legs).
    assert _SALE_CUOTA != _PURCHASE_CUOTA

    work_unit = _seed_work_unit(wu_repo)
    tx_repo.save(TransactionCatalogue.from_transactions((sale, purchase)))
    return calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-A",
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=_wallet_decision(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )


# ---------------------------------------------------------------------------
# Stage 1a — calculate-path advisory
# ---------------------------------------------------------------------------


def test_calculate_advisory_fires_when_official_devengado_boxes_unpopulated(
    secure_objects: SecureObjectRepository,
) -> None:
    """A ledger-folded calculate surfaces the official-box advisory.

    The semantic ``iva.repercutido.general`` / ``iva.soportado.interiores``
    casillas carry the seeded cuotas (so ``iva.cuota-devengada-total`` and
    ``iva.cuota-deducible-total`` are positive), while the official numbered
    boxes 09 (devengado 21pct cuota) and 29 (deducible interiores cuota) stay
    zero — exactly the silent under-declaration the advisory exists to surface.
    """
    result = _seeded_calculation(secure_objects)

    # Semantic layer carried the seeded cuotas; official numbered boxes are zero.
    assert result.revision.casilla_values["iva.repercutido.general"] == _SALE_CUOTA
    assert result.revision.casilla_values["iva.soportado.interiores"] == _PURCHASE_CUOTA
    assert Decimal(result.revision.casilla_values[_OFFICIAL_DEVENGADO_GENERAL_CUOTA]) == Decimal("0")
    assert Decimal(result.revision.casilla_values[_OFFICIAL_DEDUCIBLE_INTERIORES_CUOTA]) == Decimal("0")

    official_box_diagnostics = [
        diag for diag in result.source_diagnostics if diag.reason == "official_box_unpopulated"
    ]
    # Both the devengado and deducible totals are positive with all official
    # constituent boxes zero, so both predicates fire.
    fired_antecedents = {diag.casilla_id for diag in official_box_diagnostics}
    assert fired_antecedents == {"iva.cuota-devengada-total", "iva.cuota-deducible-total"}
    # The advisory names the concrete official boxes the operator must transcribe.
    devengado_diag = next(d for d in official_box_diagnostics if d.casilla_id == "iva.cuota-devengada-total")
    assert _OFFICIAL_DEVENGADO_GENERAL_CUOTA in devengado_diag.message
    deducible_diag = next(d for d in official_box_diagnostics if d.casilla_id == "iva.cuota-deducible-total")
    assert _OFFICIAL_DEDUCIBLE_INTERIORES_CUOTA in deducible_diag.message


def test_calculate_advisory_silent_when_official_boxes_carry_cuota(
    secure_objects: SecureObjectRepository,
) -> None:
    """No official-box advisory fires when the operator has populated the boxes.

    The operator supplies the official numbered cuota boxes (09 devengado RG
    21pct, 11/13 inversion, 29 deducible interiores) through the manual casilla
    channel, so the total-vs-constituents contradiction does not hold and the
    advisory stays silent. The boxes are manual_input (not source-owned), so the
    caller override is accepted.
    """
    _store_profile(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(_wallet_decision())

    sale = _iva_transaction(
        "general-sale",
        direction=TransactionDirection.INCOMING,
        amount=_SALE_BASE + _SALE_CUOTA,
        taxable_base=_SALE_BASE,
        iva_amount=_SALE_CUOTA,
    )
    purchase = _iva_transaction(
        "general-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=_PURCHASE_BASE + _PURCHASE_CUOTA,
        taxable_base=_PURCHASE_BASE,
        iva_amount=_PURCHASE_CUOTA,
    )
    work_unit = _seed_work_unit(wu_repo)
    tx_repo.save(TransactionCatalogue.from_transactions((sale, purchase)))

    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={
            # Devengado constituent official boxes (consistent with the semantic cuota).
            "09": _SALE_CUOTA,
            "11": Decimal("0"),
            "13": Decimal("0"),
            # Deducible constituent official boxes.
            "29": _PURCHASE_CUOTA,
            "33": Decimal("0"),
            "37": Decimal("0"),
        },
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=_wallet_decision(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )

    assert Decimal(result.revision.casilla_values[_OFFICIAL_DEVENGADO_GENERAL_CUOTA]) == _SALE_CUOTA
    assert Decimal(result.revision.casilla_values[_OFFICIAL_DEDUCIBLE_INTERIORES_CUOTA]) == _PURCHASE_CUOTA
    assert not [diag for diag in result.source_diagnostics if diag.reason == "official_box_unpopulated"]


# ---------------------------------------------------------------------------
# Stage 1b — verify-path advisory finding
# ---------------------------------------------------------------------------


def test_verify_surfaces_advisory_for_unpopulated_official_boxes(
    secure_objects: SecureObjectRepository,
) -> None:
    """The verify gate surfaces an ADVISORY finding, never finding_count == 0.

    A ledger-folded revision whose official numbered boxes are all zero (while
    the computed totals are positive) must NOT pass verify with zero findings —
    the no-silent-under-declaration invariant. At least one ADVISORY finding for
    each total-vs-constituents contradiction is surfaced.
    """
    result = _seeded_calculation(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    bv_repo = BucketEventHistoryRepository(objects=secure_objects)

    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    advisory_findings = [
        finding for finding in report.findings if finding.kind is ModeloVerificationFindingKind.ADVISORY
    ]
    advisory_refs = {ref for finding in advisory_findings for ref in finding.legal_refs}
    # The devengado advisory grounds in LIVA art. 88, the deducible in art. 92.
    assert "ley-37-1992:art-88" in advisory_refs
    assert "ley-37-1992:art-92" in advisory_refs
    assert len(advisory_findings) >= 2


def test_verify_no_official_box_advisory_when_boxes_consistent(
    secure_objects: SecureObjectRepository,
) -> None:
    """The official-box advisory does not fire when the numbered boxes are consistent.

    Negative control: when the operator has transcribed the cuota into the
    official numbered boxes, the total-vs-constituents contradiction does not
    hold, so the official-box ADVISORY findings are absent. (Other unrelated
    advisories may still surface; this asserts the official-box pair specifically
    is gone by checking the LIVA art. 88 / art. 92 advisory-grounded findings are
    not both present from the official-box predicates.)
    """
    _store_profile(secure_objects)
    wu_repo = WorkUnitCatalogueRepository(objects=secure_objects)
    cr_repo = CalculationRevisionCatalogueRepository(objects=secure_objects)
    event_repo = BucketEventHistoryRepository(objects=secure_objects)
    tx_repo = TransactionCatalogueRepository(bucket_id=_BUCKET, objects=secure_objects)
    IvaWalletDecisionRepository(objects=secure_objects).save_decision(_wallet_decision())

    sale = _iva_transaction(
        "general-sale",
        direction=TransactionDirection.INCOMING,
        amount=_SALE_BASE + _SALE_CUOTA,
        taxable_base=_SALE_BASE,
        iva_amount=_SALE_CUOTA,
    )
    purchase = _iva_transaction(
        "general-purchase",
        direction=TransactionDirection.OUTGOING,
        amount=_PURCHASE_BASE + _PURCHASE_CUOTA,
        taxable_base=_PURCHASE_BASE,
        iva_amount=_PURCHASE_CUOTA,
    )
    work_unit = _seed_work_unit(wu_repo)
    tx_repo.save(TransactionCatalogue.from_transactions((sale, purchase)))
    result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
        work_unit.work_unit_id,
        actor="operator-A",
        casilla_inputs={
            "09": _SALE_CUOTA,
            "11": Decimal("0"),
            "13": Decimal("0"),
            "29": _PURCHASE_CUOTA,
            "33": Decimal("0"),
            "37": Decimal("0"),
        },
        binding_values={
            "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
            "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        },
        iva_compensation_decision=_wallet_decision(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=event_repo,
        transaction_repository=tx_repo,
        clock=_T1,
    )

    vr_repo = VerificationReportCatalogueRepository(objects=secure_objects)
    report = verify_modelo_revision(
        result.revision.calculation_revision_id,
        actor="operator-A",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=event_repo,
        clock=_T1,
    )
    # The official-box predicates ground devengado in art. 88 and deducible in
    # art. 92; with consistent boxes neither fires, so no advisory finding carries
    # both refs from the official-box pair. We assert the contradiction is gone by
    # confirming the official-box devengado advisory (art. 88, ADVISORY) is absent.
    official_box_advisories = [
        finding
        for finding in report.findings
        if finding.kind is ModeloVerificationFindingKind.ADVISORY
        and "ley-37-1992:art-88" in finding.legal_refs
        and "rd-1624-1992:art-71" in finding.legal_refs
        and "orden-eha-3786-2008:art-1" in finding.legal_refs
    ]
    assert not official_box_advisories
