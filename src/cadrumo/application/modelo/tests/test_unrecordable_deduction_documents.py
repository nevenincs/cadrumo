"""Each unrecordable deduction document is refused on its own encrypted ledger facts."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....core.aggregation import BindingSourceKind
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from ....domain.modelos.verification_report import ModeloVerificationFinding
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..preconditions import ModeloPreconditionFailure
from ..verification_actions import _append_iva_selected_scope_evidence_finding
from ..work_form_models import finding_action_locale_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_NOW = datetime(2026, 4, 2, 12, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2026, "1T")


def _transaction(provider_id: str, kind: str | None, category: str | None, *, currency: str = "EUR") -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=date(2026, 2, 15),
                amount=Decimal("242.125"),
                currency=currency,
                description="A real native description containing spaces",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="a" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=_NOW,
                    provider_name="manual",
                ),
                raw_fields={},
            ),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "deduction_fact_kind": kind,
            "iva_category": category,
        }
    )


def _issue(transaction_id: str | None) -> CalculationSourceIssue:
    return CalculationSourceIssue(
        reason="iva_selected_scope_evidence_failure",
        binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
        message="A selected-scope deduction lacks its required evidence",
        source_ref=None if transaction_id is None else f"transaction:{transaction_id}",
    )


def _work_and_target(
    bucket_id: str, issues: tuple[CalculationSourceIssue, ...]
) -> tuple[WorkUnit, CalculationRevision]:
    work_unit_id = derive_work_unit_id(
        bucket_id=bucket_id, modelo="303", filing_year=2026, period=_PERIOD, revision_id="2026-y-siguientes"
    )
    work = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=bucket_id,
        modelo="303",
        filing_year=2026,
        period=_PERIOD,
        revision_id="2026-y-siguientes",
        name="Document evidence proof",
        created_at=_NOW,
        updated_at=_NOW,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        source_issues=issues,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    target = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="303", revision_id="2026-y-siguientes", modelo_year=2026, period="1T"
        ),
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        casilla_values={},
        source_issues=issues,
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    return work, target


def test_unrecordable_documents_are_separate_and_every_unclassified_issue_keeps_its_general_refusal(
    tmp_path: Path,
) -> None:
    """Repeated issue refs deduplicate; missing rows and unknown deductions remain blocked."""
    transactions = (
        _transaction("intra-one", "intra_eu_current", "intra_community_acquisition_reverse_charge"),
        _transaction("intra-two", "intra_eu_current", "intra_community_acquisition_reverse_charge"),
        _transaction("customs", "import_current", "import_third_country", currency="USD"),
        _transaction("reagp", "reagp_compensation", "reagp_compensation"),
        _transaction("rectification", "rectification", "domestic_general"),
        _transaction("domestic", "domestic_current", "domestic_general"),
        _transaction("unknown", None, None),
        _transaction("register-owned", "investment_goods_regularisation", "domestic_general"),
    )
    with isolated_runtime_profile(tmp_path=tmp_path) as runtime:
        repository = TransactionCatalogueRepository(bucket_id=runtime.bucket_id, objects=runtime.repository)
        repository.save(TransactionCatalogue.from_transactions(transactions))
        issues = (
            *(_issue(transaction.transaction_id) for transaction in transactions),
            _issue(transactions[0].transaction_id),
            _issue("f" * 64),
            _issue(None),
        )
        work, target = _work_and_target(runtime.bucket_id, issues)
        findings: list[ModeloVerificationFinding] = []
        failures: dict[int, ModeloPreconditionFailure] = {}
        _append_iva_selected_scope_evidence_finding(
            work_unit=work,
            target=target,
            transaction_repository=repository,
            findings=findings,
            failures_by_finding_id=failures,
        )
    assert len(findings) == 6
    separate = {
        finding.message_facts["transaction_ids"]: finding
        for finding in findings
        if "transaction_ids" in finding.message_facts
    }
    assert set(separate) == {transaction.transaction_id for transaction in transactions[:5]}
    for transaction in transactions[:5]:
        finding = separate[transaction.transaction_id]
        assert finding.message_facts["transaction_count"] == 1
        assert finding.message_facts["transaction_date"] == "2026-02-15"
        assert finding.message_facts["transaction_amount"] == Decimal("242.125")
        assert finding.message_facts["transaction_currency"] == transaction.raw.currency
        assert finding_action_locale_key(finding) == "application.modelo.work_form.finding_action.file_another_way"
        assert failures[id(finding)].verdict.no_recovery_outcome is NoRecoveryOutcome.TERMINAL
        assert failures[id(finding)].verdict.action is None
        assert "description" not in finding.message_facts
    assert separate[transactions[2].transaction_id].message_facts["transaction_currency"] == "USD"
    general = next(finding for finding in findings if "source_ref_ids" in finding.message_facts)
    assert general.message_facts["source_ref_count"] == 4
    assert general.message_facts["unidentified_source_count"] == 1
    refs = str(general.message_facts["source_ref_ids"]).split("|")
    assert set(refs) == {f"transaction:{transaction.transaction_id}" for transaction in transactions[5:]} | {
        f"transaction:{'f' * 64}"
    }
    assert failures[id(general)].verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION

    assert finding_action_locale_key(general) == "application.modelo.work_form.finding_action.correct_and_recalculate"
