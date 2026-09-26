"""Export evidence policy for ledger-derived calculation revisions.

These tests exercise the application gate over an already assembled revision.
The encrypted calculation-repository round-trip is covered separately at the
profile-persistence adapter seam.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from cadrumo.application.calculations.tests.filing_evidence import general_m303_filing_evidence
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.bindings import CasillaObservation
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    CalculationSourceIssue,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.ledger_filing_snapshot import LedgerFilingSnapshot
from cadrumo.domain.modelos.work_unit import derive_work_unit_id

from ..export import ModeloExportEvidenceMissingError, _raise_if_ledger_export_evidence_missing
from ..verification_actions import (
    _iva_compensation_annual_source_evidence_finding,
    _iva_selected_scope_evidence_finding,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 6, 3, 16, 0, tzinfo=UTC)
_TX_ID = "a" * 64
_BASE_CASILLA: CasillaId = validated_casilla_id("base", surface="_BASE_CASILLA")
_CUOTA_CASILLA: CasillaId = validated_casilla_id("cuota", surface="_CUOTA_CASILLA")


def _revision(
    *,
    source_transaction_ids: tuple[str, ...],
    ledger_filing_snapshot: LedgerFilingSnapshot | None = None,
    source_issues: tuple[CalculationSourceIssue, ...] = (),
    modelo: str = "303",
    period: str = "1T",
    operation: PinnedAuthorityOperation,
) -> CalculationRevision:
    work_unit_id = derive_work_unit_id(
        bucket_id="bucket-operator",
        modelo=modelo,
        filing_year=2026,
        period=Period.from_year_and_code(2026, period),
        revision_id="gate",
    )
    filing_instance_evidence = general_m303_filing_evidence(
        Period.from_year_and_code(2026, "1T"), reference="test:export-evidence-gate", operation=operation
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        binding_overrides={},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        source_transaction_ids=source_transaction_ids,
        filing_instance_evidence=filing_instance_evidence,
        source_issues=source_issues,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=modelo,
            revision_id="gate",
            modelo_year=2026,
            period=period,
        ),
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        input_values_by_casilla_id={_BASE_CASILLA: "100.00"},
        casilla_values={_CUOTA_CASILLA: Decimal("21.00")},
        observations=(
            CasillaObservation(
                casilla_id=_CUOTA_CASILLA,
                value=Decimal("21.00"),
                legal_refs=("ley-37-1992:art-99",),
                source_refs=("export-evidence-gate-test",),
            ),
        ),
        source_transaction_ids=source_transaction_ids,
        ledger_filing_snapshot=ledger_filing_snapshot,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=filing_instance_evidence,
        source_issues=source_issues,
        source_provenance=(),
    )


def test_export_refuses_ledger_revision_without_bundled_evidence_or_reference(
    *, operation: PinnedAuthorityOperation
) -> None:
    revision = _revision(source_transaction_ids=(_TX_ID,), operation=operation)

    with pytest.raises(ModeloExportEvidenceMissingError):
        _raise_if_ledger_export_evidence_missing(revision)


def test_export_allows_non_ledger_revision_without_evidence(*, operation: PinnedAuthorityOperation) -> None:
    revision = _revision(source_transaction_ids=(), operation=operation)

    _raise_if_ledger_export_evidence_missing(revision)


def test_export_allows_ledger_revision_with_snapshot_reference(*, operation: PinnedAuthorityOperation) -> None:
    revision = _revision(
        source_transaction_ids=(_TX_ID,),
        ledger_filing_snapshot=LedgerFilingSnapshot(
            snapshot_fingerprint="f" * 64,
            captured_at=_NOW,
        ),
        operation=operation,
    )

    _raise_if_ledger_export_evidence_missing(revision)


def test_export_refuses_a_revision_with_unresolved_selected_scope_iva_evidence(
    *, operation: PinnedAuthorityOperation
) -> None:
    revision = _revision(
        source_transaction_ids=(),
        source_issues=(
            CalculationSourceIssue(
                reason="iva_selected_scope_evidence_failure",
                binding_source=BindingSourceKind.LEDGER_IVA_AGGREGATION,
                message="selected-scope IVA evidence failure",
                resolver_id="ledger_iva_aggregation",
                source_ref=f"transaction:{_TX_ID}",
            ),
        ),
        operation=operation,
    )

    with pytest.raises(ModeloExportEvidenceMissingError):
        _raise_if_ledger_export_evidence_missing(revision)

    reopened = CalculationRevision.model_validate_json(revision.model_dump_json())
    assert reopened.source_issues == revision.source_issues
    finding = _iva_selected_scope_evidence_finding(revision)
    assert finding is not None
    assert finding.severity.value == "blocking"
    assert finding.message_facts["source_ref_ids"] == f"transaction:{_TX_ID}"


def test_export_allows_a_revision_with_an_unrouted_non_iva_source_issue(*, operation: PinnedAuthorityOperation) -> None:
    revision = _revision(
        source_transaction_ids=(),
        source_issues=(
            CalculationSourceIssue(
                reason="unrouted_observation",
                binding_source=BindingSourceKind.LEDGER_OSS_AGGREGATION,
                message="OSS source was not routed",
            ),
        ),
        operation=operation,
    )

    _raise_if_ledger_export_evidence_missing(revision)
    assert _iva_selected_scope_evidence_finding(revision) is None


def test_export_refuses_m390_when_required_annual_partition_evidence_is_unresolved(
    *, operation: PinnedAuthorityOperation
) -> None:
    revision = _revision(
        source_transaction_ids=(),
        modelo="390",
        period="0A",
        source_issues=(
            CalculationSourceIssue(
                reason="iva_compensation_annual_source_evidence_failure",
                binding_source=BindingSourceKind.IVA_COMPENSATION_ANNUAL_PARTITION,
                message="required Modelo 303 annual partition evidence is unresolved",
                resolver_id="iva_compensation_annual_partition",
            ),
        ),
        operation=operation,
    )

    with pytest.raises(ModeloExportEvidenceMissingError):
        _raise_if_ledger_export_evidence_missing(revision)

    finding = _iva_compensation_annual_source_evidence_finding(revision)
    assert finding is not None
    assert finding.severity.value == "blocking"
    assert finding.message_locale_key == "application.modelo.findings.iva_compensation_annual_source_evidence_failure"
    assert finding.message_facts == {"source_issue_count": 1}
