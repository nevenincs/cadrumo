"""Repository-backed inventory source resolver tests."""

from __future__ import annotations

import traceback
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.storage import PROFILE_INVENTORY_LEDGER_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.engine import get_engine
from ....core import BindingSourceKind, Period
from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....core.resources import resources
from ....domain.calculations.registry import DataBindingDefinition, ModeloRevision
from ....domain.contribuyente.inventory import (
    InventoryAcquisitionCompleteness,
    InventoryAcquisitionCost,
    InventoryAcquisitionEvidence,
    InventoryAcquisitionEvidenceKind,
    InventoryClosingAuthority,
    InventoryClosingAuthorityDecision,
    InventoryClosingAuthorityRecord,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    InventoryClosingValuationBasis,
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    MovementRecord,
    PhysicalClosingEvidence,
    PhysicalClosingEvidenceRole,
    PhysicalClosingObservation,
    PriorAuthoritativeClosingLink,
    PriorClosingContinuityEvidence,
    ValuationMethod,
    compute_inventory_anexo_d_projection,
    fingerprint_prior_authoritative_closing,
)
from ....domain.filing_evidence import FilingEvidenceReference
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._inventory import _VALUE_ATTRIBUTE_BY_OPERATION, InventorySourceResolver
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _Repository:
    def __init__(self, document: InventoryLedgerDocument | None = None, *, error: bool = False) -> None:
        self.document = document or InventoryLedgerDocument(ledgers=())
        self.error = error
        self.loads = 0

    def load(self) -> InventoryLedgerDocument:
        self.loads += 1
        if self.error:
            raise InventoryLedgerError("sensitive database failure detail")
        return self.document


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _ledger(
    *,
    actividad_id: str = "retail",
    complete: bool = True,
    physical_closing: Decimal | None = None,
) -> InventoryLedger:
    continuity = (PriorClosingContinuityEvidence(reference=_ref("prior-secret"), content_digest="f" * 64),)
    acquisition = InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal("100.00"),
        consideration_iva_amount=Decimal("21.00"),
        consideration_deductible_iva_ratio=Decimal("1"),
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=_ref("invoice-secret"),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("cost-review-secret"),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref("iva-review-secret"),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="c" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=_ref("invoice-secret"),
            attributable_cost_review_evidence=_ref("cost-review-secret"),
            iva_recoverability_review_evidence=_ref("iva-review-secret"),
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("21.00"),
        total_acquisition_cost=Decimal("100.00"),
    )
    movement = MovementRecord.from_purchase_acquisition(
        movement_id="purchase-1",
        movement_date=date(2025, 2, 1),
        quantity=Decimal("1"),
        acquisition_cost=acquisition,
    )
    observation = None
    if physical_closing is not None:
        observation = PhysicalClosingObservation(
            observation_id="physical-2025",
            observed_on=date(2026, 1, 1),
            as_of_date=date(2025, 12, 31),
            actividad_id=actividad_id,
            filing_year=2025,
            closing_value=physical_closing,
            valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
            evidence=(
                PhysicalClosingEvidence(
                    reference=_ref("physical-count-secret"),
                    role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                    content_digest="1" * 64,
                ),
                PhysicalClosingEvidence(
                    reference=_ref("physical-value-secret"),
                    role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                    content_digest="2" * 64,
                ),
            ),
        )
    decision = InventoryClosingAuthorityDecision(
        decision_id="decision-2025",
        actividad_id=actividad_id,
        filing_year=2025,
        authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
        physical_observation_id=observation.observation_id if observation is not None else None,
        physical_observation_fingerprint=observation.fingerprint if observation is not None else None,
        reason="Reviewed movement authority.",
        actor="reviewer-secret",
        source_command="inventory-secret-command",
        decided_at=datetime(2026, 1, 2, tzinfo=UTC),
        evidence=(
            InventoryClosingDecisionEvidence(
                reference=_ref("decision-secret"),
                role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                content_digest="d" * 64,
            ),
        ),
    )
    prior_fingerprint = fingerprint_prior_authoritative_closing(
        actividad_id=actividad_id,
        filing_year=2024,
        authoritative_closing_value=Decimal("100.00"),
        authoritative_source_fingerprint="e" * 64,
        evidence=continuity,
    )
    record = InventoryClosingAuthorityRecord(
        decision=decision,
        physical_observation=observation,
        prior_closing_link=PriorAuthoritativeClosingLink(
            actividad_id=actividad_id,
            current_filing_year=2025,
            prior_filing_year=2024,
            prior_authoritative_closing_value=Decimal("100.00"),
            current_opening_value=Decimal("100.00"),
            prior_authoritative_source_fingerprint="e" * 64,
            prior_authoritative_closing_fingerprint=prior_fingerprint,
            evidence=continuity,
        ),
    )
    ledger = InventoryLedger(
        actividad_id=actividad_id,
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("100.00"),
        period_movements=(movement,),
        closing_authority_record=record,
    )
    if complete:
        return ledger
    return ledger.model_copy(update={"closing_authority_record": None})


