"""Inventory form reads, attachment custody and closing facts through the real supervisor."""

from __future__ import annotations

from decimal import Decimal

from ...adapters.persistence.profile.tests.inventory_purchase_claim_support import (
    YEAR,
    ledger_row_of,
    purchase_movement,
)
from ...adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...application.bucket_event_repository import bucket_event_history_repository
from ...application.inventory.registered_claim_candidates_operation import (
    InventoryClaimCandidatesProjection,
    InventoryClaimCandidatesRequest,
)
from ...application.inventory.registered_evidence_operation import (
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from ...application.inventory.registered_options_operation import (
    INVENTORY_OPTION_FAMILIES,
    InventoryOptionsProjection,
    InventoryOptionsRequest,
)
from ...application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryLedgerChangeProjection,
)
from ...application.inventory.registered_requests import (
    InventoryClosingValueFactsInput,
    InventoryClosingValueRecordRequest,
    InventoryMovementClaimRequest,
)
from ...application.inventory.service import InventoryService
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
)
from ...domain.contribuyente.inventory.records import PurchaseLedgerRow
from ...domain.filing_evidence import FilingEvidenceReference
from ...domain.transactions.models import TransactionCatalogue
from ..adapter_composition_ports import build_inventory_service_ports
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile = str(context.profile_id)
    definition_id = context.definition.definition_id
    subject = profile_operation_subject(profile)
    repository = build_inventory_service_ports(bucket_id=profile).inventory_repository_factory(profile)
    before = repository.load()
    events = bucket_event_history_repository(bucket_id=profile)
    events_before = events.load()
    if definition_id == "ledger.inventory.options":

        def verify_options(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(InventoryOptionsProjection)
            assert result.profile_id == context.profile_id
            families = {family.family: family.options for family in result.families}
            assert {family: tuple(option.value for option in options) for family, options in families.items()} == {
                family: tuple(member.value for member in members) for family, members in INVENTORY_OPTION_FAMILIES
            }
            for family, options in families.items():
                assert options and len({option.value for option in options}) == len(options)
                assert all(
                    option.label_key == f"application.inventory.labels.{family}.{option.value}" for option in options
                )
            assert repository.load() == before
            assert events.load() == events_before

        return ConformancePreparation(
            subject, InventoryOptionsRequest(profile_id=context.profile_id), verify=verify_options
        )

    if definition_id == "ledger.inventory.evidence.add":
        source = context.input_root / "inventory-purchase.pdf"
        payload = b"%PDF-1.4\n% inventory purchase custody conformance\n%%EOF\n"
        source.write_bytes(payload)
        digest = sha256_hex(payload)

        def verify_evidence(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(InventoryEvidenceAddProjection)
            assert result.profile_id == context.profile_id
            assert result.content_digest == digest
            assert result.reference == f"document-{digest}"
            store = AttachmentStore(bucket_id=profile)
            assert store.read_bytes(digest) == payload
            assert store.load_manifest(digest).bucket_id == profile
            assert repository.load() == before

        return ConformancePreparation(
            subject,
            InventoryEvidenceAddRequest(
                profile_id=context.profile_id, source_path=str(source), source_directory=str(context.input_root)
            ),
            verify=verify_evidence,
        )

    if definition_id == "ledger.inventory.movement.claim-candidates":
        offered = ledger_row_of("conformance-equal")
        TransactionCatalogueRepository(bucket_id=profile, objects=secure_object_repository_for_bucket(profile)).save(
            TransactionCatalogue.from_transactions([offered, ledger_row_of("conformance-other", base=Decimal("1.00"))])
        )
        seeding = InventoryService(ports=build_inventory_service_ports(bucket_id=profile))
        seeding.create(
            bucket_id=profile,
            actividad_id="inventory-claim-candidates",
            year=YEAR,
            valuation_method="fifo",
            actor="conformance-seed",
        )
        seeding.movement_add(
            bucket_id=profile,
            actividad_id="inventory-claim-candidates",
            year=YEAR,
            movement=purchase_movement("conformance-purchase", claim=None),
            actor="conformance-seed",
        )
        candidates_events_before = events.load()
        candidates_before = repository.load()

        def verify_candidates(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(InventoryClaimCandidatesProjection)
            assert result.outcome == "listed" and result.profile_id == context.profile_id
            assert [item.transaction_id for item in result.candidates] == [offered.transaction_id]
            assert repository.load() == candidates_before
            assert events.load() == candidates_events_before

        return ConformancePreparation(
            subject,
            InventoryClaimCandidatesRequest(
                profile_id=context.profile_id,
                actividad_id="inventory-claim-candidates",
                year=YEAR,
                movement_id="conformance-purchase",
            ),
            verify=verify_candidates,
        )

    if definition_id == "ledger.inventory.movement.claim":
        claimed = ledger_row_of("conformance-claimed")
        TransactionCatalogueRepository(bucket_id=profile, objects=secure_object_repository_for_bucket(profile)).save(
            TransactionCatalogue.from_transactions([claimed])
        )
        claimant = InventoryService(ports=build_inventory_service_ports(bucket_id=profile))
        claimant.create(
            bucket_id=profile,
            actividad_id="inventory-claim",
            year=YEAR,
            valuation_method="fifo",
            actor="conformance-seed",
        )
        claimant.movement_add(
            bucket_id=profile,
            actividad_id="inventory-claim",
            year=YEAR,
            movement=purchase_movement("conformance-claim", claim=None),
            actor="conformance-seed",
        )
        claim_events_before = events.load()

        def verify_claim(outcome: ConformanceOutcome) -> None:
            result = outcome.resolve_result(InventoryLedgerChangeProjection)
            assert result.outcome == "applied" and result.profile_id == context.profile_id
            assert result.bucket_event_ids
            ledger = claimant.show(bucket_id=profile, actividad_id="inventory-claim", year=YEAR)
            (stored,) = (item for item in ledger.period_movements if item.movement_id == "conformance-claim")
            assert stored.ledger_row is PurchaseLedgerRow.CLAIMED
            assert stored.claimed_transaction_id == claimed.transaction_id
            assert events.load() != claim_events_before

        return ConformancePreparation(
            subject,
            InventoryMovementClaimRequest(
                profile_id=context.profile_id,
                actividad_id="inventory-claim",
                year=YEAR,
                correction_id="conformance-claim-1",
                movement_id="conformance-claim",
                ledger_row=PurchaseLedgerRow.CLAIMED,
                claimed_transaction_id=claimed.transaction_id,
            ),
            verify=verify_claim,
        )

    assert definition_id == "ledger.inventory.closing-value.record"
    service = InventoryService(ports=build_inventory_service_ports(bucket_id=profile))
    actividad_id = "inventory-closing-facts"
    service.create(
        bucket_id=profile,
        actividad_id=actividad_id,
        year=2026,
        valuation_method="fifo",
        opening_stock=Decimal("100.00"),
        actor="conformance-seed",
    )
    closing_events_before = events.load()
    facts = InventoryClosingValueFactsInput(
        decision_id="conformance-closing-2026",
        authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
        reason="Use the evidenced movement book for the closing value.",
        decision_evidence=(
            InventoryClosingDecisionEvidence(
                reference=FilingEvidenceReference(reference="conformance-closing-decision"),
                role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                content_digest="e" * 64,
            ),
        ),
        prior_evidence=(
            PriorClosingContinuityEvidence(
                reference=FilingEvidenceReference(reference="conformance-prior-closing"),
                content_digest="f" * 64,
            ),
        ),
    )

    def verify_closing(outcome: ConformanceOutcome) -> None:
        result = outcome.resolve_result(InventoryClosingAuthorityOperationProjection)
        assert result.outcome == "recorded" and result.record is not None
        assert result.record.profile_id == context.profile_id and result.record.changed
        ledger = service.show(bucket_id=profile, actividad_id=actividad_id, year=2026)
        record = ledger.closing_authority_record
        assert record is not None
        assert record.decision.decision_id == facts.decision_id
        assert record.decision.authority is InventoryClosingAuthority.MOVEMENT_DERIVED
        assert record.decision.evidence == facts.decision_evidence
        assert record.prior_closing_link.evidence == facts.prior_evidence
        assert record.prior_closing_link.current_opening_value == Decimal("100.00")
        assert result.record.authority_record_fingerprint == record.fingerprint
        assert result.record.decision_fingerprint == record.decision.fingerprint
        assert result.record.prior_closing_link_fingerprint == record.prior_closing_link.fingerprint
        assert result.record.physical_observation_fingerprint is None
        assert record.decision.source_command == definition_id
        assert events.load() == closing_events_before

    return ConformancePreparation(
        subject,
        InventoryClosingValueRecordRequest(
            profile_id=context.profile_id, actividad_id=actividad_id, year=2026, facts=facts
        ),
        verify=verify_closing,
    )


INVENTORY_FACTS_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=tuple(
        RegisteredExecutorConformanceCase(definition_id, OperationTerminalCondition.SUCCEEDED, effect, (definition_id,))
        for definition_id, effect in (
            ("ledger.inventory.options", OperationEffect.NONE),
            ("ledger.inventory.movement.claim-candidates", OperationEffect.NONE),
            ("ledger.inventory.movement.claim", OperationEffect.UPDATED),
            ("ledger.inventory.evidence.add", OperationEffect.UPDATED),
            ("ledger.inventory.closing-value.record", OperationEffect.UPDATED),
        )
    ),
    prepare=_prepare,
)
