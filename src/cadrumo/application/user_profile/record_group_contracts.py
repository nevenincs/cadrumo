"""Public contracts of the grouped read of related profile rows.

A record group is one row of a repeatable profile section together with every row
that names it through a schema-declared row reference, and the ledger rows that
name any of them. The read serves the relation, the row identities and the words
of every row, so a surface iterates the stream by item kind and joins nothing.

The stream is paged. A continuation names the profile revision and the digest of
the linked ledger rows it started from, and is refused when either has moved.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import profile_operation_subject
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ..operations.models import CredentialFreeOperationRequest, OperationTerminalReceipt
from ..operations.public_scalar import PublicDecimal

PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID: Final = "user-profile.record-groups"
PROFILE_RECORD_GROUPS_PHASES: Final = ("user-profile.record-groups.read", "user-profile.record-groups.project")
PROFILE_RECORD_GROUPS_MAX_ITEMS: Final = 128
# The result is nested in a settled-operation response and then a runtime frame;
# keep generous space beneath that frame's 64 KiB ceiling for both envelopes.
PROFILE_RECORD_GROUPS_MAX_RESULT_BYTES: Final = 20_000


class ProfileRecordGroupKind(StrEnum):
    """Which rows head the groups: the payload kind a surface renders without a branch."""

    RENTAL_PROPERTY = "rental_property"


class ProfileRecordDoor(StrEnum):
    """What a record's door does to the stored row it is served on."""

    EDIT = "edit"
    REMOVE = "remove"


class ProfileRecordAction(BaseModel):
    """One door of one stored row: the registered operation it submits and the words that label it.

    A surface routes the door by ``operation_definition_id`` and shows ``label_words``,
    so it names no operation and composes no label of its own.
    """

    model_config = STRICT_FROZEN_CONFIG

    door: ProfileRecordDoor
    operation_definition_id: str = Field(min_length=1)
    label_words: str
    label_words_language: OutputLanguage


class ProfileRecordGroupsRequest(CredentialFreeOperationRequest):
    """Read one page of the groups of one kind, optionally pinned to an earlier page's revision."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    group_kind: ProfileRecordGroupKind
    cursor: NonNegativeInt = 0
    limit: int = Field(default=PROFILE_RECORD_GROUPS_MAX_ITEMS, ge=1, le=PROFILE_RECORD_GROUPS_MAX_ITEMS)
    expected_revision: int | None = Field(default=None, ge=1)
    expected_content_digest: ContentDigest | None = None
    expected_ledger_digest: ContentDigest | None = None
    output_language: OutputLanguage = OutputLanguage.ES

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_complete_pin(self) -> Self:
        pins = (self.expected_revision, self.expected_content_digest, self.expected_ledger_digest)
        if any(pin is None for pin in pins) and any(pin is not None for pin in pins):
            raise ValueError("a record group read pins its profile revision, digest and ledger digest together")
        if self.cursor and self.expected_revision is None:
            raise ValueError("a continuation requires its exact profile revision and ledger digest")
        return self


class ProfileRecordGroupItem(BaseModel):
    """The row that heads one group, with how many rows the group holds."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["group"] = "group"
    #: The group's own row identity, ``section.row``; every item of the group carries it.
    group_key: str
    payload_kind: ProfileRecordGroupKind
    section_key: str
    row_key: str
    summary_words: str
    summary_words_language: OutputLanguage
    member_count: NonNegativeInt
    ledger_row_count: NonNegativeInt
    #: What the group's payload kind is, in words.
    kind_words: str
    kind_words_language: OutputLanguage
    #: The doors of the group's own row: its edit door and its remove door.
    actions: tuple[ProfileRecordAction, ...]