def _binding(operation: str, target: str) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=f"inventory-{target}",
        source=BindingSourceKind.INVENTORY,
        selector={
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "actividad_id": "retail",
            "operation": operation,
            "target_casilla_id": target,
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
    )


def _revision(*, inventory: bool = True) -> ModeloRevision:
    base = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A").revision
    bindings = ()
    if inventory:
        bindings = (
            _binding("complete_acquisition_cost", "0181"),
            _binding("closing_minus_opening_positive", "0177"),
            _binding("opening_minus_closing_positive", "0182"),
        )
    return base.model_copy(update={"bindings": bindings})


def _context(revision: ModeloRevision, *, bucket_id: str = "operator", year: int = 2025) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id=bucket_id,
        modelo="100",
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        revision=revision,
    )


def test_complete_ledger_resolves_three_values_and_stable_provenance() -> None:
    repository = _Repository(InventoryLedgerDocument(ledgers=(_ledger(),)))
    resolver = InventorySourceResolver(inventory_repository=repository)

    first = resolver.resolve(_context(_revision()))
    second = resolver.resolve(_context(_revision()))

    assert first.binding_values == {
        "inventory-0177": Decimal("100.00"),
        "inventory-0181": Decimal("100.00"),
        "inventory-0182": Decimal("0.00"),
    }
    assert first.unresolved_binding_ids == ()
    assert first.diagnostics == ()
    assert first.provenance == second.provenance
    assert first.provenance[0].source_ref == "inventory:operator:2025:retail"
    projection = compute_inventory_anexo_d_projection(repository.document.ledgers[0])
    assert first.provenance[0].fingerprint == projection.projection_fingerprint


def test_operation_adapter_is_exhaustive_for_canonical_selector_vocabulary() -> None:
    assert set(_VALUE_ATTRIBUTE_BY_OPERATION) == {
        "complete_acquisition_cost",
        "closing_minus_opening_positive",
        "opening_minus_closing_positive",
    }


def test_retained_closing_conflict_keeps_source_owned_values_and_safe_advisory() -> None:
    ledger = _ledger(physical_closing=Decimal("250.00"))
    result = InventorySourceResolver(
        inventory_repository=_Repository(InventoryLedgerDocument(ledgers=(ledger,)))
    ).resolve(_context(_revision()))

    assert result.binding_values["inventory-0177"] == Decimal("100.00")
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics[0].reason == "source_issue"
    assert "closing_conflict_retained" in result.diagnostics[0].message
    assert "250.00" not in result.diagnostics[0].message
    assert "physical-count-secret" not in result.diagnostics[0].message


def test_source_semantic_change_changes_provenance_fingerprint() -> None:
    ledger = _ledger()
    changed_movement = ledger.period_movements[0].model_copy(update={"movement_date": date(2025, 3, 1)})
    changed_ledger = InventoryLedger.model_validate(
        ledger.model_copy(update={"period_movements": (changed_movement,)}).model_dump()
    )
    first = InventorySourceResolver(
        inventory_repository=_Repository(InventoryLedgerDocument(ledgers=(ledger,)))
    ).resolve(_context(_revision()))
    changed = InventorySourceResolver(
        inventory_repository=_Repository(InventoryLedgerDocument(ledgers=(changed_ledger,)))
    ).resolve(_context(_revision()))

    assert first.binding_values == changed.binding_values
    assert first.provenance[0].fingerprint != changed.provenance[0].fingerprint


def test_no_inventory_bindings_is_allocation_free_and_does_not_read() -> None:
    repository = _Repository(error=True)
    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=False)))

    assert result.binding_values == {}
    assert result.diagnostics == ()
    assert result.provenance == ()
    assert repository.loads == 0


@pytest.mark.parametrize(
    ("kind", "expected_reason"),
    [
        ("absent", "unresolved_binding"),
        ("incomplete", "source_domain_not_ready"),
        ("unreadable", "storage_degraded"),
    ],
)
def test_source_failures_remain_unresolved_and_value_free(
    kind: str,
    expected_reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    if kind == "absent":
        repository = _Repository()
    elif kind == "incomplete":
        repository = _Repository(InventoryLedgerDocument.model_construct(ledgers=(_ledger(complete=False),)))
    else:
        repository = _Repository(error=True)
    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision()))

    assert result.binding_values == {}
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    assert result.diagnostics[0].reason == expected_reason
    rendered = " ".join(item.message for item in result.diagnostics)
    for secret in (
        "100.00", "invoice-secret", "decision-secret", "prior-secret", "reviewer-secret",
        "inventory-secret-command", "a" * 64, "d" * 64, "f" * 64, "sensitive database failure detail",
    ):
        assert secret not in rendered
        assert secret not in caplog.text


