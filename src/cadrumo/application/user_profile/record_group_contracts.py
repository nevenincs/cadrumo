"""Public contracts of the grouped read of related profile rows.

A record group is one row of a repeatable profile section together with every row
that names it through a schema-declared row reference, and the ledger rows that
name any of them. The pension contribution kind groups the taxpayer's stored
contribution certificates by ejercicio instead: the certificates live in their own
encrypted store, a group is one year, and each certificate is a member of its year.
The read serves the relation, the row identities and the words
of every row, so a surface iterates the stream by item kind and joins nothing.

A lease member also serves its art. 23.2 LIRPF reduction: the facts the derivation reads, and per
ejercicio of a Modelo 100 return the profile has started the tier, that it does not apply, or the
stored fact that keeps it from being derived with the edit door opened on that field. A lease with
no end date carries a further edit door opened on its end date.

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
from ...domain.renta.rental_reduction_derivation import RentalReductionRefusal
from ...domain.transactions.enums import TransactionDirection, TransactionLifecycleState
from ..operations.models import CredentialFreeOperationRequest, OperationTerminalReceipt
from ..operations.public_scalar import PublicDecimal
from ..prevision_social_contribution.results import PrevisionSocialRowProjection

PROFILE_RECORD_GROUPS_OPERATION_DEFINITION_ID: Final = "user-profile.record-groups"
PROFILE_RECORD_GROUPS_PHASES: Final = ("user-profile.record-groups.read", "user-profile.record-groups.project")
PENSION_CONTRIBUTION_SECTION_KEY: Final = "prevision_social_contribution"
"""The section key the pension contribution certificates are served under; they are not a profile section."""
PROFILE_RECORD_GROUPS_MAX_ITEMS: Final = 128
# The result is nested in a settled-operation response and then a runtime frame;
# keep generous space beneath that frame's 64 KiB ceiling for both envelopes.
PROFILE_RECORD_GROUPS_MAX_RESULT_BYTES: Final = 20_000


class ProfileRecordGroupKind(StrEnum):
    """Which rows head the groups: the payload kind a surface renders without a branch."""

    RENTAL_PROPERTY = "rental_property"
    PENSION_CONTRIBUTION = "pension_contribution"


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
    #: The field of the row the door opens on; ``None`` opens the row as a whole.
    field_key: str | None = Field(default=None, min_length=1)


class ProfileRecordReductionOutcome(StrEnum):
    """What the art. 23.2 LIRPF reduction does to one lease in one ejercicio."""

    APPLIES = "applies"
    DOES_NOT_APPLY = "does_not_apply"
    NOT_DETERMINABLE = "not_determinable"


class ProfileRecordReductionFact(BaseModel):
    """One stored fact of a lease as the reduction's derivation read it."""

    model_config = STRICT_FROZEN_CONFIG

    field_key: str = Field(min_length=1)
    #: The fact's name and the value the lease states for it, or that it states none.
    fact_words: str
    fact_words_language: OutputLanguage
    stated: bool


class ProfileRecordMissingFact(BaseModel):
    """The fact that keeps a reduction from being derived and the door that states it."""

    model_config = STRICT_FROZEN_CONFIG

    field_key: str = Field(min_length=1)
    #: The name of the fact.
    fact_words: str
    fact_words_language: OutputLanguage
    #: The edit door of the lease row, opened on this fact's field.
    way_out: ProfileRecordAction

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _door_opens_on_the_fact(self) -> Self:
        if self.way_out.door is not ProfileRecordDoor.EDIT or self.way_out.field_key != self.field_key:
            raise ValueError("the way out of a missing fact is the edit door opened on its field")
        return self


def _require_tier_with_application(
    outcome: ProfileRecordReductionOutcome, tier: str | None, words: str | None, language: object
) -> None:
    applies = outcome is ProfileRecordReductionOutcome.APPLIES
    if (tier is not None) != applies or (tier is None) != (words is None) or (words is None) != (language is None):
        raise ValueError("a reduction that applies names its tier with its words and their language, and no other does")


