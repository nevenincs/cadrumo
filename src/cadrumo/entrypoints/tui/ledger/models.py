"""Immutable presentation records for the host-neutral Ledger workspace."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final, Literal, Never, Protocol, SupportsIndex, get_args, override
from weakref import WeakKeyDictionary

from pydantic import BaseModel, model_validator

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.models import (
    LedgerSourceImportCommand,
    LedgerSourceImportResult,
    ManualLedgerTransactionPatch,
    ManualLedgerTransactionResult,
)
from ....application.ledger.workspace import (
    LedgerAffectedDeclarationRefV1,
    LedgerInvoiceReconciliationRefV1,
    LedgerLinkInconsistencyRefV1,
    LedgerWorkspaceArea,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
)
from ....application.operator_actions.models import ActionReference
from ....core.identity import InvoiceId, TransactionId
from ....core.models import STRICT_FROZEN_CONFIG

type LedgerDestinationIdV1 = Literal[
    "ledger.overview",
    "ledger.entries",
    "ledger.review",
    "ledger.import",
    "ledger.classification",
    "ledger.evidence",
    "ledger.reconciliation",
]


def declared_ledger_destination_ids() -> frozenset[str]:
    """Read the internal closed destination set from its defining type alias.

    Defined beside the alias it reads rather than beside a consumer, so the
    set and its declaration cannot drift apart.
    """
    return frozenset(item for item in get_args(LedgerDestinationIdV1.__value__) if isinstance(item, str))


#: The one pairing of workspace area to internal destination.
#:
#: Declared here rather than beside either consumer because both need it and
#: the route catalogue imports the controller, so neither module can own it.
#:
#: It used to be written twice: once in the route catalogue, whose totality
#: gate checked it, and once in the controller behind a ``cast`` to this
#: alias. A ``cast`` asserts rather than validates, so the controller copy was
#: checked by nothing at all -- not by the type checker, which believed the
#: assertion, and not by the route gate, which never read it. A destination
#: misspelled there stayed invisible until an operator selected that area and
#: the route lookup raised ``KeyError``; a destination swapped between two
#: areas surfaced as a disagreement refusal at the same moment. Both are
#: import-time facts about a closed set, so they are settled at import now.
LEDGER_DESTINATION_BY_AREA: Final[dict[LedgerWorkspaceArea, LedgerDestinationIdV1]] = {
    LedgerWorkspaceArea.OVERVIEW: "ledger.overview",
    LedgerWorkspaceArea.ENTRIES: "ledger.entries",
    LedgerWorkspaceArea.REVIEW: "ledger.review",
    LedgerWorkspaceArea.IMPORT: "ledger.import",
    LedgerWorkspaceArea.CLASSIFICATION: "ledger.classification",
    LedgerWorkspaceArea.EVIDENCE: "ledger.evidence",
    LedgerWorkspaceArea.RECONCILIATION: "ledger.reconciliation",
}


def _require_total_destination_pairing() -> None:
    """Refuse at import unless the pairing is a bijection in canonical order.

    Totality over the enum is what keeps navigation from raising on an area
    nobody remembered to map; uniqueness of the destinations is what keeps two
    areas from resolving to one screen. Order is checked because the route
    catalogue presents areas in enum order and reads its destinations from
    here.
    """
    if tuple(LEDGER_DESTINATION_BY_AREA) != tuple(LedgerWorkspaceArea):
        raise ValueError("Ledger destinations must cover every workspace area in canonical order")
    destinations = tuple(LEDGER_DESTINATION_BY_AREA.values())
    if frozenset(destinations) != declared_ledger_destination_ids() or len(frozenset(destinations)) != len(
        destinations
    ):
        raise ValueError("Ledger destinations must cover the internal catalogue exactly once")


_require_total_destination_pairing()


class LedgerRouteTargetV1(BaseModel):
    """One internal destination selected by its stable area identity."""

    model_config = STRICT_FROZEN_CONFIG

    destination: LedgerDestinationIdV1
    area: LedgerWorkspaceArea


class LedgerRouteRefusalV1(BaseModel):
    """A route that cannot be opened, preserving the authority that refused it."""

    model_config = STRICT_FROZEN_CONFIG

    target: LedgerRouteTargetV1
    availability: LedgerWorkspaceAvailability
    reason_key: str


class LedgerEntryRowV1(BaseModel):
    """Safe entry row containing no description, amount, counterparty, or evidence."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    source: LedgerWorkspaceEntryRefV1

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerEntryRowV1:
        if self.transaction_id != self.source.transaction_id or self.review_status != self.source.review_status:
            raise ValueError("Ledger entry row must mirror its application projection source")
        return self


class LedgerReviewRowV1(BaseModel):
    """A reviewable transaction plus the canonical read action naming its door."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    review_status: str
    action: ActionReference
    source: LedgerWorkspaceEntryRefV1

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerReviewRowV1:
        if self.transaction_id != self.source.transaction_id or self.review_status != self.source.review_status:
            raise ValueError("Ledger review row must mirror its application projection source")
        return self


class LedgerFlowState(StrEnum):
    """Explicit state of a command-backed Ledger interaction."""

    EDITING = "editing"
    CONFIRMING = "confirming"
    SUBMITTING = "submitting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LedgerClassificationSubmissionV1(BaseModel):
    """Catalogue-authorized canonical classification patch submission."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    transaction_id: TransactionId
    patch: ManualLedgerTransactionPatch


class LedgerClassificationSubmitterV1(Protocol):
    """Injected application door for a classification mutation."""

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        """Submit one authorized canonical classification patch."""
        ...


