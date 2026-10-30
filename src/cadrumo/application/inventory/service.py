"""Inventory application service: bucket-scoped CRUD over :class:`InventoryLedger`.

The service persists :class:`InventoryLedgerDocument` and emits events through
the required :class:`InventoryServicePorts` capability bundle. It does not
resolve storage routes or read and write plaintext inventory JSON side stores.
Valuation math remains delegated to :func:`compute_inventory_valuation`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.clock import now as _now_utc
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import emit_bucket_event
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.contribuyente.inventory.closing_authority_records import InventoryClosingAuthorityRecord
from ...domain.contribuyente.inventory.closing_foundations import InventoryLedgerError
from ...domain.contribuyente.inventory.closing_value_facts import (
    InventoryClosingValueFacts,
    build_closing_authority_record,
)
from ...domain.contribuyente.inventory.corrections import (
    INVENTORY_CORRECTION_REFUSAL_REASONS,
    InventoryChangeStamp,
    correct_movement,
    correct_opening,
    describe_ledger,
    inventory_refusal_key,
    restore_ledger,
    retire_ledger,
    reverse_movement,
)
from ...domain.contribuyente.inventory.records import (
    InventoryAcquisitionCost,
    InventoryCorrectionReason,
    InventoryLedger,
    InventoryLedgerDescriptor,
    InventoryLedgerDocument,
    InventoryRetirementReason,
    InventoryValuationResult,
    MovementKind,
    MovementRecord,
    ValuationMethod,
    parse_valuation_method,
)
from ...domain.contribuyente.inventory.valuation import compute_inventory_valuation
from .errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryClosingAuthorityConflictError,
    InventoryServiceInputError,
)
from .ports import InventoryClosingAuthorityWrite, InventoryLedgerServiceRepositoryProtocol, InventoryServicePorts


class InventoryActividadSummary(BaseModel):
    """One row in ``inventory list``.

    The row summarizes actividad, year, :class:`ValuationMethod`, opening
    stock, and movement count without returning the full
    :class:`InventoryLedger`.
    """

    model_config = STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    opening_stock: Decimal = Field(ge=Decimal("0"))
    movement_count: NonNegativeInt
    label: str | None = None
    retired: bool = False
    leaves_year_unresolved: bool = False
    retirement_reason: InventoryRetirementReason | None = None
    correction_count: NonNegativeInt = 0


class InventoryMovementCommand(BaseModel):
    """Strict input shape for ``inventory movement add``.

    The command is projected into a domain :class:`MovementRecord` with a
    closed :class:`MovementKind` before valuation and persistence.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    movement_id: str = Field(min_length=1, max_length=64)
    movement_date: date
    kind: MovementKind
    quantity: Decimal
    unit_cost: Decimal | None = Field(default=None)
    taxable_base: Decimal | None = Field(default=None)
    acquisition_cost: InventoryAcquisitionCost | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _purchase_has_one_cost_authority(self) -> InventoryMovementCommand:
        if self.kind is MovementKind.PURCHASE:
            if self.acquisition_cost is None:
                raise ValueError("purchase movements require acquisition_cost")
            if self.unit_cost is not None or self.taxable_base is not None:
                raise ValueError("purchase movements refuse legacy unit_cost and taxable_base authorities")
        elif self.acquisition_cost is not None:
            raise ValueError("acquisition_cost is permitted only for purchase movements")
        return self


class InventoryValuationPreview(BaseModel):
    """Operator-facing projection of an :class:`InventoryValuationResult`."""

    model_config = STRICT_FROZEN_CONFIG

    actividad_id: str = Field(min_length=1)
    year: int = Field(ge=1900)
    valuation_method: ValuationMethod
    derived_closing_value: Decimal = Field(ge=Decimal("0"))
    cogs: Decimal = Field(ge=Decimal("0"))


