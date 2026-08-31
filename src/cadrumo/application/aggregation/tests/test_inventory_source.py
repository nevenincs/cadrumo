"""Inventory resolver boundary tests for registry-owned row templates.

The inventory boundary restores the displaced encrypted success, absence,
corruption, conflict, fingerprint/tamper, determinism, and multi-activity
cohort matrix once runtime activity-row expansion exists. It must fail closed
without reading storage.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, get_args

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from ....adapters.persistence.profile.inventory import InventoryLedgerRepository
from ....adapters.persistence.storage.secure_object_namespaces import PROFILE_INVENTORY_LEDGER_NAMESPACE
from ....adapters.persistence.storage.sql import SecureObjectRow
from ....adapters.persistence.storage.sql.engine import get_engine
from ....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.inventory_bindings import InventoryProjectionOperation, InventorySelector
from ....domain.calculations.registry.schema import DataBindingDefinition, ModeloRevision
from ....domain.contribuyente.inventory.records import (
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
    fingerprint_prior_authoritative_closing,
)
from ....domain.contribuyente.inventory.valuation import compute_inventory_anexo_d_projection
from ....domain.filing_evidence import FilingEvidenceReference
from ....tests.secure_sql import isolated_runtime_profile, mutate_encrypted_secure_object_json
from .._inventory import _VALUE_ATTRIBUTE_BY_OPERATION, InventorySourceResolver
from .._source_mesh import CalculationSourceContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _InventoryLedgerRepositoryScenario:
    def __init__(self, document: InventoryLedgerDocument | None = None, *, error: bool = False) -> None:
        self.loads = 0
        self.document = document or InventoryLedgerDocument(ledgers=())
        self.error = error

    def load(self) -> InventoryLedgerDocument:
        self.loads += 1
        if self.error:
            raise InventoryLedgerError("sensitive storage detail")
        return self.document


def _ref(value: str) -> FilingEvidenceReference:
    return FilingEvidenceReference(reference=value)


def _ledger(actividad_id: str, *, physical_closing: Decimal | None = None) -> InventoryLedger:
    continuity = (PriorClosingContinuityEvidence(reference=_ref(f"prior-{actividad_id}"), content_digest="f" * 64),)
    acquisition = InventoryAcquisitionCost(
        consideration_excluding_iva=Decimal("100.00"),
        consideration_iva_amount=Decimal("21.00"),
        consideration_deductible_iva_ratio=Decimal("1"),
        attributable_cost_components=(),
        evidence=(
            InventoryAcquisitionEvidence(
                reference=_ref(f"invoice-{actividad_id}"),
                evidence_kind=InventoryAcquisitionEvidenceKind.PURCHASE_INVOICE,
                content_digest="a" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(f"cost-{actividad_id}"),
                evidence_kind=InventoryAcquisitionEvidenceKind.ATTRIBUTABLE_COST_REVIEW,
                content_digest="b" * 64,
            ),
            InventoryAcquisitionEvidence(
                reference=_ref(f"iva-{actividad_id}"),
                evidence_kind=InventoryAcquisitionEvidenceKind.IVA_RECOVERABILITY_REVIEW,
                content_digest="c" * 64,
            ),
        ),
        completeness=InventoryAcquisitionCompleteness(
            consideration_evidence=_ref(f"invoice-{actividad_id}"),
            attributable_cost_review_evidence=_ref(f"cost-{actividad_id}"),
            iva_recoverability_review_evidence=_ref(f"iva-{actividad_id}"),
        ),
        directly_attributable_cost_total=Decimal("0.00"),
        nonrecoverable_iva_included=Decimal("0.00"),
        recoverable_iva_excluded=Decimal("21.00"),
        total_acquisition_cost=Decimal("100.00"),
    )
    movement = MovementRecord.from_purchase_acquisition(
        movement_id=f"purchase-{actividad_id}",
        movement_date=date(2025, 2, 1),
        quantity=Decimal("1"),
        acquisition_cost=acquisition,
    )
    observation = None
    if physical_closing is not None:
        observation = PhysicalClosingObservation(
            observation_id=f"physical-{actividad_id}",
            observed_on=date(2026, 1, 1),
            as_of_date=date(2025, 12, 31),
            actividad_id=actividad_id,
            filing_year=2025,
            closing_value=physical_closing,
            valuation_basis=InventoryClosingValuationBasis.FIFO_ACQUISITION_PRICE,
            evidence=(
                PhysicalClosingEvidence(
                    reference=_ref(f"count-{actividad_id}"),
                    role=PhysicalClosingEvidenceRole.PHYSICAL_COUNT,
                    content_digest="1" * 64,
                ),
                PhysicalClosingEvidence(
                    reference=_ref(f"value-{actividad_id}"),
                    role=PhysicalClosingEvidenceRole.ACQUISITION_PRICE_VALUATION,
                    content_digest="2" * 64,
                ),
            ),
        )
    decision = InventoryClosingAuthorityDecision(
        decision_id=f"decision-{actividad_id}",
        actividad_id=actividad_id,
        filing_year=2025,
        authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
        physical_observation_id=None if observation is None else observation.observation_id,
        physical_observation_fingerprint=None if observation is None else observation.fingerprint,
        reason="Reviewed movement authority.",
        actor="reviewer-secret",
        source_command="inventory-secret-command",
        decided_at=datetime(2026, 1, 2, tzinfo=UTC),
        evidence=(
            InventoryClosingDecisionEvidence(
                reference=_ref(f"decision-{actividad_id}"),
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
    return InventoryLedger(
        actividad_id=actividad_id,
        year=2025,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal("100.00"),
        period_movements=(movement,),
        closing_authority_record=record,
    )


def _binding(operation: InventoryProjectionOperation, target: str) -> DataBindingDefinition:
    return DataBindingDefinition(
        id=f"inventory-{target}",
        source=BindingSourceKind.INVENTORY,
        selector={
            "modelo": "100",
            "filing_year": 2025,
            "projection_grain": "taxpayer_year_activity",
            "fact": "row_field",
            "record": "inventory_activity",
            "grouping": "per_inventory_activity",
            "row_field": operation,
            "target_casilla_id": target,
        },
        aggregation=BindingAggregation(op=BindingAggregationOp.ROWS),
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
    )


def _revision(*, inventory: bool) -> ModeloRevision:
    base = bundled_authority().snapshot("100", filing_year=2025, period="0A").revision
    bindings = (
        (
            _binding("complete_acquisition_cost", "0181"),
            _binding("closing_minus_opening_positive", "0177"),
            _binding("opening_minus_closing_positive", "0182"),
        )
        if inventory
        else ()
    )
    return base.model_copy(update={"bindings": bindings})


def _context(revision: ModeloRevision, *, year: int = 2025) -> CalculationSourceContext:
    return CalculationSourceContext(
        bucket_id="operator",
        modelo="100",
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        revision=revision,
    )


def test_inventory_operation_adapter_tracks_the_canonical_row_field_vocabulary() -> None:
    annotation = InventorySelector.model_fields["row_field"].annotation
    operations = set(get_args(getattr(annotation, "__value__", annotation)))

    assert operations == set(_VALUE_ATTRIBUTE_BY_OPERATION)
    assert operations == {
        "complete_acquisition_cost",
        "closing_minus_opening_positive",
        "opening_minus_closing_positive",
    }


def test_no_inventory_binding_is_allocation_and_repository_read_free() -> None:
    repository = _InventoryLedgerRepositoryScenario()

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=False)))

    assert repository.loads == 0
    assert result.binding_values == {}
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert result.unresolved_binding_ids == ()
    assert result.diagnostics == ()
    assert result.provenance == ()


def test_inventory_row_templates_expand_complete_activities_in_canonical_rows() -> None:
    alpha = _ledger("alpha")
    zeta = _ledger("zeta")
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(zeta, alpha)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

    assert repository.loads == 1
    assert result.binding_values == {}
    assert result.row_binding_values == {
        ("inventory-0177", 1): Decimal("100.00"),
        ("inventory-0181", 1): Decimal("100.00"),
        ("inventory-0182", 1): Decimal("0.00"),
        ("inventory-0177", 2): Decimal("100.00"),
        ("inventory-0181", 2): Decimal("100.00"),
        ("inventory-0182", 2): Decimal("0.00"),
    }
    assert result.unresolved_binding_ids == ()
    assert result.provenance == ()
    assert result.diagnostics == ()
    for binding_id in ("inventory-0177", "inventory-0181", "inventory-0182"):
        assert result.row_source_identities[(binding_id, 1)].source_row_identity == "alpha"
        assert result.row_source_identities[(binding_id, 2)].source_row_identity == "zeta"
        assert (
            result.row_source_identities[(binding_id, 1)].fingerprint
            == compute_inventory_anexo_d_projection(alpha).projection_fingerprint
        )
    assert len({item.fingerprint for key, item in result.row_source_identities.items() if key[1] == 1}) == 1
    assert len({item.fingerprint for key, item in result.row_source_identities.items() if key[1] == 2}) == 1
    public = f"{result!r} {result.model_dump()!r} {result.model_dump_json()}"
    assert "alpha" not in public
    assert "zeta" not in public


def test_inventory_activity_order_is_insertion_invariant_and_semantic_change_changes_fingerprint() -> None:
    alpha = _ledger("alpha")
    zeta = _ledger("zeta")
    forward = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(alpha, zeta)))
    ).resolve(_context(_revision(inventory=True)))
    reverse = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(zeta, alpha)))
    ).resolve(_context(_revision(inventory=True)))
    changed_movement = alpha.period_movements[0].model_copy(update={"movement_date": date(2025, 3, 1)})
    changed = InventoryLedger.model_validate(alpha.model_copy(update={"period_movements": (changed_movement,)}))
    mutated = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(changed, zeta)))
    ).resolve(_context(_revision(inventory=True)))

    assert forward.row_binding_values == reverse.row_binding_values == mutated.row_binding_values
    assert forward.row_source_identities == reverse.row_source_identities
    assert (
        forward.row_source_identities[("inventory-0181", 1)].fingerprint
        != mutated.row_source_identities[("inventory-0181", 1)].fingerprint
    )


def test_inventory_conflict_is_safe_per_activity_advisory() -> None:
    ledger = _ledger("secret-activity", physical_closing=Decimal("250.00"))
    result = InventorySourceResolver(
        inventory_repository=_InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(ledger,)))
    ).resolve(_context(_revision(inventory=True)))

    assert result.row_binding_values[("inventory-0177", 1)] == Decimal("100.00")
    assert result.diagnostics[0].reason == "source_issue"
    rendered = f"{result.diagnostics!r} {result.diagnostics[0].message}"
    assert "secret-activity" not in rendered
    assert "250.00" not in rendered


@pytest.mark.parametrize("kind", ["missing", "unreadable", "incomplete"])
def test_inventory_failure_is_atomic_value_free_and_loads_once(kind: str) -> None:
    if kind == "missing":
        repository = _InventoryLedgerRepositoryScenario()
    elif kind == "unreadable":
        repository = _InventoryLedgerRepositoryScenario(error=True)
    else:
        ledger = _ledger("secret-activity").model_copy(update={"closing_authority_record": None})
        repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument.model_construct(ledgers=(ledger,)))
    result = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

    assert repository.loads == 1
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert set(result.unresolved_binding_ids) == {"inventory-0177", "inventory-0181", "inventory-0182"}
    rendered = f"{result!r} {result.model_dump()!r}"
    for canary in ("secret-activity", "100.00", "reviewer-secret", "inventory-secret-command", "a" * 64):
        assert canary not in rendered


@pytest.mark.parametrize("actividad_id", [" alpha", "alpha ", "alpha\ncontrol"])
def test_inventory_ledger_refuses_noncanonical_activity_identity(actividad_id: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        _ledger("alpha").model_copy(update={"actividad_id": actividad_id}).model_dump_json()
        InventoryLedger.model_validate(
            _ledger("alpha").model_copy(update={"actividad_id": actividad_id}).model_dump(),
        )
    assert actividad_id not in str(exc_info.value)


def test_real_encrypted_multi_activity_success_absence_conflict_and_corruption(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    bucket_id = "00000000-0000-4000-8000-000000000176"
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=bucket_id) as runtime:
        repository = InventoryLedgerRepository(objects=runtime.repository)
        absent = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))
        alpha = _ledger("alpha", physical_closing=Decimal("250.00"))
        zeta = _ledger("zeta")
        repository.save(InventoryLedgerDocument(ledgers=(zeta, alpha)))
        complete = InventorySourceResolver(inventory_repository=repository).resolve(_context(_revision(inventory=True)))

        statement = select(SecureObjectRow).where(
            SecureObjectRow.namespace == PROFILE_INVENTORY_LEDGER_NAMESPACE.namespace,
            SecureObjectRow.object_key == PROFILE_INVENTORY_LEDGER_NAMESPACE.require_default_object_key(),
        )

        def orphan_authority(document: dict[str, Any]) -> None:
            ledgers = document["ledgers"]
            assert isinstance(ledgers, list) and isinstance(ledgers[0], dict)
            assert "zeta" in repr(ledgers)
            ledgers[0]["closing_authority_record"]["decision"]["actividad_id"] = "other"

        mutate_encrypted_secure_object_json(
            get_engine(runtime.settings),
            row_statement=statement,
            mutate=orphan_authority,
        )
        corrupted = InventorySourceResolver(inventory_repository=repository).resolve(
            _context(_revision(inventory=True))
        )

    assert absent.row_binding_values == {}
    assert absent.diagnostics[0].reason == "source_domain_not_ready"
    assert complete.row_binding_values[("inventory-0181", 1)] == Decimal("100.00")
    assert complete.row_source_identities[("inventory-0181", 1)].source_row_identity == "alpha"
    assert complete.diagnostics[0].reason == "source_issue"
    assert corrupted.row_binding_values == {}
    assert corrupted.diagnostics[0].reason == "storage_degraded"
    rendered = f"{corrupted!r} {corrupted.model_dump()!r} {caplog.text}"
    for canary in ("alpha", "zeta", "250.00", "reviewer-secret", "inventory-secret-command", "a" * 64):
        assert canary not in rendered


def test_inventory_row_template_rejects_unsupported_coordinate_without_repository_read() -> None:
    repository = _InventoryLedgerRepositoryScenario()

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(_revision(inventory=True), year=2024),
    )

    assert repository.loads == 0
    assert result.unresolved_binding_ids == ("inventory-0177", "inventory-0181", "inventory-0182")
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].reason == "unhandled_binding_source"
    assert "unsupported_coordinate" in result.diagnostics[0].message


@pytest.mark.parametrize("shape", ["missing", "duplicate"])
def test_inventory_template_cohort_refuses_atomically_before_storage(shape: str) -> None:
    revision = _revision(inventory=True)
    bindings = revision.bindings[:-1] if shape == "missing" else (*revision.bindings, revision.bindings[0])
    repository = _InventoryLedgerRepositoryScenario(InventoryLedgerDocument(ledgers=(_ledger("alpha"),)))

    result = InventorySourceResolver(inventory_repository=repository).resolve(
        _context(revision.model_copy(update={"bindings": bindings})),
    )

    assert repository.loads == 0
    assert result.row_binding_values == {}
    assert result.row_source_identities == {}
    assert result.diagnostics[0].reason == "unresolved_derived_binding"
