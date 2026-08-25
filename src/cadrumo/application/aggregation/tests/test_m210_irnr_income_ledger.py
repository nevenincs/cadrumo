"""Secure-store behavioral proof for the Modelo 210 IRNR income source."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....core import M210GrossIncomeSourceMode, M210PayerMode, Period
from ....core.resources import resources
from ....domain.calculations.registry import load_modelo_directory
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.modelos import Modelo210AgrupacionRentaRow
from ....domain.transactions import BusinessClassification, M210IncomeClassification, TransactionDirection
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.env_scope import ready_clave_settings
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.secure_sql import isolated_injected_secure_object_repository, isolated_runtime_profile
from ...ledger.models import ManualLedgerTransactionCommand, ManualLedgerTransactionPatch
from ...ledger.actions_manual import create_manual_transaction, update_manual_transaction_fields
from ...modelo import (
    ModeloAggregationBindingError,
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
    create_work_unit,
    verify_modelo_revision,
)
from ...tests import register_wizard_catalogue
from .. import (
    compute_ledger_filing_evidence,
    compute_ledger_filing_snapshot,
    evaluate_ledger_filing_staleness,
)
from .._irnr_income_ledger import (
    IrnrIncomeLedgerAggregation,
    IrnrIncomeLedgerAggregationIssueReason,
    aggregate_irnr_income_ledger_from_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "d210d210-d210-4210-8210-d210d210d210"
_CLOCK = datetime(2026, 7, 10, 10, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2025, "0A")
_M210_REGISTRY_DIR = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos" / "210"


__all__ = ["register_wizard_catalogue"]


def _classification(code: str, gross_income_amount: Decimal) -> M210IncomeClassification:
    payer_mode = M210PayerMode.MULTIPLE_PAYERS_CODE_35 if code == "35" else M210PayerMode.SINGLE_PAYER
    return M210IncomeClassification(
        official_tipo_renta_code=code,
        gross_income_amount=gross_income_amount,
        applicable_rate=Decimal("0.24"),
        payer_mode=payer_mode,
        payer_id=None if code == "35" else "ES-PAGADOR-210",
        asset_or_right_id="ES-ACTIVO-210",
    )


def _create_income(
    *,
    label: str,
    source_jurisdiction: str | None,
    classification: M210IncomeClassification | None,
    transaction_repository: TransactionCatalogueRepository,
    event_repository: BucketEventHistoryRepository,
) -> str:
    result = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=_BUCKET_ID,
            booked_date=date(2025, 2, 15),
            value_date=date(2025, 2, 15),
            amount=classification.gross_income_amount if classification is not None else Decimal("300.00"),
            direction=TransactionDirection.INCOMING,
            description=f"M210 income {label}",
            business_classification=BusinessClassification.BUSINESS,
            source_jurisdiction=source_jurisdiction,
            m210_income_classification=classification,
            idempotency_key=f"m210-irnr-{label}",
        ),
        transaction_repository=transaction_repository,
        bucket_event_repository=event_repository,
        occurred_at=_CLOCK,
    )
    return result.ref.transaction_id


def _gross_total(result: IrnrIncomeLedgerAggregation) -> Decimal:
    values = result.casilla_aggregation.casilla_values
    return values.get("rendimientos_integros", Decimal("0"))


def _annual_evidence_row() -> Modelo210AgrupacionRentaRow:
    """Supply the registry-required annual legal evidence, separate from [5]."""
    return Modelo210AgrupacionRentaRow(
        source_id="m210-ledger-mode-annual-evidence",
        tipo_renta_code="01",
        importe=Decimal("900.00"),
        tipo_gravamen=Decimal("0.24"),
        pagador_mode=M210PayerMode.SINGLE_PAYER,
        pagador_id="ES-PAGADOR-210",
        deriva_de_bien_derecho=True,
        bien_derecho_id="ES-ACTIVO-210",
    )


def _seed_m210_profile() -> None:
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="activities.description", value="Spanish-source income"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            ),
            created_at=_CLOCK,
            updated_at=_CLOCK,
        )
    )


def test_bucket_calculation_uses_injected_transaction_store_over_distinct_ambient_store(tmp_path: Path) -> None:
    """The public source mesh reads the injected store, never a same-bucket ambient store."""
    with isolated_runtime_profile(tmp_path=tmp_path / "ambient", bucket_id=_BUCKET_ID) as runtime:  # noqa: SIM117
        with isolated_injected_secure_object_repository(
            tmp_path=tmp_path / "injected",
            bucket_id=_BUCKET_ID,
            database_name="m210-injected.db",
        ) as injected_objects:
            injected_transaction_repository = TransactionCatalogueRepository(
                bucket_id=_BUCKET_ID,
                objects=injected_objects,
            )
            injected_event_repository = BucketEventHistoryRepository(objects=injected_objects)
            injected_id = _create_income(
                label="injected-store-only",
                source_jurisdiction="ES",
                classification=_classification("01", Decimal("1234.56")),
                transaction_repository=injected_transaction_repository,
                event_repository=injected_event_repository,
            )

            ambient_transaction_repository = TransactionCatalogueRepository(
                bucket_id=_BUCKET_ID,
                objects=runtime.repository,
            )
            assert ambient_transaction_repository.exists() is False
            _seed_m210_profile()
            work_repository = WorkUnitCatalogueRepository(objects=runtime.repository)
            calculation_repository = CalculationRevisionCatalogueRepository(objects=runtime.repository)
            ambient_event_repository = BucketEventHistoryRepository(objects=runtime.repository)
            snapshot = resources().modelos.authority.snapshot("210", filing_year=2025, period="0A")
            work_unit = create_work_unit(
                bucket_id=_BUCKET_ID,
                modelo="210",
                filing_year=2025,
                period=_PERIOD,
                revision_id=snapshot.revision.id,
                repository=work_repository,
                clock=_CLOCK,
            )

            revision = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_official_tipo_renta_code="01",
                m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=ambient_event_repository,
                transaction_repository=injected_transaction_repository,
                clock=_CLOCK,
            ).revision

            assert revision.casilla_values["rendimientos_integros"] == Decimal("1234.56")
            assert revision.source_transaction_ids == (injected_id,)
            assert {source.source_ref for source in revision.source_provenance} == {f"transaction:{injected_id}"}
            assert ambient_transaction_repository.exists() is False


def test_secure_store_keeps_explicit_classification_and_source_mutation_changes_admission(tmp_path: Path) -> None:
    """ES-only M210 aggregation retains only the selected-code source evidence.

    The actual encrypted transaction catalogue contains rows that differ by
    source jurisdiction, explicit M210 classification, and raw official code.
    Updating the foreign row through the real ledger mutation service changes
    the admitted source evidence; code ``03`` remains excluded from a code
    ``01`` calculation despite sharing the same conceptual general-rate path.
    """
    revision = load_modelo_directory(_M210_REGISTRY_DIR).revisions["2025"]
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        transaction_repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=runtime.repository)
        event_repository = BucketEventHistoryRepository(objects=runtime.repository)
        es_id = _create_income(
            label="es-code-01",
            source_jurisdiction="ES",
            classification=_classification("01", Decimal("825.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        foreign_id = _create_income(
            label="foreign-code-01",
            source_jurisdiction="FR",
            classification=_classification("01", Decimal("500.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        unresolved_id = _create_income(
            label="unresolved-code-01",
            source_jurisdiction=None,
            classification=_classification("01", Decimal("400.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        incomplete_id = _create_income(
            label="es-missing-classification",
            source_jurisdiction="ES",
            classification=None,
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        other_code_id = _create_income(
            label="es-code-03",
            source_jurisdiction="ES",
            classification=_classification("03", Decimal("700.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )

        before_mutation = aggregate_irnr_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            revision=revision,
            selected_official_tipo_renta_code="01",
            transaction_repository=transaction_repository,
        )
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=foreign_id,
            patch=ManualLedgerTransactionPatch(source_jurisdiction="ES"),
            actor="operator",
            source_command="aeat app ledger classify",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=_CLOCK,
        )
        after_mutation = aggregate_irnr_income_ledger_from_repositories(
            bucket_id=_BUCKET_ID,
            period=_PERIOD,
            revision=revision,
            selected_official_tipo_renta_code="01",
            transaction_repository=transaction_repository,
        )
        persisted_foreign = transaction_repository.load().transactions[foreign_id]

    assert _gross_total(before_mutation) == Decimal("825.00")
    assert {observation.transaction_id for observation in before_mutation.observations} == {es_id}
    before_reasons = {issue.transaction_id: issue.reason for issue in before_mutation.issues}
    assert before_reasons[foreign_id] is IrnrIncomeLedgerAggregationIssueReason.FOREIGN_SOURCE_OUT_OF_SCOPE
    assert before_reasons[unresolved_id] is IrnrIncomeLedgerAggregationIssueReason.SOURCE_JURISDICTION_UNRESOLVED
    assert before_reasons[incomplete_id] is IrnrIncomeLedgerAggregationIssueReason.INCOMPLETE_M210_CLASSIFICATION
    assert other_code_id not in before_reasons

    assert _gross_total(after_mutation) == Decimal("1325.00")
    assert {observation.transaction_id for observation in after_mutation.observations} == {es_id, foreign_id}
    assert persisted_foreign.source_jurisdiction == "ES"
    assert persisted_foreign.m210_income_classification == _classification("01", Decimal("500.00"))


def test_m210_gross_income_source_mode_keeps_manual_and_ledger_authority_exclusive(tmp_path: Path) -> None:
    """Manual mode accepts [5]; ledger mode derives ES-only [5] and rejects a manual value."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _seed_m210_profile()
        transaction_repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=runtime.repository)
        event_repository = BucketEventHistoryRepository(objects=runtime.repository)
        es_id = _create_income(
            label="mode-es",
            source_jurisdiction="ES",
            classification=_classification("01", Decimal("900.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        _create_income(
            label="mode-foreign",
            source_jurisdiction="DE",
            classification=_classification("01", Decimal("300.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        code_35_id = _create_income(
            label="mode-code-35",
            source_jurisdiction="ES",
            classification=_classification("35", Decimal("650.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        snapshot = resources().modelos.authority.snapshot("210", filing_year=2025, period="0A")
        work_repository = WorkUnitCatalogueRepository()
        calculation_repository = CalculationRevisionCatalogueRepository()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="210",
            filing_year=2025,
            period=_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repository,
            clock=_CLOCK,
        )

        manual_result = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={"rendimientos_integros": Decimal("777.00")},
            text_casilla_inputs={"tipo_renta": "general"},
            m210_official_tipo_renta_code="01",
            m210_gross_income_source_mode=M210GrossIncomeSourceMode.MANUAL,
            detail_rows=(_annual_evidence_row(),),
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=event_repository,
            transaction_repository=transaction_repository,
            clock=_CLOCK,
        )
        manual = manual_result.revision
        with pytest.raises(ModeloAggregationBindingError):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={"rendimientos_integros": Decimal("777.00")},
                text_casilla_inputs={"tipo_renta": "pension"},
                m210_official_tipo_renta_code="01",
                m210_gross_income_source_mode=M210GrossIncomeSourceMode.MANUAL,
                detail_rows=(_annual_evidence_row(),),
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=event_repository,
                transaction_repository=transaction_repository,
                clock=_CLOCK,
            )
        with pytest.raises(ModeloAggregationBindingError):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={"rendimientos_integros": Decimal("777.00")},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_official_tipo_renta_code="01",
                m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
                detail_rows=(_annual_evidence_row(),),
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=event_repository,
                transaction_repository=transaction_repository,
                clock=_CLOCK,
            )
        with pytest.raises(ModeloAggregationBindingError):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=event_repository,
                transaction_repository=transaction_repository,
                clock=_CLOCK,
            )
        with pytest.raises(ModeloAggregationBindingError):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                text_casilla_inputs={"tipo_renta": "pension"},
                m210_official_tipo_renta_code="01",
                m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=event_repository,
                transaction_repository=transaction_repository,
                clock=_CLOCK,
            )
        with pytest.raises(ModeloAggregationBindingError):
            calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
                work_unit.work_unit_id,
                actor="operator",
                casilla_inputs={},
                text_casilla_inputs={"tipo_renta": "general"},
                m210_official_tipo_renta_code="01",
                m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
                detail_rows=(_annual_evidence_row(),),
                work_unit_repository=work_repository,
                calculation_repository=calculation_repository,
                bucket_event_repository=event_repository,
                transaction_repository=transaction_repository,
                clock=_CLOCK,
            )
        ledger = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            text_casilla_inputs={"tipo_renta": "general"},
            m210_official_tipo_renta_code="01",
            m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=event_repository,
            transaction_repository=transaction_repository,
            clock=_CLOCK,
        ).revision
        ledger_snapshot = compute_ledger_filing_snapshot(
            source_transaction_ids=ledger.source_transaction_ids,
            catalogue=transaction_repository.load(),
            captured_at=_CLOCK,
        )
        ledger_binding = next(
            binding for binding in snapshot.revision.bindings if str(binding.source) == "ledger_irnr_income_aggregation"
        )
        ledger_evidence = compute_ledger_filing_evidence(
            source_transaction_ids=ledger.source_transaction_ids,
            catalogue=transaction_repository.load(),
            snapshot_fingerprint=ledger_snapshot.snapshot_fingerprint,
            captured_at=_CLOCK,
            legal_refs=ledger_binding.legal_refs,
            source_refs=ledger_binding.source_refs,
        )
        code_35_work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="210",
            filing_year=2025,
            period=_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repository,
            clock=_CLOCK,
        )
        ledger_code_35 = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            code_35_work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            text_casilla_inputs={"tipo_renta": "general"},
            m210_official_tipo_renta_code="35",
            m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=event_repository,
            transaction_repository=transaction_repository,
            clock=_CLOCK,
        ).revision
        # The verify half of this test moved to
        # test_m210_ledger_mode_evidence_bundle_records_no_manual_gross_income.
        # It cannot run here any more, and the two guards that make it
        # impossible are both correct. Verifying AFTER these mutations is a
        # stale draft, which the ledger-drift gate refuses: the only
        # contributing row moves twice below, its gross income amount and then
        # its jurisdiction, so granting would freeze 900.00 over a ledger that
        # no longer says 900.00 or even ES. Verifying BEFORE them finalizes the
        # revision, and the ledger then refuses to mutate a row a finalized
        # revision cites. What is left here is the staleness half.
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=es_id,
            patch=ManualLedgerTransactionPatch(
                m210_income_classification=_classification("01", Decimal("901.00")),
            ),
            actor="operator",
            source_command="aeat app ledger classify",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=_CLOCK,
        )
        classification_staleness = evaluate_ledger_filing_staleness(ledger_snapshot, transaction_repository.load())
        jurisdiction_snapshot = compute_ledger_filing_snapshot(
            source_transaction_ids=ledger.source_transaction_ids,
            catalogue=transaction_repository.load(),
            captured_at=_CLOCK,
        )
        update_manual_transaction_fields(
            bucket_id=_BUCKET_ID,
            transaction_id=es_id,
            patch=ManualLedgerTransactionPatch(source_jurisdiction="FR"),
            actor="operator",
            source_command="aeat app ledger classify",
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            occurred_at=_CLOCK,
        )
        jurisdiction_staleness = evaluate_ledger_filing_staleness(jurisdiction_snapshot, transaction_repository.load())

    assert manual.m210_gross_income_source_mode is M210GrossIncomeSourceMode.MANUAL
    assert manual.casilla_values["rendimientos_integros"] == Decimal("777.00")
    assert manual.source_transaction_ids == ()
    assert not any(
        diagnostic.reason == "unhandled_binding_source" and diagnostic.source_kind == "ledger_irnr_income_aggregation"
        for diagnostic in manual_result.source_diagnostics
    )
    assert ledger.m210_gross_income_source_mode is M210GrossIncomeSourceMode.LEDGER
    assert ledger.casilla_values["rendimientos_integros"] == Decimal("900.00")
    assert ledger.source_transaction_ids == (es_id,)
    assert ledger.calculation_revision_id != manual.calculation_revision_id
    assert {source.source_ref for source in ledger.source_provenance} == {f"transaction:{es_id}"}
    assert len(ledger.detail_rows) == 1
    derived_row = ledger.detail_rows[0]
    assert isinstance(derived_row, Modelo210AgrupacionRentaRow)
    assert derived_row.source_id == es_id
    assert derived_row.importe == ledger.casilla_values["rendimientos_integros"]
    assert derived_row.tipo_gravamen == Decimal("0.24")
    assert derived_row.pagador_id == "ES-PAGADOR-210"
    assert derived_row.bien_derecho_id == "ES-ACTIVO-210"
    assert ledger_code_35.source_transaction_ids == (code_35_id,)
    assert len(ledger_code_35.detail_rows) == 1
    derived_code_35_row = ledger_code_35.detail_rows[0]
    assert isinstance(derived_code_35_row, Modelo210AgrupacionRentaRow)
    assert derived_code_35_row.tipo_renta_code == "35"
    assert derived_code_35_row.pagador_mode is M210PayerMode.MULTIPLE_PAYERS_CODE_35
    assert derived_code_35_row.pagador_id is None
    evidence_row = ledger_evidence.rows[0]
    assert evidence_row.source_jurisdiction == "ES"
    assert evidence_row.m210_official_tipo_renta_code == "01"
    assert evidence_row.m210_gross_income_amount == ledger.casilla_values["rendimientos_integros"]
    assert evidence_row.m210_payer_id == "ES-PAGADOR-210"
    assert "trlirnr-rdleg-5-2004:art-13.1" in evidence_row.legal_refs
    assert classification_staleness.changed == (es_id,)
    assert jurisdiction_staleness.changed == (es_id,)