class InventoryLedgerResult(BaseModel):
    """Return record from a mutating inventory verb.

    ``ledger`` is the affected :class:`InventoryLedger`; ``bucket_event_ids``
    lists the audit events emitted for the application operation.
    """

    model_config = STRICT_FROZEN_CONFIG

    ledger: InventoryLedger
    bucket_event_ids: tuple[str, ...] = ()
    changed: bool = True


class InventoryValuationPreviewResult(BaseModel):
    """Return record from ``valuation_preview`` plus emitted event id."""

    model_config = STRICT_FROZEN_CONFIG

    preview: InventoryValuationPreview
    bucket_event_ids: tuple[str, ...] = ()


_INVENTORY_EVENT_PAYLOAD_VERSION = 1
_INVENTORY_VALIDATION_TRANSLATION = "errors.refused.refused_profile_inventory_validation"


def _emit_inventory_event(
    *,
    event_repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    actividad_id: str,
    year: int,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> str:
    event = emit_bucket_event(
        repository=event_repository,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.LEDGER_CATALOGUE,
        object_id=f"{actividad_id}:{year}",
        payload=payload,
        payload_version=_INVENTORY_EVENT_PAYLOAD_VERSION,
    )
    return event.event_id


def _find_ledger(document: InventoryLedgerDocument, actividad_id: str, year: int) -> InventoryLedger | None:
    for ledger in document.ledgers:
        if ledger.actividad_id == actividad_id and ledger.year == year:
            return ledger
    return None


_CHANGE_REFUSAL_KEYS = frozenset(
    {
        *(inventory_refusal_key(reason) for reason in INVENTORY_CORRECTION_REFUSAL_REASONS),
        inventory_refusal_key("duplicate_movement_id"),
    }
)


def _refusal_from_change(
    error: InventoryLedgerError | ValidationError,
    *,
    actividad_id: str,
    year: int,
) -> InventoryServiceInputError | InventoryActividadNotFoundError:
    """Name the typed reason of a refused change in this layer's own error."""
    coordinate = {"actividad_id": actividad_id, "year": str(year)}
    if isinstance(error, InventoryLedgerError):
        key = error.translated_message
        if key == "adapters.persistence.profile.inventory.errors.inventory_ledger_not_found":
            return InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.activity_not_found",
                context=coordinate,
            )
        if key in _CHANGE_REFUSAL_KEYS:
            return InventoryServiceInputError(translated_message=key, context={**coordinate, **(error.context or {})})
    return InventoryServiceInputError(translated_message=_INVENTORY_VALIDATION_TRANSLATION, context=coordinate)


def _movement_record(movement: InventoryMovementCommand) -> MovementRecord:
    """Project one command into its canonical movement row."""
    if movement.acquisition_cost is not None:
        return MovementRecord.from_purchase_acquisition(
            movement_id=movement.movement_id,
            movement_date=movement.movement_date,
            quantity=movement.quantity,
            acquisition_cost=movement.acquisition_cost,
        )
    return MovementRecord(
        movement_id=movement.movement_id,
        movement_date=movement.movement_date,
        kind=movement.kind,
        quantity=movement.quantity,
        unit_cost=movement.unit_cost,
        taxable_base=movement.taxable_base,
    )