_SAFE_CHOICE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}\Z")
_SAFE_PROVIDER_KEYS = frozenset({"tui.ledger.import.provider.bank"})
_SAFE_SOURCE_KEYS = frozenset({"tui.ledger.import.source.prepared"})
_IMPORT_COMMAND_VAULT: WeakKeyDictionary[LedgerPreparedImportV1, LedgerSourceImportCommand] = WeakKeyDictionary()


class LedgerPreparedImportV1:
    """Opaque pre-resolved import command plus safe catalogue display keys.

    The command deliberately has no public attribute, representation, or model
    serialization surface: paths and provider transport values remain inside
    the injected command boundary.
    """

    __slots__ = ("__weakref__", "_choice_id", "_provider_label_key", "_sealed", "_source_label_key")
    _choice_id: str
    _provider_label_key: str
    _sealed: bool
    _source_label_key: str

    def __init__(
        self,
        *,
        choice_id: str,
        provider_label_key: str,
        source_label_key: str,
        command: LedgerSourceImportCommand,
    ) -> None:
        """Seal one pre-resolved command behind safe authored display identities."""
        if (
            _SAFE_CHOICE_ID.fullmatch(choice_id) is None
            or provider_label_key not in _SAFE_PROVIDER_KEYS
            or source_label_key not in _SAFE_SOURCE_KEYS
        ):
            raise ValueError("prepared imports require safe Ledger catalogue identities")
        object.__setattr__(self, "_choice_id", choice_id)
        object.__setattr__(self, "_provider_label_key", provider_label_key)
        object.__setattr__(self, "_source_label_key", source_label_key)
        object.__setattr__(self, "_sealed", True)
        _IMPORT_COMMAND_VAULT[self] = command

    @property
    def choice_id(self) -> str:
        """Return the safe semantic choice identity."""
        return self._choice_id

    @property
    def provider_label_key(self) -> str:
        """Return an admitted authored provider label key."""
        return self._provider_label_key

    @property
    def source_label_key(self) -> str:
        """Return an admitted authored source label key."""
        return self._source_label_key

    @override
    def __setattr__(self, name: str, value: object) -> None:
        """Prevent command or safe metadata replacement after admission."""
        del name, value
        raise AttributeError("prepared import capabilities are immutable")

    @override
    def __repr__(self) -> str:
        """Return a path- and provider-free diagnostic representation."""
        return f"LedgerPreparedImportV1(choice_id={self.choice_id!r})"

    @override
    def __reduce_ex__(self, protocol: SupportsIndex, /) -> Never:
        """Refuse serialization so the vaulted command cannot be recovered."""
        del protocol
        raise TypeError("prepared import capabilities cannot be serialized")

    async def submit_with(self, submitter: LedgerImportSubmitterV1) -> LedgerSourceImportResult:
        """Submit the sealed command without exposing it to presentation code."""
        return await submitter(_IMPORT_COMMAND_VAULT[self])


class LedgerImportSubmitterV1(Protocol):
    """Injected application door for an already-resolved import command."""

    async def __call__(self, command: LedgerSourceImportCommand) -> LedgerSourceImportResult:
        """Submit one already-resolved canonical import command."""
        ...


class LedgerEvidenceRowV1(BaseModel):
    """Safe application evidence-review metadata with its declared read action."""

    model_config = STRICT_FROZEN_CONFIG

    attachment_id: str
    mime_type: str
    bytes_size: int
    captured_at: str
    pending_review: bool
    action: ActionReference
    source: AttachmentReviewItem

    @model_validator(mode="after")
    def _mirror_source(self) -> LedgerEvidenceRowV1:
        if (
            self.attachment_id != self.source.attachment_id
            or self.mime_type != self.source.mime_type
            or self.bytes_size != self.source.bytes_size
            or self.captured_at != self.source.captured_at
            or self.pending_review != self.source.pending_review
        ):
            raise ValueError("Ledger evidence row must mirror its canonical application source")
        return self


class LedgerLinkSubmissionV1(BaseModel):
    """Catalogue-authorized local invoice/transaction link request."""

    model_config = STRICT_FROZEN_CONFIG

    action: ActionReference
    transaction_id: TransactionId
    invoice_id: InvoiceId


class LedgerLinkResultV1(BaseModel):
    """Safe identity-only acknowledgement returned by an injected link door."""

    model_config = STRICT_FROZEN_CONFIG

    transaction_id: TransactionId
    invoice_id: InvoiceId


class LedgerLinkSubmitterV1(Protocol):
    """Injected application door for one admitted local Ledger link."""

    async def __call__(self, submission: LedgerLinkSubmissionV1) -> LedgerLinkResultV1:
        """Submit one authorized link request."""
        ...


type LedgerReconciliationSourceV1 = (
    LedgerInvoiceReconciliationRefV1 | LedgerLinkInconsistencyRefV1 | LedgerAffectedDeclarationRefV1
)


__all__ = [
    "LEDGER_DESTINATION_BY_AREA",
    "LedgerClassificationSubmissionV1",
    "LedgerClassificationSubmitterV1",
    "LedgerDestinationIdV1",
    "LedgerEntryRowV1",
    "LedgerEvidenceRowV1",
    "LedgerFlowState",
    "LedgerImportSubmitterV1",
    "LedgerLinkResultV1",
    "LedgerLinkSubmissionV1",
    "LedgerLinkSubmitterV1",
    "LedgerPreparedImportV1",
    "LedgerReviewRowV1",
    "LedgerRouteRefusalV1",
    "LedgerRouteTargetV1",
    "declared_ledger_destination_ids",
]
