"""In-memory register doors that answer with the registered operations' own projections.

Each door keeps a synthetic register and answers every request with the real
public result model the registered operation publishes, including its typed
refusal arm, so the screens are driven by the same request and result
contracts the runtime doors carry. Figures the operations derive (definitive
percentages, deductions, valuations) are fixed synthetic values chosen by the
test, never computed here. Every identifier and amount is synthetic.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from .....application.bienes_inversion.registered_requests import (
    BienesInversionDeclareRequest,
    BienesInversionListRequest,
)
from .....application.bienes_inversion.registered_result_contracts import (
    BienesInversionDeclareProjection,
    BienesInversionListProjection,
    BienesInversionRefusalProjection,
    BienInversionDisposalProjection,
    BienInversionRecordProjection,
)
from .....application.inventory.registered_evidence_operation import (
    InventoryEvidenceAddProjection,
    InventoryEvidenceAddRequest,
)
from .....application.inventory.registered_projections import (
    InventoryClosingAuthorityOperationProjection,
    InventoryClosingAuthorityRecordProjection,
    InventoryCreateProjection,
    InventoryInspectProjection,
    InventoryLedgerChangeProjection,
    InventoryLedgerProjection,
    InventoryListProjection,
    InventoryListRowProjection,
    InventoryMovementAddProjection,
    InventoryMovementProjection,
    InventoryReasonFact,
    InventoryRefusalProjection,
    InventoryValuationOperationProjection,
    InventoryValuationPreviewProjection,
)
from .....application.inventory.registered_requests import (
    InventoryAcquisitionCostRequest,
    InventoryClosingAuthorityRecordInput,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueFactsInput,
    InventoryClosingValueRecordRequest,
    InventoryCreateRequest,
    InventoryInspectRequest,
    InventoryLedgerChangeRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from .....application.operations.public_scalar import PublicDecimal
from .....application.prorrata_register.operation_requests import (
    ProrrataDeclareSectorRequest,
    ProrrataElectEspecialRequest,
    ProrrataElectGeneralRequest,
    ProrrataListRequest,
    ProrrataOperationId,
    ProrrataRevokeEspecialRequest,
    ProrrataSeedRequest,
    ProrrataSeedSectorRequest,
    ProrrataSettleSectorRequest,
)
from .....application.prorrata_register.projection_contracts import (
    ProrrataEntryProjection,
    ProrrataEspecialTransitionProjection,
    ProrrataListProjection,
    ProrrataMutationProjection,
    ProrrataRefusalProjection,
    ProrrataSectorDefinitionProjection,
    ProrrataSeedSourceProjection,
)
from .....domain.contribuyente.inventory.closing_authority_records import (
    InventoryClosingAuthorityDecision,
    InventoryClosingAuthorityRecord,
    PriorAuthoritativeClosingLink,
)
from .....domain.contribuyente.inventory.closing_foundations import (
    InventoryClosingAuthority,
    InventoryClosingDecisionEvidence,
    InventoryClosingDecisionEvidenceRole,
    PriorClosingContinuityEvidence,
    fingerprint_prior_authoritative_closing,
)
from .....domain.contribuyente.inventory.records import InventoryAcquisitionCost, ValuationMethod
from .....domain.filing_evidence import FilingEvidenceReference
from ...account import AccountSessionExpiredError
from ..registers_prorrata import ProrrataMutationRequestV1

REGISTERS_PROFILE_ID = UUID("5aa00000-0000-4000-8000-0000000000d5")
SYNTHETIC_AUTHORITY_PATH = "synthetic-closing-authority.json"
SYNTHETIC_PURCHASE_PATH = "synthetic-purchase-cost.json"
SYNTHETIC_CLOSING_FACTS_PATH = "synthetic-closing-facts.json"

_SYNTHETIC_ACQUISITION = json.dumps(
    {
        "consideration_excluding_iva": "55.00",
        "consideration_iva_amount": "11.55",
        "consideration_deductible_iva_ratio": "1.00",
        "attributable_cost_components": [],
        "evidence": [
            {
                "reference": {"reference": "synthetic-invoice-ref"},
                "evidence_kind": "purchase_invoice",
                "content_digest": "a" * 64,
            },
            {
                "reference": {"reference": "synthetic-cost-review-ref"},
                "evidence_kind": "attributable_cost_review",
                "content_digest": "b" * 64,
            },
            {
                "reference": {"reference": "synthetic-iva-review-ref"},
                "evidence_kind": "iva_recoverability_review",
                "content_digest": "c" * 64,
            },
        ],
        "completeness": {
            "consideration_evidence": {"reference": "synthetic-invoice-ref"},
            "attributable_cost_review_evidence": {"reference": "synthetic-cost-review-ref"},
            "iva_recoverability_review_evidence": {"reference": "synthetic-iva-review-ref"},
        },
        "directly_attributable_cost_total": "0.00",
        "nonrecoverable_iva_included": "0.00",
        "recoverable_iva_excluded": "11.55",
        "total_acquisition_cost": "55.00",
    }
)


def synthetic_acquisition_cost() -> InventoryAcquisitionCost:
    """A complete synthetic purchase cost the canonical model accepts."""
    return InventoryAcquisitionCost.model_validate_json(_SYNTHETIC_ACQUISITION)


def synthetic_closing_value_facts() -> InventoryClosingValueFactsInput:
    """Plain movement-derived closing facts carrying no fingerprint of their own."""
    return InventoryClosingValueFactsInput(
        decision_id="decision-1",
        decided_at=datetime(2026, 1, 2, tzinfo=UTC),
        authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
        reason="Synthetic reviewed movement-derived closing.",
        decision_evidence=(
            InventoryClosingDecisionEvidence(
                reference=FilingEvidenceReference(reference="decision-evidence"),
                role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                content_digest="e" * 64,
            ),
        ),
        prior_evidence=(
            PriorClosingContinuityEvidence(
                reference=FilingEvidenceReference(reference="prior-closing-evidence"),
                content_digest="f" * 64,
            ),
        ),
    )


def synthetic_closing_authority(actividad_id: str, year: int) -> InventoryClosingAuthorityRecord:
    """A complete synthetic movement-derived closing authority the canonical model accepts."""
    continuity = (
        PriorClosingContinuityEvidence(
            reference=FilingEvidenceReference(reference=f"{actividad_id}-prior-ref"),
            content_digest="f" * 64,
        ),
    )
    return InventoryClosingAuthorityRecord(
        decision=InventoryClosingAuthorityDecision(
            decision_id=f"decision-{actividad_id}-{year}",
            actividad_id=actividad_id,
            filing_year=year,
            authority=InventoryClosingAuthority.MOVEMENT_DERIVED,
            reason="Synthetic reviewed movement-derived closing.",
            actor="synthetic-operator",
            source_command="inventory.closing.authority.decide",
            decided_at=datetime(year + 1, 1, 2, tzinfo=UTC),
            evidence=(
                InventoryClosingDecisionEvidence(
                    reference=FilingEvidenceReference(reference=f"{actividad_id}-decision-ref"),
                    role=InventoryClosingDecisionEvidenceRole.AUTHORITY_RECONCILIATION,
                    content_digest="e" * 64,
                ),
            ),
        ),
        prior_closing_link=PriorAuthoritativeClosingLink(
            actividad_id=actividad_id,
            current_filing_year=year,
            prior_filing_year=year - 1,
            prior_authoritative_closing_value=Decimal("100.00"),
            current_opening_value=Decimal("100.00"),
            prior_authoritative_source_fingerprint="c" * 64,
            prior_authoritative_closing_fingerprint=fingerprint_prior_authoritative_closing(
                actividad_id=actividad_id,
                filing_year=year - 1,
                authoritative_closing_value=Decimal("100.00"),
                authoritative_source_fingerprint="c" * 64,
                evidence=continuity,
            ),
            evidence=continuity,
        ),
    )


def _decimal(text: str) -> PublicDecimal:
    return PublicDecimal(decimal=text)


def synthetic_prorrata_entry(
    ejercicio: int,
    *,
    sector_id: str | None = None,
    regime: str = "general",
    provisional: str | None = "80",
    definitive: str | None = None,
) -> ProrrataEntryProjection:
    """One register entry as the list operation projects it."""
    return ProrrataEntryProjection(
        ejercicio=ejercicio,
        regime=regime,
        especial_transition=None,
        sector_id=sector_id,
        interrupted=False,
        provisional_percentage=None if provisional is None else _decimal(provisional),
        provisional_provenance="synthetic_operator_estimate" if provisional is not None else None,
        authorisation_reference=None,
        definitive_percentage=None if definitive is None else _decimal(definitive),
        definitive_volume_con_derecho=None,
        definitive_volume_sin_derecho=None,
        source_observation_ref=None,
        source_registry_snapshot_refs=(),
        schema_version="1",
    )


class MemoryProrrataRegisterDoor:
    """A synthetic prorrata register answering with the registered projections."""

    def __init__(
        self,
        entries: tuple[ProrrataEntryProjection, ...] = (),
        sectors: tuple[ProrrataSectorDefinitionProjection, ...] = (),
        *,
        settled_definitive: str = "75",
    ) -> None:
        """Hold the synthetic register and the definitive figure a settlement reports."""
        self.entries: list[ProrrataEntryProjection] = list(entries)
        self.sectors: list[ProrrataSectorDefinitionProjection] = list(sectors)
        self.settled_definitive = settled_definitive
        self.refusal: ProrrataRefusalProjection | None = None
        self.requests: list[object] = []
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile every request names."""
        return REGISTERS_PROFILE_ID

    async def read_register(self, request: ProrrataListRequest) -> ProrrataListProjection:
        """Answer the list operation's projection of the whole register."""
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()
        return ProrrataListProjection(
            profile_id=request.profile_id,
            entries=tuple(self.entries),
            sectors=tuple(self.sectors),
            count=len(self.entries),
        )

    def _put(self, entry: ProrrataEntryProjection) -> ProrrataEntryProjection:
        self.entries = [
            item for item in self.entries if (item.ejercicio, item.sector_id) != (entry.ejercicio, entry.sector_id)
        ]
        self.entries.append(entry)
        self.entries.sort(key=lambda item: (item.ejercicio, item.sector_id or ""))
        return entry

    async def apply(self, request: ProrrataMutationRequestV1) -> ProrrataMutationProjection:
        """Answer one change with its mutation projection, or the refusal the test armed."""
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()
        operation_id = _PRORRATA_OPERATIONS[type(request)]
        if self.refusal is not None:
            return ProrrataMutationProjection(
                operation_id=operation_id, profile_id=request.profile_id, outcome="refused", refusal=self.refusal
            )
        if isinstance(request, ProrrataDeclareSectorRequest):
            sector = ProrrataSectorDefinitionProjection(
                sector_id=request.sector_id, letra=request.letra, member_activity_codes=request.member_activity_codes
            )
            self.sectors = [item for item in self.sectors if item.sector_id != sector.sector_id] + [sector]
            return ProrrataMutationProjection(
                operation_id=operation_id,
                profile_id=request.profile_id,
                outcome="success",
                sector_definition=sector,
                count=len(self.entries),
            )
        entry = self._put(self._entry_for(request))
        seed_source = None
        if isinstance(request, ProrrataSeedRequest):
            seed_source = ProrrataSeedSourceProjection(
                modelo="303",
                filing_year=request.ejercicio - 1,
                period="4T",
                casilla_id="iva.prorrata-porcentaje",
                stamped_revision_id="synthetic-revision",
            )
        return ProrrataMutationProjection(
            operation_id=operation_id,
            profile_id=request.profile_id,
            outcome="success",
            entry=entry,
            seed_source=seed_source,
            prior_ejercicio=request.ejercicio - 1 if isinstance(request, ProrrataSeedSectorRequest) else None,
            count=len(self.entries),
        )

    def _entry_for(self, request: ProrrataMutationRequestV1) -> ProrrataEntryProjection:
        if isinstance(request, ProrrataSeedRequest):
            return synthetic_prorrata_entry(request.ejercicio, provisional="87.25")
        if isinstance(request, ProrrataSeedSectorRequest):
            return synthetic_prorrata_entry(request.ejercicio, sector_id=request.sector_id, provisional="70")
        if isinstance(request, ProrrataSettleSectorRequest):
            return synthetic_prorrata_entry(
                request.ejercicio, sector_id=request.sector_id, definitive=self.settled_definitive
            )
        if isinstance(request, ProrrataDeclareSectorRequest):
            raise TypeError("a sector declaration carries no entry")
        transition = None
        if isinstance(request, ProrrataElectEspecialRequest | ProrrataRevokeEspecialRequest) and (
            request.evidence_reference is not None
        ):
            kind = "opcion" if isinstance(request, ProrrataElectEspecialRequest) else "revocacion"
            transition = ProrrataEspecialTransitionProjection(kind=kind, evidence_reference=request.evidence_reference)
        regime = "especial" if isinstance(request, ProrrataElectEspecialRequest) else "general"
        entry = ProrrataEntryProjection(
            ejercicio=request.ejercicio,
            regime=regime,
            especial_transition=transition,
            sector_id=request.sector_id,
            interrupted=False,
            provisional_percentage=request.percentage,
            provisional_provenance=request.provenance,
            authorisation_reference=request.reference,
            definitive_percentage=None,
            definitive_volume_con_derecho=None,
            definitive_volume_sin_derecho=None,
            source_observation_ref=None,
            source_registry_snapshot_refs=(),
            schema_version="1",
        )
        return entry