class InventoryService:
    """Bucket-scoped CRUD over per-actividad :class:`InventoryLedger` records.

    The executable composition root supplies the repository factory and event
    repository through :class:`InventoryServicePorts`; the service never
    resolves a storage route or names an adapter implementation.
    """

    def __init__(
        self,
        *,
        ports: InventoryServicePorts,
    ) -> None:
        """Bind the required application-owned inventory capabilities."""
        self._event_repository = ports.bucket_event_repository
        self._repository_factory = ports.inventory_repository_factory

    def _repository_for(self, bucket_id: str) -> InventoryLedgerServiceRepositoryProtocol:
        return self._repository_factory(bucket_id)

    def create(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        valuation_method: str,
        opening_stock: Decimal = Decimal("0"),
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Create a fresh ledger for one actividad/year. Rejects duplicates.

        Saves the containing :class:`InventoryLedgerDocument`, emits a
        ``LEDGER_INVENTORY_CREATED`` bucket event, and returns an
        :class:`InventoryLedgerResult`.
        """
        try:
            method = parse_valuation_method(valuation_method)
        except InventoryLedgerError as exc:
            raise InventoryServiceInputError(
                translated_message="application.inventory.service.errors.invalid_valuation_method",
                context={"valuation_method": valuation_method},
            ) from exc
        repository = self._repository_for(bucket_id)
        try:
            ledger = InventoryLedger(
                actividad_id=actividad_id,
                year=year,
                valuation_method=method,
                opening_stock=opening_stock,
                closing_authority_record=None,
            )
        except (InventoryLedgerError, ValidationError) as exc:
            raise InventoryServiceInputError(
                translated_message=_INVENTORY_VALIDATION_TRANSLATION,
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        # Delegated to the repository's guarded verb rather than repeating its
        # read, duplicate-check and write here. The document is a singleton row,
        # so creating one ledger rewrites all of them: performed unguarded, a
        # ledger created for a DIFFERENT activity in the interim is discarded,
        # and the duplicate check cannot notice because the two never met. The
        # verb runs that check inside the guarded unit of work, so it is
        # re-judged against the document each attempt actually writes to.
        #
        # The refusal is re-raised in this layer's own words: the adapter names
        # a storage-level conflict, and the operator asked to create an
        # actividad.
        try:
            repository.create(ledger)
        except InventoryLedgerError as exc:
            if (
                exc.translated_message
                == "adapters.persistence.profile.inventory.errors.inventory_ledger_already_exists"
            ):
                raise InventoryActividadConflictError(
                    translated_message="application.inventory.service.errors.activity_conflict",
                    context={"actividad_id": actividad_id, "year": str(year)},
                ) from exc
            raise
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_CREATED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"valuation_method": method.value},
        )
        return InventoryLedgerResult(ledger=ledger, bucket_event_ids=(event_id,))

    def list_all(self, *, bucket_id: str) -> tuple[InventoryActividadSummary, ...]:
        """Return one :class:`InventoryActividadSummary` per stored ledger.

        This is a read-only projection over the bucket's
        :class:`InventoryLedgerDocument`; it emits no bucket event.
        """
        document = self._repository_for(bucket_id).load()
        return tuple(
            InventoryActividadSummary(
                actividad_id=ledger.actividad_id,
                year=ledger.year,
                valuation_method=ledger.valuation_method,
                opening_stock=ledger.opening_stock,
                movement_count=len(ledger.period_movements),
                label=ledger.descriptor.label if ledger.descriptor is not None else None,
                retired=ledger.is_retired,
                leaves_year_unresolved=ledger.leaves_year_unresolved,
                retirement_reason=ledger.retirement_reason,
                correction_count=sum(entry.correction_reason is not None for entry in ledger.history),
            )
            for ledger in document.ledgers
        )

    def show(self, *, bucket_id: str, actividad_id: str, year: int) -> InventoryLedger:
        """Return the exact :class:`InventoryLedger` for ``actividad_id`` and ``year``.

        Raises :class:`InventoryActividadNotFoundError` when the bucket's
        inventory document has no matching actividad/year ledger.
        """
        document = self._repository_for(bucket_id).load()
        ledger = _find_ledger(document, actividad_id, year)
        if ledger is None:
            raise InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.activity_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
            )
        return ledger

    def movement_add(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        movement: InventoryMovementCommand,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Append a movement to the named ledger; refuses duplicate movement_id.

        The :class:`InventoryMovementCommand` is converted to a
        :class:`MovementRecord`, then the domain valuation guard runs
        before persistence. Returns an :class:`InventoryLedgerResult`
        with the updated ledger after the movement is appended.
        """
        try:
            record = _movement_record(movement)
        except (InventoryLedgerError, ValidationError) as exc:
            raise InventoryServiceInputError(
                translated_message=_INVENTORY_VALIDATION_TRANSLATION,
                context={"actividad_id": actividad_id, "year": str(year), "movement_id": movement.movement_id},
            ) from exc
        repository = self._repository_for(bucket_id)

        def validate_candidate(candidate: InventoryLedger) -> None:
            try:
                compute_inventory_valuation(candidate)
            except (InventoryLedgerError, ValidationError) as exc:
                # The revision-guarded repository invokes this validator on
                # each latest candidate before publishing it. Only validation
                # errors from this callback are known to precede persistence.
                if isinstance(exc, InventoryLedgerError) and exc.translated_message in _CHANGE_REFUSAL_KEYS:
                    raise _refusal_from_change(exc, actividad_id=actividad_id, year=year) from exc
                raise InventoryServiceInputError(
                    translated_message=_INVENTORY_VALIDATION_TRANSLATION,
                    context={"actividad_id": actividad_id, "year": str(year), "movement_id": movement.movement_id},
                ) from exc

        try:
            # The storage adapter retries its singleton revision-guarded mutation
            # against the latest document. Run the domain guard on that exact
            # candidate before the winning revision is published, so concurrent
            # movements cannot pass valuation against a stale read.
            updated = repository.record_movement(
                actividad_id,
                record,
                year=year,
                validate_candidate=validate_candidate,
            )
        except InventoryLedgerError as exc:
            if exc.translated_message == "adapters.persistence.profile.inventory.errors.movement_already_exists":
                raise InventoryServiceInputError(
                    translated_message="application.inventory.service.errors.duplicate_movement_id",
                    context={"movement_id": movement.movement_id},
                ) from exc
            if exc.translated_message == "adapters.persistence.profile.inventory.errors.inventory_ledger_not_found":
                raise InventoryActividadNotFoundError(
                    translated_message="application.inventory.service.errors.activity_not_found",
                    context={"actividad_id": actividad_id, "year": str(year)},
                ) from exc
            if exc.translated_message in _CHANGE_REFUSAL_KEYS:
                raise _refusal_from_change(exc, actividad_id=actividad_id, year=year) from exc
            raise
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_MOVEMENT_ADDED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"movement_id": movement.movement_id, "kind": movement.kind.value},
        )
        return InventoryLedgerResult(ledger=updated, bucket_event_ids=(event_id,), changed=True)

    def valuation_preview(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        actor: str = "cli",
    ) -> InventoryValuationPreviewResult:
        """Run the domain-layer valuation engine and report closing stock + COGS.

        Returns:
            :class:`InventoryValuationPreviewResult`: The valuation preview result.
        """
        ledger = self.show(bucket_id=bucket_id, actividad_id=actividad_id, year=year)
        try:
            result: InventoryValuationResult = compute_inventory_valuation(ledger)
        except (InventoryLedgerError, ValidationError) as exc:
            raise InventoryServiceInputError(
                translated_message=_INVENTORY_VALIDATION_TRANSLATION,
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        preview = InventoryValuationPreview(
            actividad_id=ledger.actividad_id,
            year=ledger.year,
            valuation_method=ledger.valuation_method,
            derived_closing_value=result.closing_value,
            cogs=result.cogs_value,
        )
        now = _now_utc()
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.LEDGER_INVENTORY_VALUATION_PREVIEWED,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=now,
            payload={"valuation_method": ledger.valuation_method.value},
        )
        return InventoryValuationPreviewResult(preview=preview, bucket_event_ids=(event_id,))

    def closing_authority_record(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        authority_record: InventoryClosingAuthorityRecord,
    ) -> InventoryLedgerResult:
        """Atomically validate and persist one complete closing-authority bundle."""
        repository = self._repository_for(bucket_id)

        def validate_candidate(candidate: InventoryLedger) -> InventoryLedger:
            try:
                # The repository calls this within its revision guard, before
                # mutation. Rehydrate the candidate here so a rejection has a
                # precise, pre-commit application boundary.
                return InventoryLedger.model_validate(candidate.model_dump())
            except (InventoryLedgerError, ValidationError) as exc:
                raise InventoryServiceInputError(
                    translated_message=_INVENTORY_VALIDATION_TRANSLATION,
                    context={"actividad_id": actividad_id, "year": str(year)},
                ) from exc

        try:
            write: InventoryClosingAuthorityWrite = repository.record_closing_authority(
                actividad_id,
                authority_record,
                year=year,
                validate_candidate=validate_candidate,
            )
        except InventoryClosingAuthorityConflictError as exc:
            raise InventoryServiceInputError(
                translated_message="application.inventory.service.errors.closing_authority_conflict",
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        except InventoryLedgerError as exc:
            if exc.translated_message in _CHANGE_REFUSAL_KEYS:
                raise _refusal_from_change(exc, actividad_id=actividad_id, year=year) from exc
            if exc.translated_message != "adapters.persistence.profile.inventory.errors.inventory_ledger_not_found":
                raise
            raise InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.activity_not_found",
                context={"actividad_id": actividad_id, "year": str(year)},
            ) from exc
        # No event is emitted here: inventory and bucket events have distinct
        # repositories with no shared transaction. The encrypted ledger write is
        # atomic and replay-safe; claiming a cross-repository commit would not be.
        return InventoryLedgerResult(ledger=write.ledger, changed=write.changed)

    def closing_value_record(
        self,
        *,
        bucket_id: str,
        facts: InventoryClosingValueFacts,
        actor: str,
        source_command: str,
    ) -> InventoryLedgerResult:
        """Derive one book's complete closing record from plain facts, then record it."""
        coordinate = {"actividad_id": facts.actividad_id, "year": str(facts.year)}
        document = self._repository_for(bucket_id).load()
        ledger = next(
            (item for item in document.ledgers if item.actividad_id == facts.actividad_id and item.year == facts.year),
            None,
        )
        if ledger is None:
            raise InventoryActividadNotFoundError(
                translated_message="application.inventory.service.errors.activity_not_found",
                context=coordinate,
            )
        try:
            record = build_closing_authority_record(
                facts,
                document=document,
                ledger=ledger,
                actor=actor,
                source_command=source_command,
            )
        except (InventoryLedgerError, ValidationError) as exc:
            raise InventoryServiceInputError(
                translated_message=inventory_refusal_key("closing_authority_invalid"),
                context=coordinate,
            ) from exc
        return self.closing_authority_record(
            bucket_id=bucket_id,
            actividad_id=facts.actividad_id,
            year=facts.year,
            authority_record=record,
        )

    def _apply_change(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        actor: str,
        event_type: BucketEventType,
        event_payload: dict[str, str],
        change: Callable[[InventoryLedgerDocument, InventoryLedger], InventoryLedger],
    ) -> InventoryLedgerResult:
        """Run one domain change in the revision guard; an exact replay emits no event."""
        try:
            write = self._repository_for(bucket_id).apply_ledger_change(actividad_id, year=year, change=change)
        except (InventoryLedgerError, ValidationError) as exc:
            raise _refusal_from_change(exc, actividad_id=actividad_id, year=year) from exc
        if not write.changed:
            return InventoryLedgerResult(ledger=write.ledger, changed=False)
        event_id = _emit_inventory_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=event_type,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            occurred_at=_now_utc(),
            payload=event_payload,
        )
        return InventoryLedgerResult(ledger=write.ledger, bucket_event_ids=(event_id,), changed=True)

    def describe(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        correction_id: str,
        label: str,
        description: str | None,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Replace the inventory's descriptive facts; valuation and fingerprints do not move."""
        try:
            descriptor = InventoryLedgerDescriptor(label=label, description=description)
        except (InventoryLedgerError, ValidationError) as exc:
            raise _refusal_from_change(exc, actividad_id=actividad_id, year=year) from exc
        stamp = InventoryChangeStamp(correction_id=correction_id, recorded_at=_now_utc(), actor=actor)
        return self._apply_change(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            event_type=BucketEventType.LEDGER_INVENTORY_DESCRIBED,
            event_payload={"correction_id": correction_id},
            change=lambda _document, ledger: describe_ledger(ledger, stamp=stamp, descriptor=descriptor),
        )

    def correct_opening(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        correction_id: str,
        reason: InventoryCorrectionReason,
        opening_stock: Decimal | None,
        valuation_method: ValuationMethod | None,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Rectify the opening value or valuation method, retaining what they displace."""
        stamp = InventoryChangeStamp(correction_id=correction_id, recorded_at=_now_utc(), actor=actor)
        return self._apply_change(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            event_type=BucketEventType.LEDGER_INVENTORY_CORRECTED,
            event_payload={"correction_id": correction_id, "reason": reason.value},
            change=lambda document, ledger: correct_opening(
                document,
                ledger,
                stamp=stamp,
                reason=reason,
                opening_stock=opening_stock,
                valuation_method=valuation_method,
            ),
        )

    def movement_correct(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        correction_id: str,
        target_movement_id: str,
        replacement: InventoryMovementCommand,
        reason: InventoryCorrectionReason,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Supersede one movement with a replacement, retaining the movement it displaces."""
        try:
            record = _movement_record(replacement)
        except (InventoryLedgerError, ValidationError) as exc:
            raise _refusal_from_change(exc, actividad_id=actividad_id, year=year) from exc
        stamp = InventoryChangeStamp(correction_id=correction_id, recorded_at=_now_utc(), actor=actor)
        return self._apply_change(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            event_type=BucketEventType.LEDGER_INVENTORY_MOVEMENT_CORRECTED,
            event_payload={
                "correction_id": correction_id,
                "movement_id": target_movement_id,
                "replacement_movement_id": record.movement_id,
                "reason": reason.value,
            },
            change=lambda document, ledger: correct_movement(
                document,
                ledger,
                stamp=stamp,
                target_movement_id=target_movement_id,
                replacement=record,
                reason=reason,
            ),
        )

    def movement_reverse(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        correction_id: str,
        target_movement_id: str,
        reason: InventoryCorrectionReason,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Take one movement out of the effective set, retaining it as evidence."""
        stamp = InventoryChangeStamp(correction_id=correction_id, recorded_at=_now_utc(), actor=actor)
        return self._apply_change(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            event_type=BucketEventType.LEDGER_INVENTORY_MOVEMENT_REVERSED,
            event_payload={"correction_id": correction_id, "movement_id": target_movement_id, "reason": reason.value},
            change=lambda document, ledger: reverse_movement(
                document,
                ledger,
                stamp=stamp,
                target_movement_id=target_movement_id,
                reason=reason,
            ),
        )

    def retire(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        correction_id: str,
        reason: InventoryRetirementReason,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Take the inventory out of the active register with every fact retained."""
        stamp = InventoryChangeStamp(correction_id=correction_id, recorded_at=_now_utc(), actor=actor)
        return self._apply_change(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            event_type=BucketEventType.LEDGER_INVENTORY_RETIRED,
            event_payload={"correction_id": correction_id, "reason": reason.value},
            change=lambda document, ledger: retire_ledger(document, ledger, stamp=stamp, reason=reason),
        )

    def restore(
        self,
        *,
        bucket_id: str,
        actividad_id: str,
        year: int,
        correction_id: str,
        actor: str = "cli",
    ) -> InventoryLedgerResult:
        """Bring a retired inventory back to the active register."""
        stamp = InventoryChangeStamp(correction_id=correction_id, recorded_at=_now_utc(), actor=actor)
        return self._apply_change(
            bucket_id=bucket_id,
            actividad_id=actividad_id,
            year=year,
            actor=actor,
            event_type=BucketEventType.LEDGER_INVENTORY_RESTORED,
            event_payload={"correction_id": correction_id},
            change=lambda _document, ledger: restore_ledger(ledger, stamp=stamp),
        )


__all__ = [
    "InventoryActividadSummary",
    "InventoryLedgerResult",
    "InventoryMovementCommand",
    "InventoryService",
    "InventoryValuationPreview",
    "InventoryValuationPreviewResult",
]