def _require_refusal_with_undetermined_ejercicio(
    outcome: ProfileRecordReductionOutcome, ejercicio: int | None, refusal: object, has_missing_fact: bool
) -> None:
    undetermined = outcome is ProfileRecordReductionOutcome.NOT_DETERMINABLE
    if (refusal is not None) != (undetermined and ejercicio is not None):
        raise ValueError("a refusal is served exactly for an ejercicio whose reduction cannot be derived")
    if has_missing_fact and refusal is None:
        raise ValueError("a missing fact belongs to a refused derivation")
    if ejercicio is None and not undetermined:
        raise ValueError("an outcome without an ejercicio cannot be determined")


class ProfileRecordReductionYear(BaseModel):
    """The reduction of one lease for one ejercicio, or why none can be stated."""

    model_config = STRICT_FROZEN_CONFIG

    #: The ejercicio of a Modelo 100 return the profile has started; ``None`` when there is none to speak of.
    ejercicio: int | None = Field(default=None, ge=1)
    outcome: ProfileRecordReductionOutcome
    #: The derived tier's token, for an outcome of ``applies``.
    tier: str | None = Field(default=None, min_length=1)
    tier_words: str | None = None
    tier_words_language: OutputLanguage | None = None
    #: The derivation's refusal, for an outcome of ``not_determinable`` in an ejercicio.
    refusal_code: RentalReductionRefusal | None = None
    #: The sentence that says the outcome, and for a refusal what the operator does next.
    outcome_words: str
    outcome_words_language: OutputLanguage
    missing_fact: ProfileRecordMissingFact | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _outcome_carries_what_it_needs(self) -> Self:
        _require_tier_with_application(self.outcome, self.tier, self.tier_words, self.tier_words_language)
        _require_refusal_with_undetermined_ejercicio(
            self.outcome, self.ejercicio, self.refusal_code, self.missing_fact is not None
        )
        return self


class ProfileRecordReduction(BaseModel):
    """The art. 23.2 LIRPF reduction of one lease: the facts it reads and its outcome per ejercicio."""

    model_config = STRICT_FROZEN_CONFIG

    title_words: str
    title_words_language: OutputLanguage
    facts: tuple[ProfileRecordReductionFact, ...]
    years: tuple[ProfileRecordReductionYear, ...] = Field(min_length=1)


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
    #: The art. 23.2 LIRPF reduction, for a lease.
    reduction: ProfileRecordReduction | None = None
    #: The stored certificate, with the revision its correct and remove doors submit, for a pension member.
    #: It carries keyed references and names, never a tax identifier.
    contribution: PrevisionSocialRowProjection | None = None


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


def _require_refusal_words_together(code: object, words: object, language: object) -> None:
    if (code is None) != (words is None) or (words is None) != (language is None):
        raise ValueError("a refusal code, its words and their language travel together")


def _require_refusal_carries_no_page(code: object, items: tuple[object, ...], next_cursor: int | None) -> None:
    if code is None or items or next_cursor is not None:
        raise ValueError("a refused record group read carries no page")


def _require_consistent_page(
    code: object, cursor: int, items: tuple[object, ...], total_items: int, next_cursor: int | None
) -> None:
    if code is not None or cursor + len(items) > total_items:
        raise ValueError("invalid record group page")
    if cursor < total_items and not items:
        raise ValueError("a record group page cannot claim progress without an item")
    expected_next = cursor + len(items)
    if next_cursor != (expected_next if expected_next < total_items else None):
        raise ValueError("record group continuation does not match the page items")


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
        _require_refusal_words_together(self.refusal_code, self.refusal_words, self.refusal_words_language)
        if self.outcome == "refused":
            _require_refusal_carries_no_page(self.refusal_code, self.items, self.next_cursor)
        else:
            _require_consistent_page(self.refusal_code, self.cursor, self.items, self.total_items, self.next_cursor)
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
    "PENSION_CONTRIBUTION_SECTION_KEY",
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
    "ProfileRecordMissingFact",
    "ProfileRecordReduction",
    "ProfileRecordReductionFact",
    "ProfileRecordReductionOutcome",
    "ProfileRecordReductionYear",
    "project_record_groups_result",
]