_PRORRATA_OPERATIONS: dict[type[BaseModel], ProrrataOperationId] = {
    ProrrataDeclareSectorRequest: "declare_sector",
    ProrrataElectGeneralRequest: "elect_general",
    ProrrataElectEspecialRequest: "elect_especial",
    ProrrataRevokeEspecialRequest: "revoke_especial",
    ProrrataSeedRequest: "seed",
    ProrrataSeedSectorRequest: "seed_sector",
    ProrrataSettleSectorRequest: "settle_sector",
}


def synthetic_capital_good(identifier: str, *, year: int = 2024) -> BienInversionRecordProjection:
    """One declared capital good as the list operation projects it."""
    return BienInversionRecordProjection(
        identifier=identifier,
        description=f"Synthetic good {identifier}",
        acquisition_year=year,
        cuota_soportada=_decimal("2100.00"),
        prorrata_inicial_pct=_decimal("80"),
        kind="synthetic_kind",
        art108_elegible=True,
        acquisition_ledger_id=f"tx-{identifier}",
        prorrata_sector_id=None,
        disposal=None,
        deduccion_efectuada=_decimal("1680.00"),
        schema_version="1",
    )


class MemoryCapitalGoodsDoor:
    """A synthetic capital-goods register answering with the registered projections."""

    def __init__(self, records: tuple[BienInversionRecordProjection, ...] = (), *, deduction: str = "1680.00") -> None:
        """Hold the synthetic register and the deduction a declaration reports."""
        self.records: list[BienInversionRecordProjection] = list(records)
        self.deduction = deduction
        self.requests: list[object] = []
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile every request names."""
        return REGISTERS_PROFILE_ID

    async def read_register(self, request: BienesInversionListRequest) -> BienesInversionListProjection:
        """Answer the list operation's projection of the whole register."""
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()
        return BienesInversionListProjection(profile_id=request.profile_id, rows=tuple(self.records))

    async def declare(self, request: BienesInversionDeclareRequest) -> BienesInversionDeclareProjection:
        """Declare one good, refusing a duplicate identifier as the register does."""
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()
        if any(record.identifier == request.identifier for record in self.records):
            return BienesInversionDeclareProjection(
                outcome="refused",
                profile_id=request.profile_id,
                refusal=BienesInversionRefusalProjection(
                    code="REFUSED_PROFILE_BIENES_INVERSION_VALIDATION",
                    reason="duplicate_identifier",
                    identifier=request.identifier,
                ),
            )
        disposal = (
            None
            if request.disposal_year is None or request.disposal_regime is None
            else BienInversionDisposalProjection(year=request.disposal_year, regime=request.disposal_regime)
        )
        record = BienInversionRecordProjection(
            identifier=request.identifier,
            description=request.description,
            acquisition_year=request.acquisition_year,
            cuota_soportada=request.cuota_soportada,
            prorrata_inicial_pct=request.prorrata_inicial_pct,
            kind=request.kind,
            art108_elegible=request.art108_elegible,
            acquisition_ledger_id=request.acquisition_ledger_id,
            prorrata_sector_id=request.prorrata_sector_id,
            disposal=disposal,
            deduccion_efectuada=_decimal(self.deduction),
            schema_version="1",
        )
        self.records.append(record)
        return BienesInversionDeclareProjection(
            outcome="declared", profile_id=request.profile_id, record=record, count=len(self.records)
        )