def test_wrong_activity_and_unsupported_year_fail_closed() -> None:
    repository = _Repository(InventoryLedgerDocument(ledgers=(_ledger(actividad_id="other"),)))
    absent = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision()))
    unsupported = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(), year=2024))

    assert absent.binding_values == unsupported.binding_values == {}
    assert len(absent.unresolved_binding_ids) == len(unsupported.unresolved_binding_ids) == 3
    assert absent.diagnostics[0].reason == "unresolved_binding"
    assert unsupported.diagnostics[0].reason == "unhandled_binding_source"
    assert "activity 'retail'" in absent.diagnostics[0].message
    assert "only Modelo 100 filing year 2025" in unsupported.diagnostics[0].message


def test_tampered_continuity_fingerprint_refuses_before_value_resolution() -> None:
    ledger = _ledger()
    assert ledger.closing_authority_record is not None
    link = ledger.closing_authority_record.prior_closing_link.model_copy(
        update={"prior_authoritative_closing_fingerprint": "0" * 64}
    )
    record = ledger.closing_authority_record.model_copy(update={"prior_closing_link": link})
    tampered = ledger.model_copy(update={"closing_authority_record": record})
    repository = _Repository(InventoryLedgerDocument.model_construct(ledgers=(tampered,)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision()))

    assert result.binding_values == {}
    assert result.diagnostics[0].reason == "source_domain_not_ready"
    assert "0" * 64 not in result.diagnostics[0].message


def test_real_encrypted_empty_repository_reports_absence(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="00000000-0000-4000-8000-000000000039",
    ) as runtime:
        repository = InventoryLedgerRepository(objects=runtime.repository)
        result = InventorySourceResolver(inventory_repository=repository).resolve(
            _context(_revision(), bucket_id=runtime.bucket_id)
        )

    assert result.binding_values == {}
    assert result.diagnostics[0].reason == "unresolved_binding"


def test_real_encrypted_complete_repository_resolves_projection(tmp_path: Path) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="00000000-0000-4000-8000-000000000139",
    ) as runtime:
        repository = InventoryLedgerRepository(objects=runtime.repository)
        ledger = _ledger()
        repository.save(InventoryLedgerDocument(ledgers=(ledger,)))
        result = InventorySourceResolver(inventory_repository=repository).resolve(
            _context(_revision(), bucket_id=runtime.bucket_id)
        )

    assert result.binding_values["inventory-0181"] == Decimal("100.00")
    assert result.provenance[0].fingerprint == compute_inventory_anexo_d_projection(ledger).projection_fingerprint


def test_real_encrypted_corruption_becomes_value_free_storage_diagnostic(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id="00000000-0000-4000-8000-000000000239",
    ) as runtime:
        repository = InventoryLedgerRepository(objects=runtime.repository)
        repository.save(InventoryLedgerDocument(ledgers=(_ledger(),)))
        statement = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
        )

        def remove_authority(document: dict[str, object]) -> None:
            ledgers = document["ledgers"]
            assert isinstance(ledgers, list) and isinstance(ledgers[0], dict)
            assert ledgers[0].pop("closing_authority_record") is not None

        mutate_encrypted_secure_object_json(
            get_engine(runtime.settings),
            row_statement=statement,
            mutate=remove_authority,
        )
        with pytest.raises(InventoryLedgerError) as exc_info:
            repository.load()
        assert exc_info.value.translated_message == (
            "adapters.persistence.profile.inventory.errors.load_inventory_ledger_failed"
        )
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None
        assert exc_info.value.__suppress_context__ is True
        result = InventorySourceResolver(inventory_repository=repository).resolve(
            _context(_revision(), bucket_id=runtime.bucket_id)
        )

    assert result.binding_values == {}
    assert result.diagnostics[0].reason == "storage_degraded"
    rendered = "".join(traceback.format_exception(exc_info.value))
    rendered += " ".join(item.message for item in result.diagnostics) + caplog.text
    for secret in (
        "invoice-secret",
        "cost-review-secret",
        "iva-review-secret",
        "decision-secret",
        "prior-secret",
        "reviewer-secret",
        "inventory-secret-command",
        "100.00",
        "21.00",
        *(character * 64 for character in "abcdef12"),
    ):
        assert secret not in rendered