def test_m210_ledger_mode_evidence_bundle_records_no_manual_gross_income(tmp_path: Path) -> None:
    """Ledger mode keeps [5] out of the bundle's manual fact basis.

    The verify half of the authority-exclusivity test above, which can no
    longer live there: that test mutates its only contributing row to exercise
    the staleness verdicts, and a granted verify is impossible on either side of
    those mutations. Verifying after them is a stale draft the ledger-drift gate
    refuses; verifying before them finalizes the revision, and the ledger then
    refuses to mutate a row a finalized revision cites. Both guards are correct,
    so the assertion moved to a revision whose ledger never moves.

    What it pins is the authority split reaching the persisted evidence: in
    ledger mode ``rendimientos_integros`` is derived from the rows, so it must
    NOT also appear as an operator-supplied manual fact.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        _seed_m210_profile()
        transaction_repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=runtime.repository)
        event_repository = BucketEventHistoryRepository(objects=runtime.repository)
        _create_income(
            label="bundle-es",
            source_jurisdiction="ES",
            classification=_classification("01", Decimal("900.00")),
            transaction_repository=transaction_repository,
            event_repository=event_repository,
        )
        snapshot = resources().modelos.authority.snapshot("210", filing_year=2025, period="0A")
        work_repository = WorkUnitCatalogueRepository()
        calculation_repository = CalculationRevisionCatalogueRepository()
        work_unit = create_work_unit(
            bucket_id=_BUCKET_ID,
            modelo="210",
            filing_year=2025,
            period=_PERIOD,
            revision_id=snapshot.revision.id,
            repository=work_repository,
            clock=_CLOCK,
        )
        ledger = calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work_unit.work_unit_id,
            actor="operator",
            casilla_inputs={},
            text_casilla_inputs={"tipo_renta": "general"},
            m210_official_tipo_renta_code="01",
            m210_gross_income_source_mode=M210GrossIncomeSourceMode.LEDGER,
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            bucket_event_repository=event_repository,
            transaction_repository=transaction_repository,
            clock=_CLOCK,
        ).revision

        verification = verify_modelo_revision(
            ledger.calculation_revision_id,
            actor="operator",
            workflow_profile=TaxpayerProfile(tax_id="12345678Z", iva_regime=IVARegime.GENERAL),
            work_unit_repository=work_repository,
            calculation_repository=calculation_repository,
            transaction_repository=transaction_repository,
            bucket_event_repository=event_repository,
            settings=ready_clave_settings("12345678Z"),
            clock=_CLOCK,
        )
        verified_ledger = calculation_repository.load().get(ledger.calculation_revision_id)

    assert verification.granted_verificado_completo is True
    assert verified_ledger is not None
    assert verified_ledger.ledger_filing_evidence is not None
    assert all(
        entry.casilla_id != "rendimientos_integros" for entry in verified_ledger.ledger_filing_evidence.manual_entries
    )