class ProfileRecordMemberItem(BaseModel):
    """One row that names the group's row, or names another member, through a declared row reference."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["member"] = "member"
    group_key: str
    #: This row's identity, ``section.row``.
    row_ref: str
    #: The identity of the row this one names: the group's row or another member.
    parent_ref: str
    section_key: str
    row_key: str
    #: The declared reference, ``section.field``, through which this row names its parent.
    relation: str
    relation_words: str
    relation_words_language: OutputLanguage
    summary_words: str
    summary_words_language: OutputLanguage
    #: What kind of row this member is, in words.
    kind_words: str
    kind_words_language: OutputLanguage
    #: The doors of this member's own row.
    actions: tuple[ProfileRecordAction, ...]


class ProfileRecordLedgerRowItem(BaseModel):
    """One ledger row naming the group's row or one of its members."""

    model_config = STRICT_FROZEN_CONFIG

    kind: Literal["ledger_row"] = "ledger_row"
    group_key: str
    #: The identity of the row the ledger row names.
    linked_ref: str
    transaction_id: str
    booked_date: date
    amount: PublicDecimal
    currency: str
    direction: TransactionDirection
    description: str
    lifecycle_state: TransactionLifecycleState
    #: The expense concept the row states, when it states one.
    concept: str | None = None
    concept_words: str | None = None
    concept_words_language: OutputLanguage | None = None
    #: What a ledger row is, in words.
    kind_words: str
    kind_words_language: OutputLanguage
    #: This row's place among the group's ledger rows, from zero, and how many the group holds,
    #: so a page that starts inside a group's ledger rows still states their total.
    ledger_row_index: NonNegativeInt
    ledger_row_total: NonNegativeInt

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _concept_words_travel_together(self) -> Self:
        if (self.concept is None) != (self.concept_words is None) or (self.concept_words is None) != (
            self.concept_words_language is None
        ):
            raise ValueError("a ledger row's concept, its words and their language travel together")
        if self.ledger_row_index >= self.ledger_row_total:
            raise ValueError("a ledger row's place lies within its group's ledger row total")
        return self


type ProfileRecordGroupStreamItem = Annotated[
    ProfileRecordGroupItem | ProfileRecordMemberItem | ProfileRecordLedgerRowItem,
    Field(discriminator="kind"),
]


class ProfileRecordGroupsRefusalCode(StrEnum):
    """A read that cannot truthfully yield the page asked for."""

    STALE_REVISION = "stale_revision"
    ITEM_TOO_LARGE = "item_too_large"


class ProfileRecordGroupsResult(BaseModel):
    """One page of the group stream, or an explicit refusal; neither claims a profile effect."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: UUID
    group_kind: ProfileRecordGroupKind
    outcome: Literal["page", "refused"]
    refusal_code: ProfileRecordGroupsRefusalCode | None = None
    #: The sentence that tells the operator why the page was refused and what to do.
    refusal_words: str | None = None
    refusal_words_language: OutputLanguage | None = None
    record_revision: int = Field(ge=1)
    content_digest: ContentDigest
    ledger_digest: ContentDigest
    cursor: NonNegativeInt
    next_cursor: NonNegativeInt | None = None
    total_items: NonNegativeInt
    items: tuple[ProfileRecordGroupStreamItem, ...] = ()

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_page(self) -> Self:
        if (self.refusal_code is None) != (self.refusal_words is None) or (self.refusal_words is None) != (
            self.refusal_words_language is None
        ):
            raise ValueError("a refusal code, its words and their language travel together")
        if self.outcome == "refused":
            if self.refusal_code is None or self.items or self.next_cursor is not None:
                raise ValueError("a refused record group read carries no page")
            return self
        if self.refusal_code is not None or self.cursor + len(self.items) > self.total_items:
            raise ValueError("invalid record group page")
        if self.cursor < self.total_items and not self.items:
            raise ValueError("a record group page cannot claim progress without an item")
        expected_next = self.cursor + len(self.items)
        if self.next_cursor != (expected_next if expected_next < self.total_items else None):
            raise ValueError("record group continuation does not match the page items")
        return self


class ProfileRecordGroupsProjection(ProfileRecordGroupsResult):
    """The registered read result, released only after PROFILE_VALUES disclosure."""


def project_record_groups_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release a page only for its exact settled profile subject."""
    if not isinstance(result, ProfileRecordGroupsResult):
        raise TypeError("unexpected record group result")
    if receipt.identity.definition_id != PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID or (
        receipt.identity.subject_ref != profile_operation_subject(str(result.profile_id))
    ):
        raise ValueError("record group result does not match its settled subject")
    return ProfileRecordGroupsProjection.model_validate(result.model_dump(mode="python"))


__all__ = [
    "PROFILE_RECORD_GROUPS_MAX_ITEMS",
    "PROFILE_RECORD_GROUPS_MAX_RESULT_BYTES",
    "PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID",
    "PROFILE_RECORD_GROUPS_PHASES",
    "ProfileRecordAction",
    "ProfileRecordDoor",
    "ProfileRecordGroupItem",
    "ProfileRecordGroupKind",
    "ProfileRecordGroupStreamItem",
    "ProfileRecordGroupsProjection",
    "ProfileRecordGroupsRefusalCode",
    "ProfileRecordGroupsRequest",
    "ProfileRecordGroupsResult",
    "ProfileRecordLedgerRowItem",
    "ProfileRecordMemberItem",
    "project_record_groups_result",
]