def synthetic_inventory_row(actividad_id: str, year: int = 2026) -> InventoryListRowProjection:
    """One activity inventory as the list operation projects it."""
    return InventoryListRowProjection(
        actividad_id=actividad_id,
        year=year,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=_decimal("0"),
        movement_count=0,
    )


class MemoryInventoryDoor:
    """Synthetic activity inventories answering with the registered projections."""

    def __init__(
        self,
        rows: tuple[InventoryListRowProjection, ...] = (),
        *,
        closing_value: str = "155.00",
        cogs: str = "45.00",
    ) -> None:
        """Hold the synthetic inventories and the valuation figures a preview reports."""
        self.rows: list[InventoryListRowProjection] = list(rows)
        self.movements: dict[tuple[str, int], list[InventoryMovementProjection]] = {}
        self.corrections: set[str] = set()
        self.closing_value = closing_value
        self.cogs = cogs
        self.requests: list[object] = []
        self.expired = False

    @property
    def profile_id(self) -> UUID:
        """The synthetic profile every request names."""
        return REGISTERS_PROFILE_ID

    def _check(self, request: object) -> None:
        self.requests.append(request)
        if self.expired:
            raise AccountSessionExpiredError()

    def _row(self, actividad_id: str, year: int) -> InventoryListRowProjection | None:
        for row in self.rows:
            if row.actividad_id == actividad_id and row.year == year:
                return row
        return None

    def _ledger(self, row: InventoryListRowProjection) -> InventoryLedgerProjection:
        return InventoryLedgerProjection(
            actividad_id=row.actividad_id,
            year=row.year,
            valuation_method=row.valuation_method,
            opening_stock=row.opening_stock,
            opening_layers=(),
            closing_authority_fingerprints=None,
            period_movements=tuple(self.movements.get((row.actividad_id, row.year), ())),
            schema_version="1",
            bucket_event_ids=("event-1",),
            retired=row.retired,
            retirement_reason=row.retirement_reason,
        )

    @staticmethod
    def _not_found(actividad_id: str, year: int) -> InventoryRefusalProjection:
        return InventoryRefusalProjection(
            code="REFUSED_INVENTORY_ACTIVIDAD_NOT_FOUND",
            reason="activity_not_found",
            actividad_id=actividad_id,
            year=year,
        )

    async def inspect(self, request: InventoryInspectRequest) -> InventoryInspectProjection:
        """Answer one inventory with what it retains."""
        self._check(request)
        row = self._row(request.actividad_id, request.year)
        if row is None:
            return InventoryInspectProjection(
                outcome="refused",
                profile_id=request.profile_id,
                refusal=self._not_found(request.actividad_id, request.year),
            )
        return InventoryInspectProjection(outcome="found", profile_id=request.profile_id, ledger=self._ledger(row))

    async def apply_change(self, request: InventoryLedgerChangeRequest) -> InventoryLedgerChangeProjection:
        """Retire an inventory, replay a seen correction, or refuse a second retirement by its catalogue key."""
        self._check(request)
        row = self._row(request.actividad_id, request.year)
        if row is None:
            return InventoryLedgerChangeProjection(
                outcome="refused",
                profile_id=request.profile_id,
                refusal=self._not_found(request.actividad_id, request.year),
            )
        if request.correction_id in self.corrections:
            return InventoryLedgerChangeProjection(
                outcome="replayed", profile_id=request.profile_id, ledger=self._ledger(row)
            )
        if isinstance(request, InventoryRetireRequest):
            if row.retired:
                return InventoryLedgerChangeProjection(
                    outcome="refused",
                    profile_id=request.profile_id,
                    refusal=InventoryRefusalProjection(
                        code="REFUSED_INVENTORY_SERVICE_INPUT",
                        reason="inventory_already_retired",
                        actividad_id=request.actividad_id,
                        year=request.year,
                        reason_key="application.inventory.service.errors.inventory_already_retired",
                        reason_facts=(
                            InventoryReasonFact(key="actividad_id", value=request.actividad_id),
                            InventoryReasonFact(key="year", value=str(request.year)),
                        ),
                    ),
                )
            position = self.rows.index(row)
            row = row.model_copy(update={"retired": True, "retirement_reason": request.reason})
            self.rows[position] = row
        self.corrections.add(request.correction_id)
        return InventoryLedgerChangeProjection(
            outcome="applied", profile_id=request.profile_id, ledger=self._ledger(row), bucket_event_ids=("event-1",)
        )

    async def read_register(self, request: InventoryListRequest) -> InventoryListProjection:
        """Answer the list operation's projection of every inventory."""
        self._check(request)
        return InventoryListProjection(profile_id=request.profile_id, rows=tuple(self.rows))

    async def create(self, request: InventoryCreateRequest) -> InventoryCreateProjection:
        """Create one inventory, refusing a second one for the same activity and year."""
        self._check(request)
        if self._row(request.actividad_id, request.year) is not None:
            return InventoryCreateProjection(
                outcome="refused",
                profile_id=request.profile_id,
                refusal=InventoryRefusalProjection(
                    code="REFUSED_INVENTORY_ACTIVIDAD_CONFLICT",
                    reason="activity_conflict",
                    actividad_id=request.actividad_id,
                    year=request.year,
                ),
            )
        row = InventoryListRowProjection(
            actividad_id=request.actividad_id,
            year=request.year,
            valuation_method=ValuationMethod(request.valuation_method),
            opening_stock=request.opening_stock,
            movement_count=0,
        )
        self.rows.append(row)
        return InventoryCreateProjection(
            outcome="created", profile_id=request.profile_id, ledger=self._ledger(row), bucket_event_ids=("event-1",)
        )

    async def add_movement(self, request: InventoryMovementAddRequest) -> InventoryMovementAddProjection:
        """Append one movement to an existing inventory."""
        self._check(request)
        row = self._row(request.actividad_id, request.year)
        if row is None:
            return InventoryMovementAddProjection(
                outcome="refused",
                profile_id=request.profile_id,
                refusal=self._not_found(request.actividad_id, request.year),
            )
        movement = InventoryMovementProjection(
            movement_id=request.movement_id,
            movement_date=request.movement_date,
            kind=request.kind,
            sku="default",
            quantity=request.quantity,
            unit_cost=request.unit_cost,
            taxable_base=request.taxable_base,
            iva_rate=_decimal("0"),
            iva_amount=None,
            deductible_iva_ratio=_decimal("1"),
            acquisition_cost=None,
            schema_version="1",
        )
        self.movements.setdefault((row.actividad_id, row.year), []).append(movement)
        updated = row.model_copy(update={"movement_count": row.movement_count + 1})
        self.rows = [updated if item is row else item for item in self.rows]
        return InventoryMovementAddProjection(
            outcome="added", profile_id=request.profile_id, ledger=self._ledger(updated), bucket_event_ids=("event-1",)
        )

    async def preview_valuation(
        self, request: InventoryValuationPreviewRequest
    ) -> InventoryValuationOperationProjection:
        """Report the synthetic valuation figures the test chose for an existing inventory."""
        self._check(request)
        row = self._row(request.actividad_id, request.year)
        if row is None:
            return InventoryValuationOperationProjection(
                outcome="refused", refusal=self._not_found(request.actividad_id, request.year)
            )
        return InventoryValuationOperationProjection(
            outcome="previewed",
            preview=InventoryValuationPreviewProjection(
                profile_id=request.profile_id,
                actividad_id=row.actividad_id,
                year=row.year,
                valuation_method=row.valuation_method,
                derived_closing_value=_decimal(self.closing_value),
                cogs=_decimal(self.cogs),
                bucket_event_ids=("event-2",),
            ),
        )

    async def record_closing_authority(
        self, request: InventoryClosingAuthorityRecordRequest
    ) -> InventoryClosingAuthorityOperationProjection:
        """Record a closing authority for an existing inventory."""
        self._check(request)
        if self._row(request.actividad_id, request.year) is None:
            return InventoryClosingAuthorityOperationProjection(
                outcome="refused", refusal=self._not_found(request.actividad_id, request.year)
            )
        return InventoryClosingAuthorityOperationProjection(
            outcome="recorded",
            record=InventoryClosingAuthorityRecordProjection(
                profile_id=request.profile_id,
                actividad_id=request.actividad_id,
                year=request.year,
                authority_record_fingerprint="d" * 64,
                decision_fingerprint="e" * 64,
                physical_observation_fingerprint=None,
                prior_closing_link_fingerprint="f" * 64,
                changed=True,
            ),
        )

    async def read_acquisition_cost(self, path: str) -> InventoryAcquisitionCostRequest:
        """Answer the synthetic purchase cost for its synthetic path; any other path is unreadable."""
        self.requests.append(path)
        if path != SYNTHETIC_PURCHASE_PATH:
            raise ValueError(f"unreadable: {path}")
        return InventoryAcquisitionCostRequest.from_domain(synthetic_acquisition_cost())

    async def record_closing_value(
        self, request: InventoryClosingValueRecordRequest
    ) -> InventoryClosingAuthorityOperationProjection:
        """Answer a closing value recorded from plain facts as a closing authority is."""
        self._check(request)
        if self._row(request.actividad_id, request.year) is None:
            return InventoryClosingAuthorityOperationProjection(
                outcome="refused", refusal=self._not_found(request.actividad_id, request.year)
            )
        return InventoryClosingAuthorityOperationProjection(
            outcome="recorded",
            record=InventoryClosingAuthorityRecordProjection(
                profile_id=request.profile_id,
                actividad_id=request.actividad_id,
                year=request.year,
                authority_record_fingerprint="a" * 64,
                decision_fingerprint="b" * 64,
                physical_observation_fingerprint=None,
                prior_closing_link_fingerprint="c" * 64,
                changed=True,
            ),
        )

    async def add_evidence(self, request: InventoryEvidenceAddRequest) -> InventoryEvidenceAddProjection:
        """Answer the identity a purchase would name this document by."""
        self.requests.append(request)
        return InventoryEvidenceAddProjection(
            profile_id=request.profile_id,
            reference=f"attachment:{'d' * 64}",
            content_digest="d" * 64,
        )

    async def read_closing_value_facts(self, path: str) -> InventoryClosingValueFactsInput:
        """Answer synthetic closing facts for their synthetic path; any other path is unreadable."""
        self.requests.append(path)
        if path != SYNTHETIC_CLOSING_FACTS_PATH:
            raise ValueError(f"unreadable: {path}")
        return synthetic_closing_value_facts()

    async def read_closing_authority(self, path: str) -> InventoryClosingAuthorityRecordInput:
        """Answer the synthetic closing authority for its synthetic path; any other path is unreadable."""
        self.requests.append(path)
        if path != SYNTHETIC_AUTHORITY_PATH:
            raise ValueError(f"unreadable: {path}")
        return InventoryClosingAuthorityRecordInput.from_domain(synthetic_closing_authority("act-01", 2026))


__all__ = [
    "REGISTERS_PROFILE_ID",
    "SYNTHETIC_AUTHORITY_PATH",
    "SYNTHETIC_PURCHASE_PATH",
    "MemoryCapitalGoodsDoor",
    "MemoryInventoryDoor",
    "MemoryProrrataRegisterDoor",
    "synthetic_acquisition_cost",
    "synthetic_capital_good",
    "synthetic_closing_authority",
    "synthetic_inventory_row",
    "synthetic_prorrata_entry",
]
