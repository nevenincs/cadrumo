"""Pure controller and common interaction shell for Ledger destinations."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace
from typing import Final

from ....application.ledger.models import (
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ....application.ledger.workspace import (
    LEDGER_WORKSPACE_CONTRACT_VERSION,
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceStatus,
)
from ....application.review.filter import LedgerReviewStatus
from ....core.errors.hierarchy import InternalInvariantError
from ....core.i18n.render import tr
from ....core.identity.hex_ids import InvoiceId
from ....core.identity.transaction_ids import TransactionId
from ..navigation import TuiFocusIdentityV1, TuiScreenContextV1
from .models import (
    LEDGER_DESTINATION_BY_AREA,
    LedgerClassificationPatchV1,
    LedgerClassificationResultV1,
    LedgerClassificationSubmissionV1,
    LedgerEntryRowV1,
    LedgerEvidenceConfirmationV1,
    LedgerEvidenceConfirmedV1,
    LedgerEvidenceDraftV1,
    LedgerEvidenceRecordRowV1,
    LedgerEvidenceRowV1,
    LedgerExclusionResultV1,
    LedgerExclusionSubmissionV1,
    LedgerImportOutcomeV1,
    LedgerImportRequestV1,
    LedgerInvoiceAddResultV1,
    LedgerInvoiceEntryV1,
    LedgerLinkResultV1,
    LedgerLinkSubmissionV1,
    LedgerReaderReadinessV1,
    LedgerRouteRefusalV1,
    LedgerRouteTargetV1,
)
from .tools import LedgerToolV1
from .workspace_injection import LedgerWorkspaceInjection

LEDGER_TRANSACTION_FOCUS: Final = "ledger.transaction"
"""The Ledger focus that opens its entries with one transaction selected, by its id."""

_AREA_LOCALE_KEYS: Final = {
    LedgerWorkspaceArea.OVERVIEW: "tui.ledger.area.overview",
    LedgerWorkspaceArea.ENTRIES: "tui.ledger.area.entries",
    LedgerWorkspaceArea.REVIEW: "tui.ledger.area.review",
    LedgerWorkspaceArea.IMPORT: "tui.ledger.area.import",
    LedgerWorkspaceArea.CLASSIFICATION: "tui.ledger.area.classification",
    LedgerWorkspaceArea.EVIDENCE: "tui.ledger.area.evidence",
    LedgerWorkspaceArea.RECONCILIATION: "tui.ledger.area.reconciliation",
}
_AVAILABILITY_LOCALE_KEYS: Final = {
    LedgerWorkspaceAvailability.AVAILABLE: "tui.ledger.availability.available",
    LedgerWorkspaceAvailability.LOCKED: "tui.ledger.availability.locked",
    LedgerWorkspaceAvailability.STALE: "tui.ledger.availability.stale",
    LedgerWorkspaceAvailability.NEVER_CAPTURED: "tui.ledger.availability.never_captured",
    LedgerWorkspaceAvailability.UNAVAILABLE: "tui.ledger.availability.unavailable",
}
#: Derived from the enum rather than listed, so a status cannot be produced
#: without a name.
#:
#: The hand-written version held three of the four members. Nothing pointed at
#: the enum, so ``EXCLUDED`` -- which ``ledger_transaction_review_status``
#: returns for a REVIEWED_EXCLUDED row -- had no entry, and
#: :func:`review_status_label` raises on a miss. Both the entries table and the
#: review table label every row, so classifying one row as excluded and opening
#: either body took the workspace down.
_REVIEW_STATUS_LOCALE_KEYS: Final = {
    status.value: f"tui.ledger.review_status.{status.value}" for status in LedgerReviewStatus
}
_STATUS_LOCALE_KEYS: Final = {
    LedgerWorkspaceStatus.READY: "tui.ledger.status.ready",
    LedgerWorkspaceStatus.EMPTY: "tui.ledger.status.empty",
    LedgerWorkspaceStatus.NEEDS_ATTENTION: "tui.ledger.status.needs_attention",
    LedgerWorkspaceStatus.UNMEASURED: "tui.ledger.status.unmeasured",
}


def area_label(area: LedgerWorkspaceArea) -> str:
    """Return an operator label without displaying an internal enum token."""
    return tr(_AREA_LOCALE_KEYS[area])


def availability_label(availability: LedgerWorkspaceAvailability) -> str:
    """Render availability with a textual cue independent of colour."""
    return tr(_AVAILABILITY_LOCALE_KEYS[availability])


def review_status_label(status: str) -> str:
    """Translate a source status without leaking its transport spelling."""
    key = _REVIEW_STATUS_LOCALE_KEYS.get(status)
    if key is None:
        raise ValueError("unsupported Ledger review status")
    return tr(key)


def status_label(status: LedgerWorkspaceStatus) -> str:
    """Render source status through its authored catalogue key."""
    return tr(_STATUS_LOCALE_KEYS[status])


def item_count_label(state: LedgerWorkspaceAreaStateV1) -> str:
    """Keep an unmeasured denominator distinct from a measured numeric zero."""
    return status_label(state.status) if state.status is LedgerWorkspaceStatus.UNMEASURED else str(state.item_count)


_APPLICATION_STATE_REASON_KEY = "tui.ledger.refusal.application_state"
"""The one line a closed Ledger area renders: the application names no Ledger reason codes."""


class LedgerWorkspaceController:
    """Read-only custody of one injected application projection and shell context."""

    def __init__(
        self,
        context: TuiScreenContextV1,
        projection: LedgerWorkspaceProjectionV1,
        injection: LedgerWorkspaceInjection,
    ) -> None:
        """Admit an outer Ledger context and retain its immutable snapshot."""
        if context.destination != "workbench.ledger":
            raise ValueError("Ledger workspace requires the workbench.ledger screen context")
        if projection.contract_version != LEDGER_WORKSPACE_CONTRACT_VERSION:
            raise ValueError("unsupported Ledger workspace projection contract")
        self.context = context
        self.projection = projection
        self.injection = injection
        self.review_action = injection.review_action
        self.review_door = injection.review_door
        self.classify_action = injection.classify_action
        self.classification_submitter = injection.classification_submitter
        self.import_door = injection.import_door
        self.invoice_add_door = injection.invoice_add_door
        self.exclusion_submitter = injection.exclusion_submitter
        self.evidence_door = injection.evidence_door
        self.evidence_action = injection.evidence_action
        self.evidence_items = injection.evidence_items
        self.evidence_review_door = injection.evidence_review_door
        self.link_action = injection.link_action
        self.link_submitter = injection.link_submitter
        self.activity_asset_actions = injection.activity_asset_actions
        self.record_doors = injection.record_doors
        self.own_account_door = injection.own_account_door
        self.tools = injection.tools
        self._states = {row.area: row for row in projection.areas}

    def tools_for(self, area: LedgerWorkspaceArea) -> tuple[LedgerToolV1, ...]:
        """Return the tools an area lists, in the order they were given."""
        return tuple(tool for tool in self.tools if tool.area is area)

    def tool(self, key: str) -> LedgerToolV1 | None:
        """Return the tool with this key, if the workspace was given one."""
        return next((tool for tool in self.tools if tool.key == key), None)

    def classification_target_coordinate(self) -> tuple[int, int, str]:
        """Return a safe position and redacted identifier from the visible projection."""
        target = self.classification_target
        if target is None:
            raise InternalInvariantError("classification target is unavailable")
        position = next(
            index for index, row in enumerate(self.projection.entries, start=1) if row.transaction_id == target
        )
        return position, len(self.projection.entries), str(target)[:12]

    def can_manage_activity_assets(self) -> bool:
        """Return whether the installed composition supplied the shared asset door."""
        return self.activity_asset_actions is not None

    def entry_label(self, transaction_id: TransactionId) -> str:
        """Name one entry the way the operator recorded it: its date and description.

        An entry the projection does not carry falls back to its short
        identifier rather than to a blank cell.
        """
        entry = next((row for row in self.projection.entries if row.transaction_id == transaction_id), None)
        if entry is None:
            return str(transaction_id)[:12]
        return tr("tui.ledger.entry_label", date=entry.date, description=entry.description)

    def state_for(self, area: LedgerWorkspaceArea) -> LedgerWorkspaceAreaStateV1:
        """Return the application-owned area state."""
        return self._states[area]

    def route_target(self, area: LedgerWorkspaceArea) -> LedgerRouteTargetV1:
        """Build an internal semantic target without invoking it.

        The destination comes from the canonical pairing rather than a copy
        held here, so this cannot name a screen the route catalogue does not
        have. The lookup needs no ``cast``: the pairing is typed as the
        destination alias, so a misspelling is a type error at the
        declaration instead of an assertion the checker believes.
        """
        return LedgerRouteTargetV1(destination=LEDGER_DESTINATION_BY_AREA[area], area=area)

    def _selection_refusal(
        self,
        area: LedgerWorkspaceArea,
        target: LedgerRouteTargetV1,
    ) -> LedgerRouteRefusalV1 | None:
        """Refuse an area that needs a chosen entry when none has been chosen.

        Kept out of ``refusal_for``'s ``missing_door`` expression on purpose,
        and out of any boolean joining it to the area comparison. A missing
        door is an absent INJECTED dependency — something the launcher failed
        to wire — and the wholly-wired-doors gate derives what the launcher
        owes by reading that expression. A selection is the operator's, made at
        runtime, so joining the two demanded an operator value from the
        launcher; that unsatisfiable demand is why the classification door was
        removed rather than wired.

        It also lets the operator hear what is actually true — choose an entry
        — instead of being told submission is unavailable.
        """
        if area is not LedgerWorkspaceArea.CLASSIFICATION:
            return None
        if self.classification_target is not None:
            return None
        # With no entries there is nothing to choose, and asking for a choice
        # sends the operator looking for rows that do not exist.
        reason_key = (
            "tui.ledger.refusal.selection_required" if self.projection.entries else "tui.ledger.refusal.no_entries"
        )
        return LedgerRouteRefusalV1(
            target=target,
            availability=LedgerWorkspaceAvailability.UNAVAILABLE,
            reason_key=reason_key,
        )

    def _submission_door_is_missing(self, area: LedgerWorkspaceArea) -> bool:
        """Return whether an area lacks the injected command it needs.

        Each clause joins one area to exactly the fields it needs, which is the
        shape the wholly-wired-doors gate reads the launcher's obligations from.
        """
        return (
            (area is LedgerWorkspaceArea.REVIEW and self.review_door is None)
            or (
                area is LedgerWorkspaceArea.CLASSIFICATION
                and (self.classify_action is None or self.classification_submitter is None)
            )
            or (area is LedgerWorkspaceArea.IMPORT and self.import_door is None)
            or self._evidence_door_is_missing(area)
        )

    def _evidence_door_is_missing(self, area: LedgerWorkspaceArea) -> bool:
        return area is LedgerWorkspaceArea.EVIDENCE and (
            self.evidence_action is None
            or (self.evidence_items is None and self.evidence_door is None and self.evidence_review_door is None)
        )

    def refusal_for(self, area: LedgerWorkspaceArea) -> LedgerRouteRefusalV1 | None:
        """Preserve application refusal separately from deferred screen availability."""
        target = self.route_target(area)
        state = self.state_for(area)
        if state.availability is not LedgerWorkspaceAvailability.AVAILABLE:
            return LedgerRouteRefusalV1(
                target=target,
                availability=state.availability,
                reason_key=_APPLICATION_STATE_REASON_KEY,
            )
        selection_refusal = self._selection_refusal(area, target)
        if selection_refusal is not None:
            return selection_refusal
        if self._submission_door_is_missing(area):
            return LedgerRouteRefusalV1(
                target=target,
                availability=LedgerWorkspaceAvailability.UNAVAILABLE,
                reason_key="tui.ledger.refusal.submission_unavailable",
            )
        return None

    def entry_rows(self) -> tuple[LedgerEntryRowV1, ...]:
        """Narrow safe application entry references without recovering payloads."""
        return tuple(
            LedgerEntryRowV1(
                transaction_id=row.transaction_id,
                review_status=row.review_status,
                source=row,
            )
            for row in self.projection.entries
        )

    def with_transaction_focus(self, transaction_id: TransactionId) -> LedgerWorkspaceController:
        """Re-address this workspace at one visible entry, carrying nothing else.

        Selection travels in ``context.focus`` — the channel
        :meth:`restored_transaction_id` already reads for cursor restore — so
        there is one answer to "which entry is the operator on". A separate
        mutable attribute beside it would let the restored cursor and the
        classification target disagree about the same question.

        Returns a NEW controller rather than mutating, because the context is
        frozen. An internal area move resolves its next screen synchronously
        against whatever controller the outgoing screen holds, so rebinding
        there is what carries the selection across a body swap — with no extra
        screen push, and therefore no result callback left registered against a
        pump that is about to stop.

        The context is constructed explicitly rather than by ``model_copy``:
        ``model_copy`` skips validation, and the focus/destination agreement
        check is the thing stopping a focus from naming another workspace.

        Raises:
            ValueError: When the entry is not in the visible projection. An
                entry the operator cannot see is one they cannot have chosen.
        """
        if all(row.transaction_id != transaction_id for row in self.projection.entries):
            raise ValueError("classification target is absent from the visible Ledger projection")
        return LedgerWorkspaceController(
            TuiScreenContextV1(
                destination=self.context.destination,
                focus=TuiFocusIdentityV1(
                    destination=self.context.destination,
                    semantic_key=LEDGER_TRANSACTION_FOCUS,
                    restore_token=transaction_id,
                ),
                action_candidate_id=self.context.action_candidate_id,
            ),
            self.projection,
            self.injection,
        )

    @property
    def classification_target(self) -> TransactionId | None:
        """The entry the operator selected, read from the one focus channel."""
        return self.restored_transaction_id()

    def restored_transaction_id(self) -> TransactionId | None:
        """Resolve a transaction focus by semantic identity, never by row position."""
        focus = self.context.focus
        if focus is None or focus.semantic_key != LEDGER_TRANSACTION_FOCUS or focus.restore_token is None:
            return None
        candidate = focus.restore_token
        return candidate if any(row.transaction_id == candidate for row in self.projection.entries) else None

    def build_classification_patch(self, values: dict[str, object]) -> LedgerClassificationPatchV1:
        """Use the injected request boundary or the existing direct application's patch."""
        builder = self.injection.classification_patch_builder
        return ManualLedgerTransactionPatch.model_validate(values) if builder is None else builder(values)

    async def submit_classification(
        self, patch: LedgerClassificationPatchV1
    ) -> ManualLedgerTransactionResult | LedgerClassificationResultV1:
        """Submit an explicit patch through the injected authorized door."""
        if self.classify_action is None or self.classification_target is None or self.classification_submitter is None:
            raise InternalInvariantError("classification submission is unavailable")
        submission = LedgerClassificationSubmissionV1(
            action=self.classify_action,
            transaction_id=self.classification_target,
            patch=patch,
        )
        result = await self.classification_submitter(submission)
        transaction_id = (
            result.transaction_id if isinstance(result, LedgerClassificationResultV1) else result.ref.transaction_id
        )
        if transaction_id != self.classification_target:
            raise ValueError("classification result transaction identity disagrees")
        return result

    async def preview_import(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Ask the injected import door what applying ``request`` would do."""
        if self.import_door is None:
            raise InternalInvariantError("import submission is unavailable")
        return await self.import_door.preview(request)

    async def apply_import(self, request: LedgerImportRequestV1) -> LedgerImportOutcomeV1:
        """Write a previewed import through the injected door."""
        if self.import_door is None:
            raise InternalInvariantError("import submission is unavailable")
        return await self.import_door.apply(request)

    def can_exclude(self) -> bool:
        """Report whether excluding an entry is admitted: the classify authority and its writer."""
        return self.classify_action is not None and self.exclusion_submitter is not None

    async def submit_exclusion(
        self, transaction_id: TransactionId, *, listed: Collection[TransactionId]
    ) -> ManualLedgerTransactionResult | LedgerExclusionResultV1:
        """Exclude one entry the operator can see in the review queue, which lists ``listed``."""
        if self.classify_action is None or self.exclusion_submitter is None:
            raise InternalInvariantError("exclusion is unavailable")
        if transaction_id not in listed:
            raise ValueError("exclusion target is absent from the visible review list")
        result = await self.exclusion_submitter(
            LedgerExclusionSubmissionV1(action=self.classify_action, transaction_id=transaction_id)
        )
        settled = result.transaction_id if isinstance(result, LedgerExclusionResultV1) else result.ref.transaction_id
        if settled != transaction_id:
            raise ValueError("exclusion result transaction identity disagrees")
        return result

    def can_add_invoices(self) -> bool:
        """Report whether the invoice writer door is admitted in this session."""
        return self.invoice_add_door is not None

    async def add_invoice(self, entry: LedgerInvoiceEntryV1) -> LedgerInvoiceAddResultV1:
        """Record one typed invoice through the injected catalogue writer."""
        if self.invoice_add_door is None:
            raise InternalInvariantError("invoice entry is unavailable")
        return await self.invoice_add_door(entry)

    def evidence_records(self) -> tuple[LedgerEvidenceRecordRowV1, ...] | None:
        """Read the local evidence records, or ``None`` when no door reads them."""
        return None if self.evidence_door is None else self.evidence_door.list_records()

    async def add_evidence(self, source_path: str) -> LedgerEvidenceRecordRowV1:
        """Register one document, as the operator typed its path, through the injected door."""
        if self.evidence_door is None:
            raise InternalInvariantError("evidence registration is unavailable")
        return await self.evidence_door.add(source_path)

    async def extract_evidence(self, evidence_id: str) -> LedgerEvidenceDraftV1:
        """Read one registered document through the injected evidence door."""
        if self.evidence_door is None:
            raise InternalInvariantError("evidence reading is unavailable")
        return await self.evidence_door.extract(evidence_id)

    async def confirm_evidence(self, confirmation: LedgerEvidenceConfirmationV1) -> LedgerEvidenceConfirmedV1:
        """Record one read document as an invoice through the injected evidence door."""
        if self.evidence_door is None:
            raise InternalInvariantError("evidence confirmation is unavailable")
        return await self.evidence_door.confirm(confirmation)

    def reader_readiness(self) -> LedgerReaderReadinessV1 | None:
        """Measure the local reader, or ``None`` when no door can measure it."""
        return None if self.evidence_door is None else self.evidence_door.reader_readiness()

    def can_refresh(self) -> bool:
        """Report whether this workspace can re-read its state after a write."""
        return self.injection.refresh is not None

    def refreshed(self) -> LedgerWorkspaceController:
        """Return this workspace re-read from the current profile state.

        The focus is kept only while the entry it names is still visible; a
        focus on a row the write removed would otherwise address nothing.
        """
        refresh = self.injection.refresh
        if refresh is None:
            return self
        snapshot = refresh()
        injection = replace(self.injection, evidence_items=snapshot.evidence_items)
        focus = self.context.focus
        if (
            focus is not None
            and focus.semantic_key == LEDGER_TRANSACTION_FOCUS
            and all(row.transaction_id != focus.restore_token for row in snapshot.projection.entries)
        ):
            focus = None
        context = TuiScreenContextV1(
            destination=self.context.destination,
            focus=focus,
            action_candidate_id=self.context.action_candidate_id,
        )
        return LedgerWorkspaceController(context, snapshot.projection, injection)

    def evidence_rows(self) -> tuple[LedgerEvidenceRowV1, ...]:
        """Project only canonical review-safe metadata from the injected result."""
        if self.evidence_action is None or self.evidence_items is None:
            raise InternalInvariantError("evidence review is unavailable")
        return tuple(
            LedgerEvidenceRowV1(
                attachment_id=item.attachment_id,
                mime_type=item.mime_type,
                bytes_size=item.bytes_size,
                captured_at=item.captured_at,
                pending_review=item.pending_review,
                action=self.evidence_action,
                source=item,
            )
            for item in self.evidence_items
        )

    def restored_evidence_id(self) -> str | None:
        """Restore evidence focus by semantic application identity."""
        focus = self.context.focus
        if focus is None or focus.semantic_key != "ledger.evidence" or focus.restore_token is None:
            return None
        return (
            focus.restore_token
            if any(row.attachment_id == focus.restore_token for row in self.evidence_rows())
            else None
        )

    def can_submit_links(self) -> bool:
        """Report whether the optional local link-mutation door is admitted."""
        return self.link_action is not None and self.link_submitter is not None

    async def submit_link(self, transaction_id: TransactionId, invoice_id: InvoiceId) -> LedgerLinkResultV1:
        """Admit a visible suggestion and submit it through the authorized door."""
        if self.link_action is None or self.link_submitter is None:
            raise InternalInvariantError("Ledger reconciliation is unavailable")
        if not any(
            row.transaction_id == transaction_id and row.invoice_id == invoice_id
            for row in self.projection.invoice_reconciliations
        ) or not any(row.transaction_id == transaction_id for row in self.projection.entries):
            raise ValueError("link target is absent from the visible reconciliation projection")
        submission = LedgerLinkSubmissionV1(
            action=self.link_action,
            transaction_id=transaction_id,
            invoice_id=invoice_id,
        )
        result = await self.link_submitter(submission)
        if result.transaction_id != transaction_id or result.invoice_id != invoice_id:
            raise ValueError("link result identities disagree with the admitted suggestion")
        return result


__all__ = [
    "LedgerWorkspaceController",
    "area_label",
    "availability_label",
    "item_count_label",
    "review_status_label",
    "status_label",
]
